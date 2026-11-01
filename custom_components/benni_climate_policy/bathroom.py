"""Pure bathroom heating and fan policy."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
import hashlib
import json
import math
from typing import Any, Literal, Mapping

from .models import ClimateContextSnapshot, EffectiveTemperatureBreakdown, ZonePlan
from .policy import (
    FloorSlabDeltaBreakdown,
    PolicyTuning,
    floor_slab_delta_for_month_breakdown,
    indoor_heat_rule_for,
    no_heat_demand_reason,
)

BathFanMode = Literal["off", "akut", "nachluft", "stoss"]

BATH_SETPOINT_PROTECTION = 16.0
BATH_SETPOINT_GROUND = 22.0
BATH_SETPOINT_COMFORT = 23.0
BATH_SETPOINT_OFF = 10.0
BATH_OVER_TARGET_HYSTERESIS = 0.3
BATH_COMFORT_SUPPRESSION_TEFF = 18.0
BATH_BONUS_TEFF_0 = 0.5
BATH_BONUS_TEFF_5 = 0.3
BATH_BONUS_TEFF_WARM = -0.5
BATH_HUMIDITY_ACUTE_THRESHOLD = 75.0
BATH_HUMIDITY_ACUTE_RISE_THRESHOLD = 15.0
BATH_HUMIDITY_END_THRESHOLD = 60.0
BATH_DEWPOINT_ACUTE_THRESHOLD = 17.0
BATH_HUMIDITY_GROUND_HEAT_THRESHOLD = 68.0
BATH_DEWPOINT_GROUND_HEAT_THRESHOLD = 15.0
BATH_HUMIDITY_GROUND_HEAT_TEFF_LIMIT = 16.0
BATH_HUMIDITY_GROUND_HEAT_TARGET = BATH_SETPOINT_GROUND
BATH_HUMIDITY_GROUND_HEAT_OFF_AT = 22.5
BATH_AH_DELTA_AFTERRUN_ON = 1.5
BATH_AH_DELTA_AFTERRUN_OFF = 0.8
BATH_AH_DELTA_STOSS = 0.5
BATH_FAN_HEAT_COORDINATION_DELTA = 1.5
BATH_FAN_ACUTE_MAX_MINUTES = 45
BATH_FAN_AFTERRUN_MAX_MINUTES = 60
BATH_FAN_STOSS_INTERVAL_HOURS = 12
BATH_FAN_STOSS_DURATION_MINUTES = 10
# Hard rolling cap against 24/7 operation: the fan may run on humidity grounds for
# at most this long per run-window. Each genuine usage event (shower/toilet/usage
# hold) refills the window. Once exhausted without a fresh event the fan enters a
# cooldown lockout so it cannot immediately re-arm on persistent humidity.
BATH_FAN_HARD_CAP_MINUTES = 120
BATH_FAN_COOLDOWN_MINUTES = 120
# The aroma diffuser starts together with the fan but must end earlier (its own
# shorter cap), so the two start synchronously and end asynchronously.
BATH_DIFFUSER_MAX_MINUTES = 30

OPT_BATH_SETPOINT_PROTECTION = "bath_setpoint_protection"
OPT_BATH_SETPOINT_GROUND = "bath_setpoint_ground"
OPT_BATH_SETPOINT_COMFORT = "bath_setpoint_comfort"
OPT_BATH_COMFORT_SUPPRESSION_TEFF = "bath_comfort_suppression_teff"
OPT_BATH_BONUS_TEFF_0 = "bath_bonus_teff_0"
OPT_BATH_BONUS_TEFF_5 = "bath_bonus_teff_5"
OPT_BATH_BONUS_TEFF_WARM = "bath_bonus_teff_warm"
OPT_BATH_HUMIDITY_ACUTE_THRESHOLD = "bath_humidity_acute_threshold"
OPT_BATH_HUMIDITY_ACUTE_RISE_THRESHOLD = "bath_humidity_acute_rise_threshold"
OPT_BATH_HUMIDITY_END_THRESHOLD = "bath_humidity_end_threshold"
OPT_BATH_DEWPOINT_ACUTE_THRESHOLD = "bath_dewpoint_acute_threshold"
OPT_BATH_HUMIDITY_GROUND_HEAT_THRESHOLD = "bath_humidity_ground_heat_threshold"
OPT_BATH_DEWPOINT_GROUND_HEAT_THRESHOLD = "bath_dewpoint_ground_heat_threshold"
OPT_BATH_HUMIDITY_GROUND_HEAT_TEFF_LIMIT = "bath_humidity_ground_heat_teff_limit"
OPT_BATH_HUMIDITY_GROUND_HEAT_TARGET = "bath_humidity_ground_heat_target"
OPT_BATH_HUMIDITY_GROUND_HEAT_OFF_AT = "bath_humidity_ground_heat_off_at"
OPT_BATH_AH_DELTA_AFTERRUN_ON = "bath_ah_delta_afterrun_on"
OPT_BATH_AH_DELTA_AFTERRUN_OFF = "bath_ah_delta_afterrun_off"
OPT_BATH_AH_DELTA_STOSS = "bath_ah_delta_stoss"
OPT_BATH_FAN_HEAT_COORDINATION_DELTA = "bath_fan_heat_coordination_delta"
OPT_BATH_FAN_ACUTE_MAX_MINUTES = "bath_fan_acute_max_minutes"
OPT_BATH_FAN_AFTERRUN_MAX_MINUTES = "bath_fan_afterrun_max_minutes"
OPT_BATH_FAN_STOSS_INTERVAL_HOURS = "bath_fan_stoss_interval_hours"
OPT_BATH_FAN_STOSS_DURATION_MINUTES = "bath_fan_stoss_duration_minutes"
OPT_BATH_FAN_HARD_CAP_MINUTES = "bath_fan_hard_cap_minutes"
OPT_BATH_FAN_COOLDOWN_MINUTES = "bath_fan_cooldown_minutes"
OPT_BATH_DIFFUSER_MAX_MINUTES = "bath_diffuser_max_minutes"

BATH_OPTION_KEYS = (
    OPT_BATH_SETPOINT_PROTECTION,
    OPT_BATH_SETPOINT_GROUND,
    OPT_BATH_SETPOINT_COMFORT,
    OPT_BATH_COMFORT_SUPPRESSION_TEFF,
    OPT_BATH_BONUS_TEFF_0,
    OPT_BATH_BONUS_TEFF_5,
    OPT_BATH_BONUS_TEFF_WARM,
    OPT_BATH_HUMIDITY_ACUTE_THRESHOLD,
    OPT_BATH_HUMIDITY_ACUTE_RISE_THRESHOLD,
    OPT_BATH_HUMIDITY_END_THRESHOLD,
    OPT_BATH_DEWPOINT_ACUTE_THRESHOLD,
    OPT_BATH_HUMIDITY_GROUND_HEAT_THRESHOLD,
    OPT_BATH_DEWPOINT_GROUND_HEAT_THRESHOLD,
    OPT_BATH_HUMIDITY_GROUND_HEAT_TEFF_LIMIT,
    OPT_BATH_HUMIDITY_GROUND_HEAT_TARGET,
    OPT_BATH_HUMIDITY_GROUND_HEAT_OFF_AT,
    OPT_BATH_AH_DELTA_AFTERRUN_ON,
    OPT_BATH_AH_DELTA_AFTERRUN_OFF,
    OPT_BATH_AH_DELTA_STOSS,
    OPT_BATH_FAN_HEAT_COORDINATION_DELTA,
    OPT_BATH_FAN_ACUTE_MAX_MINUTES,
    OPT_BATH_FAN_AFTERRUN_MAX_MINUTES,
    OPT_BATH_FAN_STOSS_INTERVAL_HOURS,
    OPT_BATH_FAN_STOSS_DURATION_MINUTES,
    OPT_BATH_FAN_HARD_CAP_MINUTES,
    OPT_BATH_FAN_COOLDOWN_MINUTES,
    OPT_BATH_DIFFUSER_MAX_MINUTES,
)


def _float_option(
    options: Mapping[str, Any] | None,
    key: str,
    default: float,
    sources: dict[str, str],
    *,
    min_value: float | None = None,
    max_value: float | None = None,
) -> float:
    if options is None or key not in options:
        sources[key] = "default"
        return default
    try:
        value = float(options[key])
    except (TypeError, ValueError):
        sources[key] = "invalid_fallback_default"
        return default
    if min_value is not None and value < min_value:
        sources[key] = "invalid_fallback_default"
        return default
    if max_value is not None and value > max_value:
        sources[key] = "invalid_fallback_default"
        return default
    sources[key] = "user option"
    return value


def _int_option(
    options: Mapping[str, Any] | None,
    key: str,
    default: int,
    sources: dict[str, str],
    *,
    min_value: int = 1,
) -> int:
    value = _float_option(options, key, float(default), sources, min_value=float(min_value))
    return int(value)


@dataclass(frozen=True)
class BathTuning:
    setpoint_protection: float = BATH_SETPOINT_PROTECTION
    setpoint_ground: float = BATH_SETPOINT_GROUND
    setpoint_comfort: float = BATH_SETPOINT_COMFORT
    comfort_suppression_teff: float = BATH_COMFORT_SUPPRESSION_TEFF
    bonus_teff_0: float = BATH_BONUS_TEFF_0
    bonus_teff_5: float = BATH_BONUS_TEFF_5
    bonus_teff_warm: float = BATH_BONUS_TEFF_WARM
    humidity_acute_threshold: float = BATH_HUMIDITY_ACUTE_THRESHOLD
    humidity_acute_rise_threshold: float = BATH_HUMIDITY_ACUTE_RISE_THRESHOLD
    humidity_end_threshold: float = BATH_HUMIDITY_END_THRESHOLD
    dewpoint_acute_threshold: float = BATH_DEWPOINT_ACUTE_THRESHOLD
    humidity_ground_heat_threshold: float = BATH_HUMIDITY_GROUND_HEAT_THRESHOLD
    dewpoint_ground_heat_threshold: float = BATH_DEWPOINT_GROUND_HEAT_THRESHOLD
    humidity_ground_heat_teff_limit: float = BATH_HUMIDITY_GROUND_HEAT_TEFF_LIMIT
    humidity_ground_heat_target: float = BATH_HUMIDITY_GROUND_HEAT_TARGET
    humidity_ground_heat_off_at: float = BATH_HUMIDITY_GROUND_HEAT_OFF_AT
    ah_delta_afterrun_on: float = BATH_AH_DELTA_AFTERRUN_ON
    ah_delta_afterrun_off: float = BATH_AH_DELTA_AFTERRUN_OFF
    ah_delta_stoss: float = BATH_AH_DELTA_STOSS
    fan_heat_coordination_delta: float = BATH_FAN_HEAT_COORDINATION_DELTA
    fan_acute_max_minutes: int = BATH_FAN_ACUTE_MAX_MINUTES
    fan_afterrun_max_minutes: int = BATH_FAN_AFTERRUN_MAX_MINUTES
    fan_stoss_interval_hours: int = BATH_FAN_STOSS_INTERVAL_HOURS
    fan_stoss_duration_minutes: int = BATH_FAN_STOSS_DURATION_MINUTES
    fan_hard_cap_minutes: int = BATH_FAN_HARD_CAP_MINUTES
    fan_cooldown_minutes: int = BATH_FAN_COOLDOWN_MINUTES
    diffuser_max_minutes: int = BATH_DIFFUSER_MAX_MINUTES
    sources: dict[str, str] = field(default_factory=dict)

    @property
    def signature(self) -> str:
        payload = self.as_dict(include_sources=False)
        blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]

    def as_dict(self, *, include_sources: bool = True) -> dict[str, Any]:
        data: dict[str, Any] = {
            "setpoint_protection": self.setpoint_protection,
            "setpoint_ground": self.setpoint_ground,
            "setpoint_comfort": self.setpoint_comfort,
            "comfort_suppression_teff": self.comfort_suppression_teff,
            "bonus_teff_0": self.bonus_teff_0,
            "bonus_teff_5": self.bonus_teff_5,
            "bonus_teff_warm": self.bonus_teff_warm,
            "humidity_acute_threshold": self.humidity_acute_threshold,
            "humidity_acute_rise_threshold": self.humidity_acute_rise_threshold,
            "humidity_end_threshold": self.humidity_end_threshold,
            "dewpoint_acute_threshold": self.dewpoint_acute_threshold,
            "humidity_ground_heat_threshold": self.humidity_ground_heat_threshold,
            "dewpoint_ground_heat_threshold": self.dewpoint_ground_heat_threshold,
            "humidity_ground_heat_teff_limit": self.humidity_ground_heat_teff_limit,
            "humidity_ground_heat_target": self.humidity_ground_heat_target,
            "humidity_ground_heat_off_at": self.humidity_ground_heat_off_at,
            "ah_delta_afterrun_on": self.ah_delta_afterrun_on,
            "ah_delta_afterrun_off": self.ah_delta_afterrun_off,
            "ah_delta_stoss": self.ah_delta_stoss,
            "fan_heat_coordination_delta": self.fan_heat_coordination_delta,
            "fan_acute_max_minutes": self.fan_acute_max_minutes,
            "fan_afterrun_max_minutes": self.fan_afterrun_max_minutes,
            "fan_stoss_interval_hours": self.fan_stoss_interval_hours,
            "fan_stoss_duration_minutes": self.fan_stoss_duration_minutes,
            "fan_hard_cap_minutes": self.fan_hard_cap_minutes,
            "fan_cooldown_minutes": self.fan_cooldown_minutes,
            "diffuser_max_minutes": self.diffuser_max_minutes,
        }
        if include_sources:
            data["signature"] = self.signature
        if include_sources:
            data["sources"] = dict(self.sources)
        return data


def bath_tuning_from_options(options: Mapping[str, Any] | None) -> BathTuning:
    sources: dict[str, str] = {}
    return BathTuning(
        setpoint_protection=_float_option(options, OPT_BATH_SETPOINT_PROTECTION, BATH_SETPOINT_PROTECTION, sources, min_value=5, max_value=30),
        setpoint_ground=_float_option(options, OPT_BATH_SETPOINT_GROUND, BATH_SETPOINT_GROUND, sources, min_value=5, max_value=30),
        setpoint_comfort=_float_option(options, OPT_BATH_SETPOINT_COMFORT, BATH_SETPOINT_COMFORT, sources, min_value=5, max_value=30),
        comfort_suppression_teff=_float_option(options, OPT_BATH_COMFORT_SUPPRESSION_TEFF, BATH_COMFORT_SUPPRESSION_TEFF, sources, min_value=-30, max_value=35),
        bonus_teff_0=_float_option(options, OPT_BATH_BONUS_TEFF_0, BATH_BONUS_TEFF_0, sources, min_value=-5, max_value=5),
        bonus_teff_5=_float_option(options, OPT_BATH_BONUS_TEFF_5, BATH_BONUS_TEFF_5, sources, min_value=-5, max_value=5),
        bonus_teff_warm=_float_option(options, OPT_BATH_BONUS_TEFF_WARM, BATH_BONUS_TEFF_WARM, sources, min_value=-5, max_value=5),
        humidity_acute_threshold=_float_option(options, OPT_BATH_HUMIDITY_ACUTE_THRESHOLD, BATH_HUMIDITY_ACUTE_THRESHOLD, sources, min_value=0, max_value=100),
        humidity_acute_rise_threshold=_float_option(options, OPT_BATH_HUMIDITY_ACUTE_RISE_THRESHOLD, BATH_HUMIDITY_ACUTE_RISE_THRESHOLD, sources, min_value=0, max_value=100),
        humidity_end_threshold=_float_option(options, OPT_BATH_HUMIDITY_END_THRESHOLD, BATH_HUMIDITY_END_THRESHOLD, sources, min_value=0, max_value=100),
        dewpoint_acute_threshold=_float_option(options, OPT_BATH_DEWPOINT_ACUTE_THRESHOLD, BATH_DEWPOINT_ACUTE_THRESHOLD, sources, min_value=-20, max_value=40),
        humidity_ground_heat_threshold=_float_option(options, OPT_BATH_HUMIDITY_GROUND_HEAT_THRESHOLD, BATH_HUMIDITY_GROUND_HEAT_THRESHOLD, sources, min_value=0, max_value=100),
        dewpoint_ground_heat_threshold=_float_option(options, OPT_BATH_DEWPOINT_GROUND_HEAT_THRESHOLD, BATH_DEWPOINT_GROUND_HEAT_THRESHOLD, sources, min_value=-20, max_value=40),
        humidity_ground_heat_teff_limit=_float_option(options, OPT_BATH_HUMIDITY_GROUND_HEAT_TEFF_LIMIT, BATH_HUMIDITY_GROUND_HEAT_TEFF_LIMIT, sources, min_value=-30, max_value=35),
        humidity_ground_heat_target=_float_option(options, OPT_BATH_HUMIDITY_GROUND_HEAT_TARGET, BATH_HUMIDITY_GROUND_HEAT_TARGET, sources, min_value=5, max_value=30),
        humidity_ground_heat_off_at=_float_option(options, OPT_BATH_HUMIDITY_GROUND_HEAT_OFF_AT, BATH_HUMIDITY_GROUND_HEAT_OFF_AT, sources, min_value=5, max_value=30),
        ah_delta_afterrun_on=_float_option(options, OPT_BATH_AH_DELTA_AFTERRUN_ON, BATH_AH_DELTA_AFTERRUN_ON, sources, min_value=-10, max_value=30),
        ah_delta_afterrun_off=_float_option(options, OPT_BATH_AH_DELTA_AFTERRUN_OFF, BATH_AH_DELTA_AFTERRUN_OFF, sources, min_value=-10, max_value=30),
        ah_delta_stoss=_float_option(options, OPT_BATH_AH_DELTA_STOSS, BATH_AH_DELTA_STOSS, sources, min_value=-10, max_value=30),
        fan_heat_coordination_delta=_float_option(options, OPT_BATH_FAN_HEAT_COORDINATION_DELTA, BATH_FAN_HEAT_COORDINATION_DELTA, sources, min_value=0, max_value=10),
        fan_acute_max_minutes=_int_option(options, OPT_BATH_FAN_ACUTE_MAX_MINUTES, BATH_FAN_ACUTE_MAX_MINUTES, sources),
        fan_afterrun_max_minutes=_int_option(options, OPT_BATH_FAN_AFTERRUN_MAX_MINUTES, BATH_FAN_AFTERRUN_MAX_MINUTES, sources),
        fan_stoss_interval_hours=_int_option(options, OPT_BATH_FAN_STOSS_INTERVAL_HOURS, BATH_FAN_STOSS_INTERVAL_HOURS, sources),
        fan_stoss_duration_minutes=_int_option(options, OPT_BATH_FAN_STOSS_DURATION_MINUTES, BATH_FAN_STOSS_DURATION_MINUTES, sources),
        fan_hard_cap_minutes=_int_option(options, OPT_BATH_FAN_HARD_CAP_MINUTES, BATH_FAN_HARD_CAP_MINUTES, sources),
        fan_cooldown_minutes=_int_option(options, OPT_BATH_FAN_COOLDOWN_MINUTES, BATH_FAN_COOLDOWN_MINUTES, sources),
        diffuser_max_minutes=_int_option(options, OPT_BATH_DIFFUSER_MAX_MINUTES, BATH_DIFFUSER_MAX_MINUTES, sources),
        sources=sources,
    )


@dataclass(frozen=True)
class BathroomClimateInput:
    room_temperature: float | None
    room_humidity: float | None
    thermostat_entity_id: str | None
    last_mode: str | None = None


@dataclass(frozen=True)
class BathroomHumidityInput:
    bathroom_temperature: float | None
    bathroom_humidity: float | None
    living_temperature: float | None
    living_humidity: float | None
    fan_active_since: datetime | None = None
    fan_active_since_uncertain: bool = False
    toilet_activity_active: bool = False
    shower_activity_active: bool = False
    fan_usage_hold_active: bool = False
    fan_usage_hold_until: datetime | None = None
    previous_bathroom_humidity: float | None = None
    previous_bathroom_humidity_at: datetime | None = None
    # Rolling hard-cap state carried over from the previous evaluation.
    cap_deadline: datetime | None = None
    cooldown_until: datetime | None = None


@dataclass(frozen=True)
class BathroomFanPlan:
    zone: str
    mode: BathFanMode
    reason: str
    target_switch_state: str
    blocked_by: list[str] = field(default_factory=list)
    diagnostics: dict[str, Any] = field(default_factory=dict)
    policy_config_hash: str | None = None
    last_calculated: str | None = None
    apply_status: str = "pending"
    apply_block_reason: str = "none"
    # Rolling hard-cap state to persist for the next evaluation.
    cap_deadline: datetime | None = None
    cooldown_until: datetime | None = None

    @property
    def plan_hash(self) -> str:
        payload = {
            "mode": self.mode,
            "target_switch_state": self.target_switch_state,
            "reason": self.reason,
            "blocked_by": sorted(self.blocked_by),
            "policy_config_hash": self.policy_config_hash,
            "diagnostics": {
                "ah_delta": self.diagnostics.get("ah_delta"),
                "dewpoint": self.diagnostics.get("dewpoint"),
                "toilet_activity_active": self.diagnostics.get("toilet_activity_active"),
                "shower_activity_active": self.diagnostics.get("shower_activity_active"),
                "fan_usage_hold_active": self.diagnostics.get("fan_usage_hold_active"),
                "fan_usage_hold_until": self.diagnostics.get("fan_usage_hold_until"),
                "fan_max_duration_reached": self.diagnostics.get("fan_max_duration_reached"),
                "heating_fan_coordination_state": self.diagnostics.get("heating_fan_coordination_state"),
            },
        }
        blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]

    @property
    def apply_blocked(self) -> bool:
        return bool(self.blocked_by)

    def as_dict(self) -> dict[str, Any]:
        return {
            "zone": self.zone,
            "mode": self.mode,
            "reason": self.reason,
            "target_switch_state": self.target_switch_state,
            "blocked_by": list(self.blocked_by),
            "diagnostics": dict(self.diagnostics),
            "fan_reason": self.reason,
            "fan_blocker": ", ".join(self.blocked_by) if self.blocked_by else "none",
            "policy_config_hash": self.policy_config_hash,
            "last_calculated": self.last_calculated,
            "apply_status": self.apply_status,
            "apply_block_reason": self.apply_block_reason,
            "plan_hash": self.plan_hash,
        }


def dew_point_celsius(temperature: float, relative_humidity: float) -> float:
    humidity = max(0.1, min(100.0, relative_humidity))
    a = 17.62
    b = 243.12
    gamma = math.log(humidity / 100.0) + (a * temperature) / (b + temperature)
    return round((b * gamma) / (a - gamma), 2)


def absolute_humidity_gm3(temperature: float, relative_humidity: float) -> float:
    humidity = max(0.0, min(100.0, relative_humidity))
    saturation = 6.112 * math.exp((17.67 * temperature) / (temperature + 243.5))
    vapor_pressure = humidity / 100.0 * saturation
    return round(216.7 * vapor_pressure / (temperature + 273.15), 2)


def humidity_diagnostics(inp: BathroomHumidityInput) -> dict[str, Any]:
    out: dict[str, Any] = {
        "bathroom_temperature": inp.bathroom_temperature,
        "bathroom_humidity": inp.bathroom_humidity,
        "living_temperature": inp.living_temperature,
        "living_humidity": inp.living_humidity,
        "toilet_activity_active": inp.toilet_activity_active,
        "shower_activity_active": inp.shower_activity_active,
        "fan_usage_hold_active": inp.fan_usage_hold_active,
        "fan_usage_hold_until": inp.fan_usage_hold_until.isoformat() if inp.fan_usage_hold_until else None,
        "fan_active_since": inp.fan_active_since.isoformat() if inp.fan_active_since else None,
        "fan_active_since_uncertain": inp.fan_active_since_uncertain,
        "previous_bathroom_humidity": inp.previous_bathroom_humidity,
        "previous_bathroom_humidity_at": inp.previous_bathroom_humidity_at.isoformat() if inp.previous_bathroom_humidity_at else None,
        "bathroom_humidity_rise_5m": None,
        "fan_active_duration_minutes": None,
        "dewpoint": None,
        "absolute_humidity_bathroom": None,
        "absolute_humidity_living": None,
        "ah_delta": None,
        "input_quality": "missing",
    }
    if inp.bathroom_temperature is None or inp.bathroom_humidity is None:
        return out
    if inp.previous_bathroom_humidity is not None:
        out["bathroom_humidity_rise_5m"] = round(inp.bathroom_humidity - inp.previous_bathroom_humidity, 2)
    out["dewpoint"] = dew_point_celsius(inp.bathroom_temperature, inp.bathroom_humidity)
    out["absolute_humidity_bathroom"] = absolute_humidity_gm3(inp.bathroom_temperature, inp.bathroom_humidity)
    if inp.living_temperature is not None and inp.living_humidity is not None:
        out["absolute_humidity_living"] = absolute_humidity_gm3(inp.living_temperature, inp.living_humidity)
        out["ah_delta"] = round(out["absolute_humidity_bathroom"] - out["absolute_humidity_living"], 2)
        out["input_quality"] = "ok"
    else:
        out["input_quality"] = "degraded"
    return out


def _ctx_value(ctx: ClimateContextSnapshot, field_name: str) -> str | None:
    value = getattr(ctx, field_name).value
    if value in (None, "", "unknown", "unavailable"):
        return None
    return str(value)


def bath_outdoor_bonus(teff: float | None, tuning: BathTuning) -> float:
    if teff is None:
        return 0.0
    if teff <= 0:
        return tuning.bonus_teff_0
    if teff <= 5:
        return tuning.bonus_teff_5
    if teff > 15:
        return tuning.bonus_teff_warm
    return 0.0


def bath_humidity_ground_heat_active(
    inp: BathroomClimateInput,
    teff: float | None,
    tuning: BathTuning,
    *,
    drying_active: bool = False,
) -> bool:
    if teff is None or teff > tuning.humidity_ground_heat_teff_limit:
        return False
    # When the fan is in its humidity cooldown lockout (or venting cannot help),
    # warmth is the only remaining drying lever, so in cool weather we engage
    # ground heat regardless of the standalone humidity/dewpoint thresholds.
    if drying_active:
        return True
    humidity = inp.room_humidity
    if humidity is None:
        return False
    if humidity >= tuning.humidity_ground_heat_threshold:
        return True
    if inp.room_temperature is None:
        return False
    return dew_point_celsius(inp.room_temperature, humidity) >= tuning.dewpoint_ground_heat_threshold


def decide_bathroom_climate(
    inp: BathroomClimateInput,
    ctx: ClimateContextSnapshot,
    effective: EffectiveTemperatureBreakdown,
    now: datetime,
    tuning: BathTuning,
    *,
    indoor_tuning: PolicyTuning | None = None,
    floor_slab_delta: FloorSlabDeltaBreakdown | None = None,
    fan_drying_active: bool = False,
) -> ZonePlan:
    blockers: list[str] = []
    path: list[str] = []
    teff = effective.effective_temperature
    day_state = _ctx_value(ctx, "day_state")
    workday = (_ctx_value(ctx, "workday_state") or _ctx_value(ctx, "day_context") or "").lower()
    is_workday = workday in ("werktag", "workday", "working_day", "on")
    is_free = workday in ("wochenende", "weekend", "frei", "feiertag", "free", "holiday", "off")

    profile: Literal["off", "protection", "grundwaerme", "komfort"] = "grundwaerme"
    reason = "bath_ground_heat_default"
    target = tuning.setpoint_ground

    if not inp.thermostat_entity_id:
        blockers.append("thermostat_entity_missing")
    if teff is None:
        profile = "protection"
        target = tuning.setpoint_protection
        reason = "effective_temperature_missing_protection"
        path.append(reason)
    else:
        comfort_phase = (
            (is_workday and day_state == "early_morning")
            or (is_free and day_state == "forenoon")
            or day_state == "late_evening"
        )
        if comfort_phase and teff <= tuning.comfort_suppression_teff:
            bonus = bath_outdoor_bonus(teff, tuning)
            profile = "komfort"
            target = round(tuning.setpoint_comfort + bonus, 2)
            reason = "bath_comfort_phase_and_teff"
            path.append(reason)
        else:
            path.append(reason)

    allowed_profile = profile
    allowed_reason = reason
    heat_demand: bool | None = False if profile == "off" else None
    indoor_reason: str | None = "candidate_profile_off" if profile == "off" else None
    indoor_rule = indoor_heat_rule_for("bathroom", profile, indoor_tuning) if profile != "protection" else None
    humidity_ground_heat = profile == "grundwaerme" and bath_humidity_ground_heat_active(
        inp, teff, tuning, drying_active=fan_drying_active
    )
    indoor_heat_off_at = indoor_rule.heat_off_at if indoor_rule else None
    if humidity_ground_heat:
        target = max(target, tuning.humidity_ground_heat_target)
        reason = "bath_cooldown_drying_heat" if fan_drying_active else "bath_humidity_ground_heat"
        path.append(reason)
        indoor_heat_off_at = max(indoor_heat_off_at or tuning.humidity_ground_heat_off_at, tuning.humidity_ground_heat_off_at)
    if profile != "protection" and indoor_rule is not None:
        if inp.room_temperature is None:
            heat_demand = True
            indoor_reason = "room_temperature_missing_allows_candidate"
        elif indoor_heat_off_at is not None and inp.room_temperature >= indoor_heat_off_at:
            profile = "off"
            target = BATH_SETPOINT_OFF
            reason = no_heat_demand_reason("bathroom")
            path.append(reason)
            heat_demand = False
            indoor_reason = "room_temperature_above_heat_off_at"
        elif inp.room_temperature < indoor_rule.heat_on_below:
            heat_demand = True
            indoor_reason = "room_temperature_below_heat_on_below"
        elif humidity_ground_heat:
            heat_demand = True
            indoor_reason = "bath_humidity_ground_heat_overrides_indoor_hysteresis"
        elif inp.last_mode == "off":
            profile = "off"
            target = BATH_SETPOINT_OFF
            reason = "no_heat_demand"
            path.append(reason)
            heat_demand = False
            indoor_reason = "indoor_hysteresis_holds_off"
        else:
            heat_demand = True
            indoor_reason = "indoor_hysteresis_holds_heat" if inp.last_mode in ("grundwaerme", "komfort") else "indoor_hysteresis_initial_allows_heat"
    elif (
        inp.room_temperature is not None
        and profile != "protection"
        and inp.room_temperature >= target + BATH_OVER_TARGET_HYSTERESIS
    ):
        profile = "off"
        target = BATH_SETPOINT_OFF
        reason = "bath_over_target_forces_off"
        path.append(reason)
        heat_demand = False
        indoor_reason = "legacy_bath_over_target_hysteresis"

    slab = floor_slab_delta or floor_slab_delta_for_month_breakdown(now.month, indoor_tuning)

    return ZonePlan(
        zone="bathroom",
        profile=profile,  # type: ignore[arg-type]
        target_temperature=target,
        raw_target_temperature=target,
        reason=reason,
        decision_path=path,
        blocked_by=blockers,
        input_quality="ok" if teff is not None else "degraded",
        effective_outdoor_temperature=teff,
        floor_slab_delta=slab.current,
        floor_slab_delta_source=slab.source,
        floor_slab_delta_quality=slab.quality,
        floor_slab_delta_reason=slab.reason,
        floor_slab_cold_index=slab.cold_index,
        hysteresis_state=profile,
        allowed_profile=allowed_profile,
        allowed_reason=allowed_reason,
        heat_demand=heat_demand,
        indoor_heat_demand_reason=indoor_reason,
        indoor_heat_on_below=indoor_rule.heat_on_below if indoor_rule else None,
        indoor_heat_off_at=indoor_heat_off_at,
        indoor_min_hold_minutes=indoor_rule.min_hold_minutes if indoor_rule else None,
        last_calculated=now.isoformat(),
        apply_block_reason=", ".join(blockers) if blockers else "none",
        policy_config_hash=f"{tuning.signature}:{indoor_tuning.signature if indoor_tuning else 'default'}",
    )


def _apply_fan_hard_cap(
    mode: BathFanMode,
    reason: str,
    *,
    now: datetime,
    event_protected: bool,
    humidity_wants_on: bool,
    cap_deadline: datetime | None,
    cooldown_until: datetime | None,
    hard_cap_minutes: int,
    cooldown_minutes: int,
) -> tuple[BathFanMode, str, datetime | None, datetime | None, str]:
    """Enforce a rolling hard cap with cooldown lockout against 24/7 running.

    The cap tracks the *uncapped* humidity demand (``humidity_wants_on``) so the
    short off gaps from the per-mode duration caps do not reset the budget.
    Genuine usage events refill a fresh window and clear any cooldown.
    """
    hard_cap = timedelta(minutes=hard_cap_minutes)
    cooldown = timedelta(minutes=cooldown_minutes)

    if event_protected:
        return mode, reason, now + hard_cap, None, "event_refill"

    if cooldown_until is not None and now < cooldown_until:
        if mode in ("akut", "nachluft", "stoss"):
            return "off", "bath_fan_cooldown_lockout", None, cooldown_until, "cooldown_lockout"
        return mode, reason, None, cooldown_until, "cooldown_idle"

    if not humidity_wants_on:
        return mode, reason, None, None, "idle"

    if cap_deadline is None:
        return mode, reason, now + hard_cap, None, "budget_started"
    if now >= cap_deadline:
        return "off", "bath_fan_hard_cap_reached", None, now + cooldown, "hard_cap_reached"
    return mode, reason, cap_deadline, None, "within_budget"


def decide_bathroom_fan(
    humidity_input: BathroomHumidityInput,
    heating_plan: ZonePlan,
    *,
    now: datetime,
    day_state: str | None,
    last_fan_active_at: datetime | None,
    tuning: BathTuning,
) -> BathroomFanPlan:
    diagnostics = humidity_diagnostics(humidity_input)
    fan_active_duration_minutes = (
        round(max(0.0, (now - humidity_input.fan_active_since).total_seconds() / 60), 2)
        if humidity_input.fan_active_since is not None
        else None
    )
    humidity = humidity_input.bathroom_humidity
    dewpoint = diagnostics["dewpoint"]
    ah_delta = diagnostics["ah_delta"]
    humidity_rise = diagnostics["bathroom_humidity_rise_5m"]
    humidity_rise_recent = (
        humidity_rise is not None
        and humidity_input.previous_bathroom_humidity_at is not None
        and now - humidity_input.previous_bathroom_humidity_at <= timedelta(minutes=5)
    )
    mode: BathFanMode = "off"
    reason = "bath_fan_no_need"
    blockers: list[str] = []
    toilet_activity = humidity_input.toilet_activity_active
    shower_activity = humidity_input.shower_activity_active
    usage_hold = humidity_input.fan_usage_hold_active or toilet_activity or shower_activity
    usage_hold_protected = humidity_input.fan_usage_hold_active or toilet_activity

    humidity_acute_raw = (
        (humidity_rise_recent and humidity_rise > tuning.humidity_acute_rise_threshold)
        or
        (humidity is not None and humidity > tuning.humidity_acute_threshold)
        or (dewpoint is not None and dewpoint > tuning.dewpoint_acute_threshold)
    )
    # Venting only lowers bathroom moisture when bathroom air is more humid than the
    # air the fan pulls in (living). When ah_delta <= 0 (e.g. humid summer weather)
    # running the fan is counterproductive, so humidity-only acute must not fire.
    # ah_delta is None means living data is missing — keep the prior best-effort
    # behaviour and allow acute rather than going dark.
    venting_helps = ah_delta is None or ah_delta > 0
    acute = humidity_acute_raw and venting_helps
    acute_venting_unhelpful = humidity_acute_raw and not venting_helps
    if shower_activity:
        mode = "akut"
        reason = "bath_fan_shower_activity_hold"
    elif usage_hold:
        mode = "stoss"
        reason = "bath_fan_usage_hold"
    elif acute:
        mode = "akut"
        reason = "bath_fan_acute_humidity_rise_or_threshold"
    elif acute_venting_unhelpful:
        reason = "bath_fan_acute_venting_unhelpful"
    elif ah_delta is None:
        reason = "bath_fan_missing_humidity_delta"
        blockers.append("humidity_delta_missing")
    elif ah_delta > tuning.ah_delta_afterrun_on:
        mode = "nachluft"
        reason = "bath_fan_afterrun_ah_delta"
    elif ah_delta < tuning.ah_delta_afterrun_off:
        reason = "bath_fan_afterrun_end_threshold"
    elif (
        ah_delta > tuning.ah_delta_stoss
        and day_state not in ("early_night", "late_night")
        and last_fan_active_at is not None
        and now - last_fan_active_at > timedelta(hours=tuning.fan_stoss_interval_hours)
    ):
        mode = "stoss"
        reason = "bath_fan_stoss_due"
    elif ah_delta > tuning.ah_delta_stoss and last_fan_active_at is None:
        reason = "bath_fan_stoss_history_not_available"
    elif day_state in ("early_night", "late_night"):
        reason = "bath_fan_stoss_blocked_by_night"

    uncapped_mode = mode
    uncapped_reason = reason
    max_duration_minutes = {
        "akut": tuning.fan_acute_max_minutes,
        "nachluft": tuning.fan_afterrun_max_minutes,
        "stoss": tuning.fan_stoss_duration_minutes,
    }.get(mode)
    known_duration_reached = (
        max_duration_minutes is not None
        and fan_active_duration_minutes is not None
        and fan_active_duration_minutes >= max_duration_minutes
    )
    unknown_startup_duration_reached = (
        max_duration_minutes is not None
        and humidity_input.fan_active_since_uncertain
    )
    max_duration_reached = (
        (known_duration_reached or unknown_startup_duration_reached)
        and not usage_hold_protected
    )
    if max_duration_reached:
        mode = "off"
        if humidity_input.fan_active_since_uncertain:
            reason = f"bath_fan_{uncapped_mode}_active_since_unknown_at_startup"
        else:
            reason = f"bath_fan_{uncapped_mode}_max_duration_reached"

    strongly_heating = (
        humidity_input.bathroom_temperature is not None
        and humidity_input.bathroom_temperature < heating_plan.target_temperature - tuning.fan_heat_coordination_delta
    )
    if strongly_heating and mode in ("nachluft", "stoss") and not usage_hold:
        blockers.append("bath_heating_up_blocks_fan")
        mode = "off"
        reason = "bath_fan_blocked_by_heating_coordination"

    humidity_wants_on = uncapped_mode in ("akut", "nachluft", "stoss")
    mode, reason, next_cap_deadline, next_cooldown_until, hard_cap_state = _apply_fan_hard_cap(
        mode,
        reason,
        now=now,
        event_protected=usage_hold,
        humidity_wants_on=humidity_wants_on,
        cap_deadline=humidity_input.cap_deadline,
        cooldown_until=humidity_input.cooldown_until,
        hard_cap_minutes=tuning.fan_hard_cap_minutes,
        cooldown_minutes=tuning.fan_cooldown_minutes,
    )
    in_cooldown_lockout = hard_cap_state in ("cooldown_lockout", "hard_cap_reached")
    # Warmth is the drying lever when venting is pointless (negative ah_delta) or
    # the fan is locked out in cooldown while humidity persists.
    drying_recommended = humidity_acute_raw and (acute_venting_unhelpful or in_cooldown_lockout)
    coordination = (
        "max_duration_reached"
        if max_duration_reached
        else "shower_activity_overrides_heating"
        if shower_activity
        else "acute_overrides_heating"
        if acute
        else "usage_hold_overrides_heating"
        if usage_hold
        else "heating_up"
        if strongly_heating
        else "clear"
    )

    diagnostics.update({
        "heating_fan_coordination_state": coordination,
        "strongly_heating": strongly_heating,
        "fan_active_duration_minutes": fan_active_duration_minutes,
        "fan_active_since": humidity_input.fan_active_since.isoformat() if humidity_input.fan_active_since else None,
        "fan_active_since_uncertain": humidity_input.fan_active_since_uncertain,
        "fan_max_duration_reached": max_duration_reached,
        "fan_uncapped_mode": uncapped_mode,
        "fan_uncapped_reason": uncapped_reason,
        "max_duration_minutes": {
            "akut": tuning.fan_acute_max_minutes,
            "nachluft": tuning.fan_afterrun_max_minutes,
            "stoss": tuning.fan_stoss_duration_minutes,
        },
        "stoss_interval_hours": tuning.fan_stoss_interval_hours,
        "last_fan_active_at": last_fan_active_at.isoformat() if last_fan_active_at else None,
        "hard_cap_state": hard_cap_state,
        "hard_cap_minutes": tuning.fan_hard_cap_minutes,
        "cooldown_minutes": tuning.fan_cooldown_minutes,
        "cap_deadline": next_cap_deadline.isoformat() if next_cap_deadline else None,
        "cooldown_until": next_cooldown_until.isoformat() if next_cooldown_until else None,
        "drying_recommended": drying_recommended,
    })
    return BathroomFanPlan(
        zone="bathroom_fan",
        mode=mode,
        reason=reason,
        target_switch_state="on" if mode in ("akut", "nachluft", "stoss") else "off",
        blocked_by=blockers,
        diagnostics=diagnostics,
        policy_config_hash=tuning.signature,
        last_calculated=now.isoformat(),
        apply_block_reason=", ".join(blockers) if blockers else "none",
        cap_deadline=next_cap_deadline,
        cooldown_until=next_cooldown_until,
    )


@dataclass(frozen=True)
class BathroomDiffuserPlan:
    zone: str
    mode: str  # "on" | "off"
    reason: str
    target_switch_state: str
    blocked_by: list[str] = field(default_factory=list)
    diagnostics: dict[str, Any] = field(default_factory=dict)
    policy_config_hash: str | None = None
    last_calculated: str | None = None
    apply_status: str = "pending"
    apply_block_reason: str = "none"
    # When the current diffuser run-window started (tied to the fan run).
    run_started_at: datetime | None = None

    @property
    def plan_hash(self) -> str:
        payload = {
            "mode": self.mode,
            "target_switch_state": self.target_switch_state,
            "reason": self.reason,
            "blocked_by": sorted(self.blocked_by),
            "policy_config_hash": self.policy_config_hash,
            "diagnostics": {
                "fan_target_state": self.diagnostics.get("fan_target_state"),
                "run_duration_minutes": self.diagnostics.get("run_duration_minutes"),
                "max_duration_minutes": self.diagnostics.get("max_duration_minutes"),
            },
        }
        blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]

    @property
    def apply_blocked(self) -> bool:
        return bool(self.blocked_by)

    def as_dict(self) -> dict[str, Any]:
        return {
            "zone": self.zone,
            "mode": self.mode,
            "reason": self.reason,
            "target_switch_state": self.target_switch_state,
            "blocked_by": list(self.blocked_by),
            "diagnostics": dict(self.diagnostics),
            "policy_config_hash": self.policy_config_hash,
            "last_calculated": self.last_calculated,
            "apply_status": self.apply_status,
            "apply_block_reason": self.apply_block_reason,
            "plan_hash": self.plan_hash,
        }


def decide_bathroom_diffuser(
    fan_plan: BathroomFanPlan,
    *,
    run_started_at: datetime | None,
    now: datetime,
    tuning: BathTuning,
) -> BathroomDiffuserPlan:
    """Aroma diffuser follows the fan on, but ends after its own shorter cap.

    Starts synchronously with the fan; once the diffuser cap is reached it turns
    off while the fan may keep running (asynchronous end). It only restarts after
    the fan has cycled off and on again (``run_started_at`` is cleared on fan off).
    """
    max_minutes = tuning.diffuser_max_minutes
    fan_on = fan_plan.target_switch_state == "on"
    diagnostics: dict[str, Any] = {
        "fan_target_state": fan_plan.target_switch_state,
        "max_duration_minutes": max_minutes,
    }

    if not fan_on:
        diagnostics["run_duration_minutes"] = None
        return BathroomDiffuserPlan(
            zone="bathroom_diffuser",
            mode="off",
            reason="bath_diffuser_fan_off",
            target_switch_state="off",
            diagnostics=diagnostics,
            policy_config_hash=tuning.signature,
            last_calculated=now.isoformat(),
            run_started_at=None,
        )

    if run_started_at is None:
        diagnostics["run_duration_minutes"] = 0.0
        return BathroomDiffuserPlan(
            zone="bathroom_diffuser",
            mode="on",
            reason="bath_diffuser_follows_fan",
            target_switch_state="on",
            diagnostics=diagnostics,
            policy_config_hash=tuning.signature,
            last_calculated=now.isoformat(),
            run_started_at=now,
        )

    duration = round(max(0.0, (now - run_started_at).total_seconds() / 60), 2)
    diagnostics["run_duration_minutes"] = duration
    if duration >= max_minutes:
        return BathroomDiffuserPlan(
            zone="bathroom_diffuser",
            mode="off",
            reason="bath_diffuser_max_duration_reached",
            target_switch_state="off",
            diagnostics=diagnostics,
            policy_config_hash=tuning.signature,
            last_calculated=now.isoformat(),
            run_started_at=run_started_at,
        )
    return BathroomDiffuserPlan(
        zone="bathroom_diffuser",
        mode="on",
        reason="bath_diffuser_follows_fan",
        target_switch_state="on",
        diagnostics=diagnostics,
        policy_config_hash=tuning.signature,
        last_calculated=now.isoformat(),
        run_started_at=run_started_at,
    )
