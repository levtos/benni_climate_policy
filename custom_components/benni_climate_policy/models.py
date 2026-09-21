"""Pure data models for the climate policy."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import json
from typing import Any, Literal

Quality = Literal["ok", "degraded", "fallback", "missing", "unknown"]
ClimateMode = Literal["off", "spar", "komfort", "boost", "grundwaerme", "protection"]
ApplyStatus = Literal["applied", "blocked", "skipped", "dry_run", "error"]


@dataclass(frozen=True)
class SourceValue:
    value: Any
    source_entity_id: str | None
    quality: Quality = "unknown"
    fallback_used: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "source_entity_id": self.source_entity_id,
            "quality": self.quality,
            "fallback_used": self.fallback_used,
        }


@dataclass(frozen=True)
class ClimateContextSnapshot:
    activity_state: SourceValue
    bio_state: SourceValue
    day_context: SourceValue
    day_state: SourceValue
    presence_band: SourceValue
    presence_household: SourceValue
    presence_personal: SourceValue
    presence_preheat_active: SourceValue
    presence_transition: SourceValue
    workday_state: SourceValue
    planned_wakeup_time: SourceValue

    def as_dict(self) -> dict[str, Any]:
        return {name: getattr(self, name).as_dict() for name in self.__dataclass_fields__}


@dataclass(frozen=True)
class EffectiveTemperatureInput:
    real_temperature: float | None
    feels_like_temperature: float | None = None
    forecast_temperature: float | None = None
    weather_condition: str | None = None
    outdoor_lux: float | None = None
    sun_elevation: float | None = None
    month: int = 1


@dataclass(frozen=True)
class EffectiveTemperatureBreakdown:
    real_temperature: float | None
    floor_slab_offset: float
    feels_like_offset: float
    weather_offset: float
    forecast_offset: float
    lux_bonus: float
    effective_temperature: float | None
    input_quality: Quality

    def as_dict(self) -> dict[str, Any]:
        return {
            "real_temperature": self.real_temperature,
            "floor_slab_offset": self.floor_slab_offset,
            "feels_like_offset": self.feels_like_offset,
            "weather_offset": self.weather_offset,
            "forecast_offset": self.forecast_offset,
            "lux_bonus": self.lux_bonus,
            "effective_temperature": self.effective_temperature,
            "input_quality": self.input_quality,
        }


@dataclass(frozen=True)
class WindowState:
    open_state: str | None = None
    tilt_state: str | None = None

    @property
    def open_blocks(self) -> bool:
        return self.open_state not in ("off", "closed", "false", "False", False)

    @property
    def tilt_blocks(self) -> bool:
        return self.tilt_state in ("on", "open", "true", "True", True)

    @property
    def blocks_heating(self) -> bool:
        return self.open_blocks or self.tilt_blocks


def window_state_from_master_value(value: Any) -> WindowState:
    """Translate one openings-master value into a fail-safe window state."""
    text = "" if value is None else str(value).strip().lower()
    if text in ("", "unknown", "unavailable", "stale"):
        return WindowState("unknown", "off")
    return WindowState(
        "on" if text == "open" else "off",
        "on" if text == "tilted" else "off",
    )


@dataclass(frozen=True)
class ZoneInput:
    zone: str
    room_temperature: float | None = None
    room_humidity: float | None = None
    thermostat_entity_id: str | None = None
    windows: tuple[WindowState, ...] = ()
    last_mode: str | None = None
    last_mode_changed_at: datetime | None = None


@dataclass(frozen=True)
class RoomComfort:
    label: str
    reason: str
    quality: Quality
    perceived_temperature: float | None = None

    def as_dict(self) -> dict[str, Any]:
        payload = {
            "room_comfort_label": self.label,
            "room_comfort_reason": self.reason,
            "room_comfort_quality": self.quality,
            "perceived_room_temperature": self.perceived_temperature,
        }
        return {
            "room_comfort": payload,
            **payload,
        }


@dataclass
class ZonePlan:
    zone: str
    profile: ClimateMode
    target_temperature: float
    raw_target_temperature: float
    reason: str
    decision_path: list[str] = field(default_factory=list)
    blocked_by: list[str] = field(default_factory=list)
    source_entities: list[str] = field(default_factory=list)
    input_quality: Quality = "ok"
    effective_outdoor_temperature: float | None = None
    floor_slab_delta: float = 0.0
    floor_slab_delta_source: str | None = None
    floor_slab_delta_quality: str | None = None
    floor_slab_delta_reason: str | None = None
    floor_slab_cold_index: float | None = None
    room_comfort: RoomComfort | None = None
    is_boost_active: bool = False
    boost_until: str | None = None
    hysteresis_state: str | None = None
    allowed_profile: str | None = None
    allowed_reason: str | None = None
    heat_demand: bool | None = None
    indoor_heat_demand_reason: str | None = None
    indoor_heat_on_below: float | None = None
    indoor_heat_off_at: float | None = None
    indoor_min_hold_minutes: int | None = None
    last_calculated: str | None = None
    last_applied: str | None = None
    apply_status: str = "pending"
    apply_block_reason: str = "none"
    policy_config_hash: str | None = None

    @property
    def plan_hash(self) -> str:
        payload = {
            "zone": self.zone,
            "profile": self.profile,
            "target_temperature": self.target_temperature,
            "raw_target_temperature": self.raw_target_temperature,
            "floor_slab_delta": self.floor_slab_delta,
            "floor_slab_delta_source": self.floor_slab_delta_source,
            "floor_slab_delta_quality": self.floor_slab_delta_quality,
            "floor_slab_delta_reason": self.floor_slab_delta_reason,
            "floor_slab_cold_index": self.floor_slab_cold_index,
            "blocked_by": sorted(self.blocked_by),
            "effective_outdoor_temperature": self.effective_outdoor_temperature,
            "policy_config_hash": self.policy_config_hash,
            "allowed_profile": self.allowed_profile,
            "heat_demand": self.heat_demand,
            "indoor_heat_demand_reason": self.indoor_heat_demand_reason,
        }
        blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]

    @property
    def apply_blocked(self) -> bool:
        return bool(self.blocked_by)

    def as_dict(self) -> dict[str, Any]:
        return {
            "zone": self.zone,
            "profile": self.profile,
            "target_temperature": self.target_temperature,
            "thermostat_target_temperature": self.target_temperature,
            "raw_target_temperature": self.raw_target_temperature,
            "policy_target_temperature": self.raw_target_temperature,
            "floor_slab_delta": self.floor_slab_delta,
            "floor_slab_delta_current": self.floor_slab_delta,
            "floor_slab_delta_source": self.floor_slab_delta_source,
            "floor_slab_delta_quality": self.floor_slab_delta_quality,
            "floor_slab_delta_reason": self.floor_slab_delta_reason,
            "floor_slab_cold_index": self.floor_slab_cold_index,
            "final_target_temperature": self.target_temperature,
            "reason": self.reason,
            "decision_path": list(self.decision_path),
            "blocked_by": list(self.blocked_by),
            "input_quality": self.input_quality,
            "source_entities": list(self.source_entities),
            "effective_outdoor_temperature": self.effective_outdoor_temperature,
            **(self.room_comfort.as_dict() if self.room_comfort else {}),
            "is_boost_active": self.is_boost_active,
            "boost_until": self.boost_until,
            "hysteresis_state": self.hysteresis_state,
            "allowed_profile": self.allowed_profile,
            "allowed_reason": self.allowed_reason,
            "heat_demand": self.heat_demand,
            "indoor_heat_demand_reason": self.indoor_heat_demand_reason,
            "indoor_heat_on_below": self.indoor_heat_on_below,
            "indoor_heat_off_at": self.indoor_heat_off_at,
            "indoor_min_hold_minutes": self.indoor_min_hold_minutes,
            "last_calculated": self.last_calculated,
            "last_applied": self.last_applied,
            "apply_status": self.apply_status,
            "apply_block_reason": self.apply_block_reason,
            "policy_config_hash": self.policy_config_hash,
            "plan_hash": self.plan_hash,
        }


@dataclass(frozen=True)
class ClimateDecision:
    context: ClimateContextSnapshot
    effective_temperature: EffectiveTemperatureBreakdown
    zone_plans: dict[str, ZonePlan]
    calculated_at: datetime
    system_ready: bool

    def zone(self, zone: str) -> ZonePlan | None:
        return self.zone_plans.get(zone)

    @property
    def input_hash(self) -> str:
        payload = {
            "context": self.context.as_dict(),
            "effective_temperature": self.effective_temperature.as_dict(),
            "system_ready": self.system_ready,
        }
        blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class ApplyActionResult:
    zone: str
    status: ApplyStatus
    reason: str
    target_entity_id: str | None
    plan_hash: str | None
    service_calls: list[dict[str, Any]] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "zone": self.zone,
            "status": self.status,
            "reason": self.reason,
            "target_entity_id": self.target_entity_id,
            "plan_hash": self.plan_hash,
            "service_calls": list(self.service_calls),
            "details": dict(self.details),
        }


@dataclass(frozen=True)
class ApplyResult:
    status: ApplyStatus
    reason: str
    actions: list[ApplyActionResult]
    dry_run: bool = False
    input_hash: str | None = None
    plan_hashes: dict[str, str | None] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "reason": self.reason,
            "dry_run": self.dry_run,
            "input_hash": self.input_hash,
            "plan_hashes": dict(self.plan_hashes),
            "actions": [a.as_dict() for a in self.actions],
        }

