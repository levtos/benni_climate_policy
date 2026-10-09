"""Coordinator for Benni Climate Policy."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
import logging
import time
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers.event import async_call_later, async_track_state_change_event, async_track_time_interval
from homeassistant.util import dt as dt_util

from .apply_engine import ApplyEngine, ApplyGateState
from .const import (
    CONF_APPLY_ACTIVE,
    CONF_APPLY_COOLDOWN_SECONDS,
    CONF_BATH_DIFFUSER,
    CONF_BATH_FAN,
    CONF_BATH_SHOWER_ACTIVITY,
    CONF_BATH_TOILET_ACTIVITY,
    CONF_COOLDOWN_SECONDS,
    CONF_FORECAST_TEMPERATURE,
    CONF_KITCHEN_PATIO_OPEN,
    CONF_KITCHEN_PATIO_TILT,
    CONF_LIVING_WINDOW_LEFT_OPEN,
    CONF_LIVING_WINDOW_LEFT_TILT,
    CONF_LIVING_WINDOW_RIGHT_OPEN,
    CONF_LIVING_WINDOW_RIGHT_TILT,
    CORE_OPENINGS_MASTER_ENTITY,
    CONF_OUTDOOR_FEELS_LIKE,
    CONF_OUTDOOR_HUMIDITY,
    CONF_OUTDOOR_LUX,
    CONF_OUTDOOR_TEMPERATURE,
    CONF_OUTDOOR_WIND_SPEED,
    CONF_STARTUP_BLOCK_SECONDS,
    CONF_SUN,
    CONF_SYSTEM_READY,
    CONF_WEATHER_CONDITION,
    CONF_WEATHER_ENTITY,
    CONF_ZONE_HUMIDITY,
    CONF_ZONE_TEMPERATURE,
    CONF_ZONE_THERMOSTAT,
    DEFAULT_APPLY_ACTIVE,
    DEFAULT_COOLDOWN_SECONDS,
    DEFAULT_STARTUP_BLOCK_SECONDS,
    HEATING_ZONES,
    INTEGRATION_VERSION,
    PRESET,
    SELF_GENERATED_INPUT_ENTITY_IDS,
    ZONE_BATHROOM,
    ZONE_KITCHEN,
    ZONE_LIVING,
)
from .bathroom import (
    BathroomClimateInput,
    BathroomDiffuserPlan,
    BathroomFanPlan,
    BathroomHumidityInput,
    bath_tuning_from_options,
    decide_bathroom_climate,
    decide_bathroom_diffuser,
    decide_bathroom_fan,
)
from .context_resolver import ContextResolver
from .models import (
    ApplyResult,
    ClimateDecision,
    EffectiveTemperatureInput,
    WindowState,
    ZoneInput,
    ZonePlan,
    window_state_from_master_value,
)
from .options import apply_cooldown_seconds_from_config
from .policy import (
    decide_zone,
    dynamic_floor_slab_delta,
    effective_outdoor_temperature,
    empty_context,
    evaluate_room_comfort,
    FloorSlabDeltaBreakdown,
    FloorSlabDeltaInput,
    floor_slab_delta_for_month,
    policy_tuning_from_options,
    policy_visibility_snapshot,
    setpoint_for,
    thermostat_target_for,
    threshold_for_month_config,
)
from .tuning_options import tuning_options_snapshot, validated_options_update
from .weather_resolver import DEFAULT_FORECAST_CACHE_TTL_SECONDS, ForecastCache, WeatherResolution, WeatherResolver

_LOGGER = logging.getLogger(__name__)
EVALUATE_DEBOUNCE_SECONDS = 2
LAST_KNOWN_VALUE_TTL_SECONDS = 2 * 60 * 60
BOOST_STANDARD_DURATION = timedelta(minutes=45)
BOOST_PRE_NIGHT_DURATION = timedelta(minutes=15)
BATH_FAN_USAGE_HOLD_DURATION = timedelta(minutes=30)
HEAT_STRENGTH = {"off": 0, "protection": 0, "spar": 1, "grundwaerme": 1, "komfort": 2, "boost": 3}
IMMEDIATE_DECISION_REASONS = {
    "bio_sleep_forces_off",
    "bio_waking_forces_off",
    "window_blocks_heating",
    "presence_far_forces_off",
    "passing_through_blocks_preheat",
    "dynamic_wakeup_cutoff",
    "room_temperature_above_target_no_heating",
    "living_area_temperature_above_target_no_heating",
    "bath_temperature_above_target_no_heating",
    "no_heat_demand",
    "presence_preheat_caps_to_spar",
    "free_time_early_night_holds_comfort",
    "night_temperature_ramp_late_evening",
    "night_temperature_ramp_early_night",
    "night_temperature_ramp_late_night",
    "night_hard_spar",
}

OPENING_ATTRIBUTE_BY_KEY = {
    CONF_LIVING_WINDOW_LEFT_OPEN: "living_window_left",
    CONF_LIVING_WINDOW_LEFT_TILT: "living_window_left",
    CONF_LIVING_WINDOW_RIGHT_OPEN: "living_window_right",
    CONF_LIVING_WINDOW_RIGHT_TILT: "living_window_right",
    CONF_KITCHEN_PATIO_OPEN: "kitchen_patio_door",
    CONF_KITCHEN_PATIO_TILT: "kitchen_patio_door",
}


def _float(value: str | None) -> float | None:
    if value in (None, "", "unknown", "unavailable", "none"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _state_value(value: str | None) -> str | None:
    if value in (None, "", "unknown", "unavailable", "none"):
        return None
    return str(value)


def _preferred_attribute_for_key(key: str) -> str | None:
    if key.endswith("_humidity"):
        return "humidity"
    if key in OPENING_ATTRIBUTE_BY_KEY:
        return OPENING_ATTRIBUTE_BY_KEY[key]
    return None


def _state_or_preferred_attribute(key: str, state) -> str | None:
    if state is None:
        return None
    attr = _preferred_attribute_for_key(key)
    if attr and attr in state.attributes:
        value = state.attributes.get(attr)
        if value not in (None, "", "unknown", "unavailable", "none"):
            return str(value)
    return state.state


def _input_role(key: str) -> str:
    if key == CONF_BATH_FAN:
        return "actuator"
    if key in (CONF_BATH_TOILET_ACTIVITY, CONF_BATH_SHOWER_ACTIVITY):
        return "activity"
    if key.startswith("context_"):
        return "context"
    if key in (
        CONF_OUTDOOR_TEMPERATURE,
        CONF_OUTDOOR_HUMIDITY,
        CONF_OUTDOOR_WIND_SPEED,
        CONF_FORECAST_TEMPERATURE,
        CONF_WEATHER_ENTITY,
        CONF_WEATHER_CONDITION,
        CONF_OUTDOOR_LUX,
        CONF_SUN,
    ):
        return "weather"
    if "window" in key or "patio_door" in key:
        return "window"
    if key.endswith("_thermostat"):
        return "thermostat"
    if key.endswith("_temperature") or key.endswith("_humidity"):
        return "room"
    if key == CONF_SYSTEM_READY:
        return "system"
    return "other"


def _input_status(state_value: str | None) -> str:
    if state_value is None:
        return "missing"
    if state_value in ("unknown", "unavailable"):
        return state_value
    return "ok"


def _is_watchable_entity_id(value: Any) -> bool:
    return isinstance(value, str) and "." in value and value not in SELF_GENERATED_INPUT_ENTITY_IDS


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value) in ("on", "open", "true", "True", "1")


def _window_activity_from_state(state: Any, attr_name: str, *, active_states: tuple[Any, ...]) -> tuple[str | None, bool]:
    if state is None:
        return None, False
    if attr_name in state.attributes:
        active = _coerce_bool(state.attributes.get(attr_name))
        return ("on" if active else "off"), active
    return state.state, state.state in active_states


class ClimatePolicyCoordinator:
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.apply_engine = ApplyEngine(hass)
        self._unsub: list[CALLBACK_TYPE] = []
        self._ha_started_unsub: CALLBACK_TYPE | None = None
        self._evaluate_debounce_unsub: CALLBACK_TYPE | None = None
        self._bath_fan_usage_hold_unsub: CALLBACK_TYPE | None = None
        self._listeners: list[CALLBACK_TYPE] = []
        self._ha_started = False
        self._started_at = time.monotonic()
        self._weather_forecast_cache: ForecastCache = {}
        self.decision: ClimateDecision | None = None
        self.weather_resolution: WeatherResolution | None = None
        self.bathroom_fan_plan: BathroomFanPlan | None = None
        self.bathroom_diffuser_plan: BathroomDiffuserPlan | None = None
        self.last_apply_result: ApplyResult | None = None
        self.last_recalculate_at: datetime | None = None
        self.recalculate_count = 0
        self.last_recalculate_reason = "never"
        self.entity_publish_skipped_count = 0
        self.entity_publish_changed_count = 0
        apply_zones = (*HEATING_ZONES, ZONE_BATHROOM, "bathroom_fan", "bathroom_diffuser")
        self.last_applied_hash: dict[str, str | None] = {zone: None for zone in apply_zones}
        self.last_apply_at: dict[str, datetime | None] = {zone: None for zone in apply_zones}
        self.last_bath_fan_active_at: datetime | None = None
        self._bath_fan_cap_deadline: datetime | None = None
        self._bath_fan_cooldown_until: datetime | None = None
        self._diffuser_run_started_at: datetime | None = None
        self._last_good_numeric: dict[str, tuple[float, datetime]] = {}
        self._numeric_fallback_keys: set[str] = set()
        self._zone_profile_state: dict[str, str | None] = {zone: None for zone in (*HEATING_ZONES, ZONE_BATHROOM)}
        self._zone_profile_reason: dict[str, str | None] = {zone: None for zone in (*HEATING_ZONES, ZONE_BATHROOM)}
        self._zone_hysteresis_pending: dict[str, tuple[str, str, datetime]] = {}
        self._boost_until: dict[str, datetime | None] = {zone: None for zone in HEATING_ZONES}
        self._boost_reason: dict[str, str | None] = {zone: None for zone in HEATING_ZONES}
        self._last_day_state: str | None = None
        self._last_bathroom_humidity_sample: tuple[float, datetime] | None = None
        self._bath_fan_usage_hold_until: datetime | None = None
        self._floor_slab_daily_samples: dict[str, float] = {}
        self.floor_slab_delta: FloorSlabDeltaBreakdown | None = None
        self.last_evaluate_duration_ms: float | None = None
        self.evaluate_duration_samples_ms: list[float] = []
        self.last_apply_duration_ms: float | None = None
        self.last_forecast_duration_ms: float | None = None

    @property
    def config(self) -> dict[str, Any]:
        return {**PRESET, **self.entry.data, **self.entry.options}

    @property
    def apply_active(self) -> bool:
        return bool(self.config.get(CONF_APPLY_ACTIVE, DEFAULT_APPLY_ACTIVE))

    @property
    def cooldown_seconds(self) -> int:
        return apply_cooldown_seconds_from_config(self.config)

    @property
    def startup_block_seconds(self) -> int:
        return int(self.config.get(CONF_STARTUP_BLOCK_SECONDS, DEFAULT_STARTUP_BLOCK_SECONDS))

    @property
    def policy_tuning(self):
        return policy_tuning_from_options(self.entry.options)

    @property
    def bath_tuning(self):
        return bath_tuning_from_options(self.entry.options)

    @property
    def startup_ready(self) -> bool:
        return self._ha_started and (time.monotonic() - self._started_at) >= self.startup_block_seconds

    def add_listener(self, cb: CALLBACK_TYPE) -> None:
        self._listeners.append(cb)

    def remove_listener(self, cb: CALLBACK_TYPE) -> None:
        if cb in self._listeners:
            self._listeners.remove(cb)

    def _notify(self) -> None:
        for cb in list(self._listeners):
            cb()

    @callback
    def async_start(self) -> None:
        if self.hass.is_running:
            self._ha_started = True
            self._started_at = time.monotonic()
        else:
            self._ha_started_unsub = self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, self._on_started)

        watch = {
            value
            for key, value in self.config.items()
            if key != CONF_OUTDOOR_FEELS_LIKE and _is_watchable_entity_id(value)
        }
        if watch:
            self._unsub.append(async_track_state_change_event(self.hass, list(watch), self._on_state_change))
        self._unsub.append(async_track_time_interval(self.hass, self._on_interval, timedelta(minutes=15)))

    @callback
    def async_stop(self) -> None:
        if self._evaluate_debounce_unsub:
            self._evaluate_debounce_unsub()
            self._evaluate_debounce_unsub = None
        if self._bath_fan_usage_hold_unsub:
            self._bath_fan_usage_hold_unsub()
            self._bath_fan_usage_hold_unsub = None
        if self._ha_started_unsub:
            self._ha_started_unsub()
            self._ha_started_unsub = None
        for unsub in self._unsub:
            unsub()
        self._unsub.clear()

    @callback
    def _on_started(self, _event) -> None:
        self._ha_started_unsub = None
        self._ha_started = True
        self._started_at = time.monotonic()
        self.hass.async_create_task(self.async_evaluate(auto_apply=False, reason="homeassistant_started"))

    @callback
    def _on_interval(self, _now) -> None:
        self.hass.async_create_task(self.async_evaluate(auto_apply=True, reason="interval_15m"))

    @callback
    def _on_state_change(self, event: Event) -> None:
        entity_id = event.data.get("entity_id", "unknown")
        new_state = event.data.get("new_state")
        now = dt_util.now()
        if entity_id == self.config.get(CONF_BATH_FAN):
            if getattr(new_state, "state", None) == "on":
                self.last_bath_fan_active_at = now
            elif getattr(new_state, "state", None) == "off":
                self.last_bath_fan_active_at = None
        if self._is_bath_fan_usage_source(entity_id) and getattr(new_state, "state", None) == "on":
            self._extend_bath_fan_usage_hold(now)
        self._schedule_evaluate(auto_apply=True, reason=f"state_change:{entity_id}")

    @callback
    def _schedule_evaluate(self, *, auto_apply: bool, reason: str) -> None:
        if self._evaluate_debounce_unsub:
            self._evaluate_debounce_unsub()

        @callback
        def _run(_now) -> None:
            self._evaluate_debounce_unsub = None
            self.hass.async_create_task(self.async_evaluate(auto_apply=auto_apply, reason=reason))

        self._evaluate_debounce_unsub = async_call_later(self.hass, EVALUATE_DEBOUNCE_SECONDS, _run)

    def record_entity_publish(self, *, changed: bool) -> None:
        if changed:
            self.entity_publish_changed_count += 1
        else:
            self.entity_publish_skipped_count += 1

    def _state(self, key: str) -> str | None:
        entity_id = self.config.get(key)
        state = self.hass.states.get(entity_id) if entity_id else None
        return _state_or_preferred_attribute(key, state)

    def _state_obj(self, key: str):
        entity_id = self.config.get(key)
        return self.hass.states.get(entity_id) if entity_id else None

    def _bath_fan_active_since(self, now: datetime) -> datetime | None:
        state = self._state_obj(CONF_BATH_FAN)
        if state is None or state.state != "on":
            return None
        candidates = [
            value
            for value in (getattr(state, "last_changed", None), self.last_bath_fan_active_at)
            if isinstance(value, datetime) and value <= now
        ]
        return max(candidates) if candidates else now

    def _bath_fan_active_since_uncertain(self) -> bool:
        state = self._state_obj(CONF_BATH_FAN)
        if state is None or state.state != "on":
            return False
        return self.last_bath_fan_active_at is None

    def _is_bath_fan_usage_source(self, entity_id: str | None) -> bool:
        return entity_id in {
            self.config.get(CONF_BATH_TOILET_ACTIVITY),
            self.config.get(CONF_BATH_SHOWER_ACTIVITY),
        }

    def _extend_bath_fan_usage_hold(self, now: datetime) -> None:
        self._bath_fan_usage_hold_until = now + BATH_FAN_USAGE_HOLD_DURATION
        if self._bath_fan_usage_hold_unsub:
            self._bath_fan_usage_hold_unsub()

        @callback
        def _expire(_now) -> None:
            self._bath_fan_usage_hold_unsub = None
            self.hass.async_create_task(self.async_evaluate(auto_apply=True, reason="bath_fan_usage_hold_expired"))

        self._bath_fan_usage_hold_unsub = async_call_later(self.hass, BATH_FAN_USAGE_HOLD_DURATION.total_seconds(), _expire)

    def _ensure_bath_fan_usage_hold_for_active_sources(self, now: datetime) -> None:
        if self._state(CONF_BATH_TOILET_ACTIVITY) == "on" or self._state(CONF_BATH_SHOWER_ACTIVITY) == "on":
            if self._bath_fan_usage_hold_until is None or self._bath_fan_usage_hold_until <= now:
                self._extend_bath_fan_usage_hold(now)

    def _bath_fan_usage_hold_active(self, now: datetime) -> bool:
        if self._bath_fan_usage_hold_until is None:
            return False
        if now >= self._bath_fan_usage_hold_until:
            self._bath_fan_usage_hold_until = None
            return False
        return True

    def _float_state(self, key: str, *, hold_last: bool = True) -> float | None:
        value = _float(self._state(key))
        now = dt_util.now()
        if value is not None:
            self._last_good_numeric[key] = (value, now)
            return value
        if not hold_last:
            return None
        cached = self._last_good_numeric.get(key)
        if cached is None:
            return None
        cached_value, cached_at = cached
        if now - cached_at > timedelta(seconds=LAST_KNOWN_VALUE_TTL_SECONDS):
            return None
        self._numeric_fallback_keys.add(key)
        return cached_value

    def _sun_elevation(self) -> float | None:
        entity_id = self.config.get(CONF_SUN)
        state = self.hass.states.get(entity_id) if entity_id else None
        if not state:
            return None
        return _float(str(state.attributes.get("elevation")))

    def input_snapshot(self) -> list[dict[str, Any]]:
        keys = sorted({*PRESET, *(key for key, value in self.config.items() if isinstance(value, str))})
        out: list[dict[str, Any]] = []
        for key in keys:
            configured = self.config.get(key)
            preset = PRESET.get(key)
            entity_id = configured or preset
            state = self.hass.states.get(entity_id) if entity_id else None
            state_value = _state_or_preferred_attribute(key, state)
            attr = _preferred_attribute_for_key(key)
            if configured and preset and configured == preset:
                source = "candidate"
            elif configured:
                source = "user configured"
            elif preset:
                source = "fallback"
            else:
                source = "missing"
            out.append({
                "role": _input_role(key),
                "key": key,
                "entity_id": entity_id,
                "attribute": attr if state is not None and attr in state.attributes else None,
                "state": state_value,
                "status": _input_status(state_value),
                "source": source,
            })
        return out

    def effective_input_snapshot(self) -> dict[str, Any]:
        sun_entity = self.config.get(CONF_SUN)
        sun_state = self.hass.states.get(sun_entity) if sun_entity else None
        weather_resolution = self.weather_resolution.as_dict() if self.weather_resolution else None
        return {
            "real_temperature": self._float_state(CONF_OUTDOOR_TEMPERATURE),
            "outdoor_humidity": self._float_state(CONF_OUTDOOR_HUMIDITY),
            "outdoor_wind_speed": self._float_state(CONF_OUTDOOR_WIND_SPEED),
            "feels_like_temperature": (
                self.weather_resolution.feels_like_temperature
                if self.weather_resolution
                else None
            ),
            "forecast_temperature": (
                self.weather_resolution.forecast_temperature
                if self.weather_resolution
                else self._float_state(CONF_FORECAST_TEMPERATURE)
            ),
            "weather_condition": self._state(CONF_WEATHER_CONDITION),
            "outdoor_lux": self._float_state(CONF_OUTDOOR_LUX),
            "sun_elevation": self._sun_elevation(),
            "source_entities": {
                "real_temperature": self.config.get(CONF_OUTDOOR_TEMPERATURE),
                "outdoor_humidity": self.config.get(CONF_OUTDOOR_HUMIDITY),
                "outdoor_wind_speed": self.config.get(CONF_OUTDOOR_WIND_SPEED),
                "feels_like_temperature": "computed_from_raw_weather_inputs",
                "forecast_temperature": self.config.get(CONF_FORECAST_TEMPERATURE),
                "weather_entity": self.config.get(CONF_WEATHER_ENTITY),
                "weather_condition": self.config.get(CONF_WEATHER_CONDITION),
                "outdoor_lux": self.config.get(CONF_OUTDOOR_LUX),
                "sun": sun_entity,
            },
            "forecast_resolution": weather_resolution.get("forecast") if weather_resolution else None,
            "feels_like_resolution": weather_resolution.get("feels_like") if weather_resolution else None,
            "weather_resolution": weather_resolution,
            "floor_slab_delta": self.floor_slab_delta.as_dict() if self.floor_slab_delta else None,
            "floor_slab_forecast_resolution": weather_resolution.get("floor_slab_forecast") if weather_resolution else None,
            "sun_state": sun_state.state if sun_state else None,
        }

    @property
    def system_ready(self) -> bool:
        external = self._state(CONF_SYSTEM_READY)
        if external in ("off", "false", "False", "unknown", "unavailable", ""):
            return False
        if self.decision is None:
            return False
        return self.decision.effective_temperature.effective_temperature is not None

    @property
    def apply_ready(self) -> bool:
        return self.apply_active and self.system_ready and self.startup_ready

    @property
    def manual_apply_possible(self) -> bool:
        return self.system_ready and self.startup_ready

    async def async_evaluate(self, *, auto_apply: bool = False, reason: str = "manual") -> ClimateDecision:
        evaluate_started = time.perf_counter()
        now = dt_util.now()
        self.recalculate_count += 1
        self.last_recalculate_at = now
        self.last_recalculate_reason = reason
        tuning = self.policy_tuning
        bath_tuning = self.bath_tuning
        self._numeric_fallback_keys.clear()
        context = ContextResolver(self.hass, self.config).resolve()
        real_temperature = self._float_state(CONF_OUTDOOR_TEMPERATURE)
        outdoor_humidity = self._float_state(CONF_OUTDOOR_HUMIDITY)
        outdoor_wind_speed = self._float_state(CONF_OUTDOOR_WIND_SPEED)
        forecast_started = time.perf_counter()
        self.weather_resolution = await WeatherResolver(
            self.hass,
            self.config,
            forecast_cache=self._weather_forecast_cache,
            forecast_cache_ttl_seconds=DEFAULT_FORECAST_CACHE_TTL_SECONDS,
        ).async_resolve(
            real_temperature=real_temperature,
            outdoor_humidity=outdoor_humidity,
            outdoor_wind_speed=outdoor_wind_speed,
            now=now,
        )
        self.last_forecast_duration_ms = round((time.perf_counter() - forecast_started) * 1000, 2)
        self._record_floor_slab_daily_sample(now, real_temperature)
        self.floor_slab_delta = self._floor_slab_delta_breakdown(
            now,
            real_temperature,
            self.weather_resolution.floor_slab_tomorrow_temperature,
            tuning,
        )
        effective = effective_outdoor_temperature(
            EffectiveTemperatureInput(
                real_temperature=real_temperature,
                feels_like_temperature=self.weather_resolution.feels_like_temperature,
                forecast_temperature=self.weather_resolution.forecast_temperature,
                weather_condition=self._state(CONF_WEATHER_CONDITION),
                outdoor_lux=self._float_state(CONF_OUTDOOR_LUX),
                sun_elevation=self._sun_elevation(),
                month=now.month,
            ),
            floor_slab_tau=tuning.floor_slab_tau,
            lux_bonus_max=tuning.lux_bonus_max,
            lux_reference=tuning.lux_reference,
            feels_like_damping=tuning.feels_like_damping,
            forecast_weight=tuning.forecast_weight,
        )
        if self._numeric_fallback_keys & {
            CONF_OUTDOOR_TEMPERATURE,
            CONF_OUTDOOR_HUMIDITY,
            CONF_OUTDOOR_WIND_SPEED,
            CONF_FORECAST_TEMPERATURE,
            CONF_OUTDOOR_LUX,
        }:
            effective = replace(effective, input_quality="fallback")
        zone_inputs = {
            ZONE_LIVING: self._zone_input(ZONE_LIVING),
            ZONE_KITCHEN: self._zone_input(ZONE_KITCHEN),
        }
        bathroom_input = self._bathroom_climate_input()
        fan_drying_active = bool(
            self.bathroom_fan_plan.diagnostics.get("drying_recommended")
            if self.bathroom_fan_plan
            else False
        )
        bathroom_plan = decide_bathroom_climate(
            bathroom_input,
            context,
            effective,
            now,
            bath_tuning,
            indoor_tuning=tuning,
            floor_slab_delta=self.floor_slab_delta,
            fan_drying_active=fan_drying_active,
        )
        bathroom_plan = self._apply_floor_slab_context(bathroom_plan, bathroom_input, self.floor_slab_delta)
        plans = {
            ZONE_LIVING: decide_zone(zone_inputs[ZONE_LIVING], context, effective, now, tuning=tuning, floor_slab_delta=self.floor_slab_delta),
            ZONE_KITCHEN: decide_zone(zone_inputs[ZONE_KITCHEN], context, effective, now, tuning=tuning, floor_slab_delta=self.floor_slab_delta),
            ZONE_BATHROOM: bathroom_plan,
        }
        for zone_id in HEATING_ZONES:
            plans[zone_id] = self._apply_hysteresis(zone_id, plans[zone_id], now, tuning)
        self._apply_stateful_boosts(plans, zone_inputs, context, now, tuning)
        self._commit_zone_profiles(plans)
        self.bathroom_fan_plan = decide_bathroom_fan(
            self._bathroom_humidity_input(),
            plans[ZONE_BATHROOM],
            now=now,
            day_state=_state_value(context.day_state.value),
            last_fan_active_at=self.last_bath_fan_active_at,
            tuning=bath_tuning,
        )
        self._bath_fan_cap_deadline = self.bathroom_fan_plan.cap_deadline
        self._bath_fan_cooldown_until = self.bathroom_fan_plan.cooldown_until
        self.bathroom_diffuser_plan = decide_bathroom_diffuser(
            self.bathroom_fan_plan,
            run_started_at=self._diffuser_run_started_at,
            now=now,
            tuning=bath_tuning,
        )
        self._diffuser_run_started_at = self.bathroom_diffuser_plan.run_started_at
        self._last_day_state = _state_value(context.day_state.value)
        self.decision = ClimateDecision(context, effective, plans, now, self.system_ready)
        self.last_evaluate_duration_ms = round((time.perf_counter() - evaluate_started) * 1000, 2)
        self.evaluate_duration_samples_ms.append(self.last_evaluate_duration_ms)
        self.evaluate_duration_samples_ms = self.evaluate_duration_samples_ms[-100:]
        self._notify()
        if auto_apply and self.apply_active:
            await self.async_apply(manual=False, dry_run=False, refresh=False)
        return self.decision

    def _record_floor_slab_daily_sample(self, now: datetime, real_temperature: float | None) -> None:
        if real_temperature is None:
            return
        self._floor_slab_daily_samples[now.date().isoformat()] = real_temperature
        cutoff = now.date() - timedelta(days=3)
        self._floor_slab_daily_samples = {
            key: value
            for key, value in self._floor_slab_daily_samples.items()
            if datetime.fromisoformat(key).date() >= cutoff
        }

    def _floor_slab_delta_breakdown(
        self,
        now: datetime,
        real_temperature: float | None,
        forecast_temperature: float | None,
        tuning: Any,
    ) -> FloorSlabDeltaBreakdown:
        yesterday_key = (now.date() - timedelta(days=1)).isoformat()
        static_fallback = floor_slab_delta_for_month(now.month, tuning)
        return dynamic_floor_slab_delta(
            FloorSlabDeltaInput(
                yesterday_temperature=self._floor_slab_daily_samples.get(yesterday_key),
                today_temperature=real_temperature,
                tomorrow_temperature=forecast_temperature,
                static_fallback_delta=static_fallback,
            ),
            tuning,
        )

    def _living_area_windows(self) -> tuple[WindowState, ...]:
        return (
            self._window_state(CONF_LIVING_WINDOW_LEFT_OPEN, CONF_LIVING_WINDOW_LEFT_TILT),
            self._window_state(CONF_LIVING_WINDOW_RIGHT_OPEN, CONF_LIVING_WINDOW_RIGHT_TILT),
            self._window_state(CONF_KITCHEN_PATIO_OPEN, CONF_KITCHEN_PATIO_TILT),
        )

    def _window_state(
        self,
        open_key: str,
        tilt_key: str,
    ) -> WindowState:
        open_state = self._state_obj(open_key)
        tilt_state = self._state_obj(tilt_key)
        if (
            self.config.get(open_key) == CORE_OPENINGS_MASTER_ENTITY
            and self.config.get(tilt_key) == CORE_OPENINGS_MASTER_ENTITY
            and OPENING_ATTRIBUTE_BY_KEY.get(open_key) == OPENING_ATTRIBUTE_BY_KEY.get(tilt_key)
        ):
            attr_name = OPENING_ATTRIBUTE_BY_KEY[open_key]
            return window_state_from_master_value(
                open_state.attributes.get(attr_name) if open_state else None
            )
        open_value, _ = _window_activity_from_state(
            open_state,
            "open",
            active_states=tuple(value for value in ("on", "open", "true", "True") if value is not False),
        )
        tilt_value, _ = _window_activity_from_state(
            tilt_state,
            "tilted",
            active_states=("on", "open", "true", "True", True),
        )
        return WindowState(open_value, tilt_value)

    def _zone_input(self, zone: str) -> ZoneInput:
        windows: tuple[WindowState, ...]
        if zone in (ZONE_LIVING, ZONE_KITCHEN):
            windows = self._living_area_windows()
        else:
            windows = ()
        return ZoneInput(
            zone=zone,
            room_temperature=self._float_state(CONF_ZONE_TEMPERATURE.format(zone=zone)),
            room_humidity=self._float_state(CONF_ZONE_HUMIDITY.format(zone=zone)),
            thermostat_entity_id=self.config.get(CONF_ZONE_THERMOSTAT.format(zone=zone)),
            windows=windows,
            last_mode=self._zone_profile_state.get(zone),
        )

    def _apply_floor_slab_context(self, plan: ZonePlan, inp: BathroomClimateInput, slab: FloorSlabDeltaBreakdown) -> ZonePlan:
        delta = slab.current
        policy_target = plan.raw_target_temperature
        thermostat_target = thermostat_target_for(policy_target, plan.profile, delta)
        return replace(
            plan,
            target_temperature=thermostat_target,
            raw_target_temperature=policy_target,
            floor_slab_delta=delta,
            floor_slab_delta_source=slab.source,
            floor_slab_delta_quality=slab.quality,
            floor_slab_delta_reason=slab.reason,
            floor_slab_cold_index=slab.cold_index,
            room_comfort=evaluate_room_comfort(inp.room_temperature, inp.room_humidity, delta),
        )

    def _hysteresis_requirement(
        self,
        previous: str,
        candidate: str,
        teff: float | None,
        now: datetime,
        tuning: Any,
    ) -> tuple[bool, int, str] | None:
        if teff is None or previous not in HEAT_STRENGTH or candidate not in HEAT_STRENGTH:
            return None
        thresholds = threshold_for_month_config(now.month, tuning)
        off_threshold = float(thresholds["off"])
        comfort_threshold = thresholds["comfort"]
        boost_threshold = thresholds["boost"]

        if candidate == "off" and previous != "off":
            if teff < off_threshold + 1.5:
                return (False, 0, "hysteresis_wait_off_margin")
            return (True, 120 * 60, "hysteresis_wait_off_duration")
        if previous == "off" and candidate != "off":
            if teff > off_threshold - 0.5:
                return (False, 0, "hysteresis_wait_off_exit_margin")
            return (True, 45 * 60, "hysteresis_wait_off_exit_duration")

        previous_strength = HEAT_STRENGTH[previous]
        candidate_strength = HEAT_STRENGTH[candidate]
        if candidate_strength < previous_strength:
            if previous == "boost" and boost_threshold is not None and teff <= float(boost_threshold) + 0.8:
                return (False, 0, "hysteresis_wait_warmer_boost_margin")
            if previous == "komfort" and comfort_threshold is not None and teff <= float(comfort_threshold) + 0.8:
                return (False, 0, "hysteresis_wait_warmer_comfort_margin")
            return (True, 60 * 60, "hysteresis_wait_warmer_duration")
        if candidate_strength > previous_strength:
            if candidate == "boost" and boost_threshold is not None and teff > float(boost_threshold) - 0.8:
                return (False, 0, "hysteresis_wait_colder_boost_margin")
            if candidate == "komfort" and comfort_threshold is not None and teff > float(comfort_threshold) - 0.8:
                return (False, 0, "hysteresis_wait_colder_comfort_margin")
            return (True, 30 * 60, "hysteresis_wait_colder_duration")
        return None

    def _hold_hysteresis_plan(self, plan: ZonePlan, previous: str, reason: str, now: datetime, tuning: Any) -> ZonePlan:
        delta = plan.floor_slab_delta
        policy_target = setpoint_for(previous, plan.effective_outdoor_temperature, tuning)
        target = thermostat_target_for(policy_target, previous, delta)
        return replace(
            plan,
            profile=previous,  # type: ignore[arg-type]
            target_temperature=target,
            raw_target_temperature=policy_target,
            floor_slab_delta=delta,
            reason=reason,
            decision_path=[*plan.decision_path, reason],
            is_boost_active=previous == "boost",
            hysteresis_state=f"holding:{previous}->candidate:{plan.profile}",
            last_calculated=now.isoformat(),
        )

    def _apply_hysteresis(self, zone: str, plan: ZonePlan, now: datetime, tuning: Any) -> ZonePlan:
        previous = self._zone_profile_state.get(zone)
        if zone in HEATING_ZONES and previous == "boost" and threshold_for_month_config(now.month, tuning)["boost"] is None:
            self._zone_hysteresis_pending.pop(zone, None)
            return plan
        if previous is None or previous == plan.profile:
            self._zone_hysteresis_pending.pop(zone, None)
            return plan
        previous_reason = self._zone_profile_reason.get(zone)
        if plan.reason in IMMEDIATE_DECISION_REASONS or previous_reason in IMMEDIATE_DECISION_REASONS:
            self._zone_hysteresis_pending.pop(zone, None)
            return plan
        requirement = self._hysteresis_requirement(previous, plan.profile, plan.effective_outdoor_temperature, now, tuning)
        if requirement is None:
            self._zone_hysteresis_pending.pop(zone, None)
            return plan

        can_start_timer, required_seconds, reason = requirement
        if not can_start_timer:
            self._zone_hysteresis_pending.pop(zone, None)
            return self._hold_hysteresis_plan(plan, previous, reason, now, tuning)

        pending = self._zone_hysteresis_pending.get(zone)
        if pending is None or pending[0] != previous or pending[1] != plan.profile:
            self._zone_hysteresis_pending[zone] = (previous, plan.profile, now)
            return self._hold_hysteresis_plan(plan, previous, reason, now, tuning)
        if (now - pending[2]).total_seconds() < required_seconds:
            return self._hold_hysteresis_plan(plan, previous, reason, now, tuning)
        self._zone_hysteresis_pending.pop(zone, None)
        return plan

    def _boosted_plan(self, plan: ZonePlan, now: datetime, until: datetime, reason: str, tuning: Any) -> ZonePlan:
        delta = plan.floor_slab_delta
        policy_target = setpoint_for("boost", plan.effective_outdoor_temperature, tuning)
        target = thermostat_target_for(policy_target, "boost", delta)
        return replace(
            plan,
            profile="boost",
            target_temperature=target,
            raw_target_temperature=policy_target,
            floor_slab_delta=delta,
            reason=reason,
            decision_path=[*plan.decision_path, reason],
            is_boost_active=True,
            boost_until=until.isoformat(),
            hysteresis_state="boost_timer_active",
            last_calculated=now.isoformat(),
        )

    def _apply_stateful_boosts(
        self,
        plans: dict[str, ZonePlan],
        zone_inputs: dict[str, ZoneInput],
        context: Any,
        now: datetime,
        tuning: Any,
    ) -> None:
        if threshold_for_month_config(now.month, tuning)["boost"] is None:
            for zone_id in HEATING_ZONES:
                self._boost_until[zone_id] = None
                self._boost_reason[zone_id] = None
            return
        day_state = _state_value(context.day_state.value)
        bio = _state_value(context.bio_state.value)
        presence_band = _state_value(context.presence_band.value)
        pre_night_trigger = (
            day_state == "early_night"
            and self._last_day_state != "early_night"
            and bio == "awake"
            and presence_band in ("home", "near")
        )
        for zone_id in HEATING_ZONES:
            plan = plans[zone_id]
            if plan.profile == "off":
                self._boost_until[zone_id] = None
                self._boost_reason[zone_id] = None
                continue

            active_until = self._boost_until.get(zone_id)
            if active_until and active_until > now and plan.profile in ("komfort", "boost"):
                plans[zone_id] = self._boosted_plan(
                    plan,
                    now,
                    active_until,
                    self._boost_reason.get(zone_id) or "boost_timer_active",
                    tuning,
                )
                continue
            if active_until and active_until <= now:
                self._boost_until[zone_id] = None
                self._boost_reason[zone_id] = None
                active_until = None
            if plan.profile == "boost" and self._zone_profile_state.get(zone_id) == "boost" and active_until is None:
                delta = plan.floor_slab_delta
                policy_target = setpoint_for("komfort", plan.effective_outdoor_temperature, tuning)
                target = thermostat_target_for(policy_target, "komfort", delta)
                plans[zone_id] = replace(
                    plan,
                    profile="komfort",
                    target_temperature=target,
                    raw_target_temperature=policy_target,
                    floor_slab_delta=delta,
                    reason="boost_timer_elapsed_fallback_komfort",
                    decision_path=[*plan.decision_path, "boost_timer_elapsed_fallback_komfort"],
                    is_boost_active=False,
                    boost_until=None,
                    hysteresis_state="boost_timer_elapsed",
                    last_calculated=now.isoformat(),
                )
                continue

            start_reason: str | None = None
            duration = BOOST_STANDARD_DURATION
            teff = plan.effective_outdoor_temperature
            if pre_night_trigger and teff is not None and teff <= 5 and plan.profile in ("komfort", "boost"):
                start_reason = "pre_night_thermal_boost"
                duration = BOOST_PRE_NIGHT_DURATION
            elif plan.profile == "boost":
                start_reason = plan.reason
            elif self._zone_profile_state.get(zone_id) in ("off", "spar") and plan.profile == "komfort":
                room_temp = zone_inputs[zone_id].room_temperature
                comfort_target = setpoint_for("komfort", teff, tuning)
                if room_temp is not None and room_temp <= comfort_target - tuning.boost_activation_delta:
                    start_reason = "boost_transition_to_comfort_room_delta"

            if start_reason is None:
                continue
            until = now + duration
            self._boost_until[zone_id] = until
            self._boost_reason[zone_id] = start_reason
            plans[zone_id] = self._boosted_plan(plan, now, until, start_reason, tuning)

    def _commit_zone_profiles(self, plans: dict[str, ZonePlan]) -> None:
        for zone_id in (*HEATING_ZONES, ZONE_BATHROOM):
            plan = plans[zone_id]
            self._zone_profile_state[zone_id] = plan.profile
            self._zone_profile_reason[zone_id] = plan.reason

    def _bathroom_climate_input(self) -> BathroomClimateInput:
        return BathroomClimateInput(
            room_temperature=self._float_state(CONF_ZONE_TEMPERATURE.format(zone=ZONE_BATHROOM)),
            room_humidity=self._float_state(CONF_ZONE_HUMIDITY.format(zone=ZONE_BATHROOM)),
            thermostat_entity_id=self.config.get(CONF_ZONE_THERMOSTAT.format(zone=ZONE_BATHROOM)),
            last_mode=self._zone_profile_state.get(ZONE_BATHROOM),
        )

    def _bathroom_humidity_input(self) -> BathroomHumidityInput:
        now = dt_util.now()
        self._ensure_bath_fan_usage_hold_for_active_sources(now)
        bathroom_humidity = self._float_state(CONF_ZONE_HUMIDITY.format(zone=ZONE_BATHROOM))
        previous = self._last_bathroom_humidity_sample
        if bathroom_humidity is not None:
            self._last_bathroom_humidity_sample = (bathroom_humidity, now)
        return BathroomHumidityInput(
            bathroom_temperature=self._float_state(CONF_ZONE_TEMPERATURE.format(zone=ZONE_BATHROOM)),
            bathroom_humidity=bathroom_humidity,
            living_temperature=self._float_state(CONF_ZONE_TEMPERATURE.format(zone=ZONE_LIVING)),
            living_humidity=self._float_state(CONF_ZONE_HUMIDITY.format(zone=ZONE_LIVING)),
            fan_active_since=self._bath_fan_active_since(now),
            fan_active_since_uncertain=self._bath_fan_active_since_uncertain(),
            toilet_activity_active=self._state(CONF_BATH_TOILET_ACTIVITY) == "on",
            shower_activity_active=self._state(CONF_BATH_SHOWER_ACTIVITY) == "on",
            fan_usage_hold_active=self._bath_fan_usage_hold_active(now),
            fan_usage_hold_until=self._bath_fan_usage_hold_until,
            previous_bathroom_humidity=previous[0] if previous else None,
            previous_bathroom_humidity_at=previous[1] if previous else None,
            cap_deadline=self._bath_fan_cap_deadline,
            cooldown_until=self._bath_fan_cooldown_until,
        )

    async def async_set_apply_active(self, value: bool) -> None:
        self.hass.config_entries.async_update_entry(
            self.entry,
            options={**self.entry.options, CONF_APPLY_ACTIVE: bool(value)},
        )
        await self.async_evaluate(auto_apply=bool(value), reason="apply_active_changed")

    async def async_update_options(
        self,
        updates: dict[str, Any] | None = None,
        *,
        reset_keys: list[str] | tuple[str, ...] = (),
    ) -> None:
        new_options = validated_options_update(self.entry.options, updates or {}, reset_keys=reset_keys)
        self.hass.config_entries.async_update_entry(self.entry, options=new_options)
        await self.async_evaluate(auto_apply=False, reason="options_updated")

    async def async_apply(
        self,
        *,
        zone: str | None = None,
        manual: bool,
        dry_run: bool,
        refresh: bool = True,
    ) -> ApplyResult:
        apply_started = time.perf_counter()
        if refresh or self.decision is None:
            await self.async_evaluate(auto_apply=False, reason="apply_refresh_before_execute")
        decision = self.decision
        if decision is None:
            self.last_apply_result = ApplyResult("error", "no_decision", [])
            self.last_apply_duration_ms = round((time.perf_counter() - apply_started) * 1000, 2)
            self._notify()
            return self.last_apply_result

        selected = [zone] if zone else [*HEATING_ZONES, ZONE_BATHROOM, "bathroom_fan", "bathroom_diffuser"]
        now = dt_util.now()
        apply_specs = []
        switch_specs = []
        for zone_id in selected:
            if zone_id in ("bathroom_fan", "bathroom_diffuser"):
                if zone_id == "bathroom_fan":
                    plan = self.bathroom_fan_plan
                    target = self.config.get(CONF_BATH_FAN)
                else:
                    plan = self.bathroom_diffuser_plan
                    target = self.config.get(CONF_BATH_DIFFUSER)
                if plan is None:
                    continue
                target_state = self.hass.states.get(target).state if target and self.hass.states.get(target) else None
                gate = ApplyGateState(
                    apply_active=self.apply_active,
                    manual=manual,
                    dry_run=dry_run,
                    system_ready=self.system_ready,
                    startup_ready=self.startup_ready,
                    cooldown_seconds=self.cooldown_seconds,
                    now=now,
                    target_state=target_state,
                    last_applied_hash=self.last_applied_hash.get(zone_id),
                    last_apply_at=self.last_apply_at.get(zone_id),
                )
                switch_specs.append((plan, target, gate))
                continue
            plan = decision.zone(zone_id)
            if plan is None:
                continue
            target = self.config.get(CONF_ZONE_THERMOSTAT.format(zone=zone_id))
            target_state = self.hass.states.get(target).state if target and self.hass.states.get(target) else None
            gate = ApplyGateState(
                apply_active=self.apply_active,
                manual=manual,
                dry_run=dry_run,
                system_ready=self.system_ready,
                startup_ready=self.startup_ready,
                cooldown_seconds=self.cooldown_seconds,
                now=now,
                target_state=target_state,
                last_applied_hash=self.last_applied_hash.get(zone_id),
                last_apply_at=self.last_apply_at.get(zone_id),
            )
            apply_specs.append((plan, target, gate))

        result = await self.apply_engine.async_apply_many(apply_specs)
        switch_actions = [
            await self.apply_engine.async_apply_switch_plan(plan, target_entity_id=target, gate=gate)
            for plan, target, gate in switch_specs
        ]
        if switch_actions:
            actions = [*result.actions, *switch_actions]
            if any(a.status == "error" for a in actions):
                status = "error"
            elif any(a.status == "applied" for a in actions):
                status = "applied"
            elif all(a.status == "dry_run" for a in actions):
                status = "dry_run"
            elif any(a.status == "blocked" for a in actions):
                status = "blocked"
            else:
                status = "skipped"
            result = ApplyResult(status, status, actions, dry_run=all(a.status == "dry_run" for a in actions))
        result = replace(
            result,
            input_hash=decision.input_hash,
            plan_hashes={zone_id: plan.plan_hash for zone_id, plan in decision.zone_plans.items()},
        )
        if not dry_run:
            for action in result.actions:
                if action.zone == "bathroom_fan":
                    if self.bathroom_fan_plan:
                        self.bathroom_fan_plan = replace(
                            self.bathroom_fan_plan,
                            apply_status=action.status,
                            apply_block_reason=action.reason,
                        )
                    plan = self.bathroom_fan_plan
                elif action.zone == "bathroom_diffuser":
                    if self.bathroom_diffuser_plan:
                        self.bathroom_diffuser_plan = replace(
                            self.bathroom_diffuser_plan,
                            apply_status=action.status,
                            apply_block_reason=action.reason,
                        )
                    plan = self.bathroom_diffuser_plan
                else:
                    plan = decision.zone(action.zone)
                    if plan:
                        plan.apply_status = action.status
                        plan.apply_block_reason = action.reason
                if action.status == "applied":
                    self.last_applied_hash[action.zone] = action.plan_hash
                    self.last_apply_at[action.zone] = now
                    if action.zone == "bathroom_fan":
                        if self.bathroom_fan_plan and self.bathroom_fan_plan.target_switch_state == "on":
                            self.last_bath_fan_active_at = now
                    elif action.zone == "bathroom_diffuser":
                        pass
                    elif plan:
                        plan.last_applied = now.isoformat()
        self.last_apply_result = result
        self.last_apply_duration_ms = round((time.perf_counter() - apply_started) * 1000, 2)
        self._notify()
        return result

    def zone_plan(self, zone: str) -> ZonePlan | None:
        return self.decision.zone(zone) if self.decision else None

    def bathroom_debug(self) -> dict[str, Any]:
        return {
            "climate_plan": self.zone_plan(ZONE_BATHROOM).as_dict() if self.zone_plan(ZONE_BATHROOM) else None,
            "fan_plan": self.bathroom_fan_plan.as_dict() if self.bathroom_fan_plan else None,
            "diffuser_plan": self.bathroom_diffuser_plan.as_dict() if self.bathroom_diffuser_plan else None,
            "tuning": self.bath_tuning.as_dict(),
        }

    def debug_summary(self) -> str:
        if self.decision is None:
            return "not_calculated"
        modes = ",".join(f"{z}:{p.profile}" for z, p in self.decision.zone_plans.items())
        return f"ready={self.system_ready}; apply={self.apply_active}; {modes}"

    def debug_payload(self) -> dict[str, Any]:
        now = dt_util.now()
        effective_temperature = (
            self.decision.effective_temperature.effective_temperature
            if self.decision
            else None
        )
        thresholds = policy_visibility_snapshot(now.month, effective_temperature, self.policy_tuning)
        forecast_diag = self.weather_resolution.forecast.as_dict() if self.weather_resolution else {}
        samples = sorted(self.evaluate_duration_samples_ms)
        average_evaluate_ms = round(sum(samples) / len(samples), 2) if samples else None
        p95_evaluate_ms = samples[min(len(samples) - 1, int(len(samples) * 0.95))] if samples else None
        update_load = "ruhig"
        if self.last_evaluate_duration_ms is not None and self.last_evaluate_duration_ms > 1000:
            update_load = "auffällig"
        elif self.last_evaluate_duration_ms is not None and self.last_evaluate_duration_ms > 250:
            update_load = "normal"
        return {
            "integration_version": INTEGRATION_VERSION,
            "system_ready": self.system_ready,
            "apply_active": self.apply_active,
            "apply_ready": self.apply_ready,
            "manual_apply_possible": self.manual_apply_possible,
            "startup_ready": self.startup_ready,
            "startup_block_seconds": self.startup_block_seconds,
            "cooldown_seconds": self.cooldown_seconds,
            "thresholds": {
                **thresholds,
                "apply_cooldowns": {
                    "cooldown_seconds": self.cooldown_seconds,
                    "startup_block_seconds": self.startup_block_seconds,
                    "startup_ready": self.startup_ready,
                    "last_apply_at": {
                        zone: value.isoformat() if value else None
                        for zone, value in self.last_apply_at.items()
                    },
                },
            },
            "tuning_options": tuning_options_snapshot(self.entry.options),
            "last_applied_hash": dict(self.last_applied_hash),
            "last_apply_at": {
                zone: value.isoformat() if value else None
                for zone, value in self.last_apply_at.items()
            },
            "last_apply_result": self.last_apply_result.as_dict() if self.last_apply_result else None,
            "effective_inputs": self.effective_input_snapshot(),
            "bathroom": self.bathroom_debug(),
            "inputs": self.input_snapshot(),
            "performance": {
                "last_recalculate_at": self.last_recalculate_at.isoformat() if self.last_recalculate_at else None,
                "recalculate_count": self.recalculate_count,
                "last_recalculate_reason": self.last_recalculate_reason,
                "evaluate_debounce_seconds": EVALUATE_DEBOUNCE_SECONDS,
                "weather_forecast_cache_ttl_seconds": DEFAULT_FORECAST_CACHE_TTL_SECONDS,
                "weather_forecast_last_fetch_at": forecast_diag.get("last_fetch_at"),
                "weather_forecast_cache_age": forecast_diag.get("cache_age_seconds"),
                "weather_forecast_cache_hit": forecast_diag.get("cache_hit"),
                "entity_publish_skipped_count": self.entity_publish_skipped_count,
                "entity_publish_changed_count": self.entity_publish_changed_count,
                "last_evaluate_duration_ms": self.last_evaluate_duration_ms,
                "average_evaluate_duration_ms": average_evaluate_ms,
                "p95_evaluate_duration_ms": p95_evaluate_ms,
                "last_apply_duration_ms": self.last_apply_duration_ms,
                "last_forecast_duration_ms": self.last_forecast_duration_ms,
                "update_load": update_load,
            },
        }

