from __future__ import annotations

from datetime import datetime, timedelta

from custom_components.benni_climate_policy.models import (
    ClimateContextSnapshot,
    EffectiveTemperatureBreakdown,
    SourceValue,
    WindowState,
    ZoneInput,
    window_state_from_master_value,
)
from custom_components.benni_climate_policy.policy import (
    FloorSlabDeltaInput,
    OPT_LUX_REFERENCE,
    OPT_SETPOINT_SPAR,
    dynamic_floor_slab_delta,
    default_policy_tuning,
    decide_zone,
    evaluate_room_comfort,
    floor_slab_delta_for_cold_index,
    policy_tuning_from_options,
    policy_visibility_snapshot,
    setpoint_for,
    threshold_option_key,
)


def sv(value):
    return SourceValue(value, "sensor.test", "ok", False)


def ctx(
    *,
    bio="awake",
    band="home",
    transition="none",
    preheat=False,
    activity="idle",
    day_state="afternoon",
    wakeup=None,
):
    return ClimateContextSnapshot(
        activity_state=sv(activity),
        bio_state=sv(bio),
        day_context=sv("werktag"),
        day_state=sv(day_state),
        presence_band=sv(band),
        presence_household=sv("nicht_leer"),
        presence_personal=sv("zuhause"),
        presence_preheat_active=sv("on" if preheat else "off"),
        presence_transition=sv(transition),
        workday_state=sv("werktag"),
        planned_wakeup_time=sv(wakeup),
    )


def eff(temp):
    return EffectiveTemperatureBreakdown(temp, 0, 0, 0, 0, 0, temp, "ok")


def zone(**kw):
    return ZoneInput(
        kw.get("zone", "living_room"),
        room_temperature=kw.get("room_temperature", 20.0),
        thermostat_entity_id=kw.get("thermostat_entity_id", "climate.living"),
        last_mode=kw.get("last_mode"),
    )


def test_sleep_forces_off():
    plan = decide_zone(zone(), ctx(bio="sleep"), eff(0), datetime(2026, 1, 1, 12))
    assert plan.profile == "off"
    assert plan.reason == "bio_sleep_forces_off"


def test_waking_forces_off():
    plan = decide_zone(zone(), ctx(bio="waking"), eff(0), datetime(2026, 1, 1, 12))
    assert plan.profile == "off"


def test_window_unknown_open_blocks_but_unknown_tilt_ignored():
    plan = decide_zone(
        ZoneInput("living_room", thermostat_entity_id="climate.living", windows=(WindowState("unknown", "unknown"),)),
        ctx(),
        eff(0),
        datetime(2026, 1, 1, 12),
    )
    assert plan.profile == "off"
    assert plan.reason == "window_blocks_heating"

    plan = decide_zone(
        ZoneInput("living_room", thermostat_entity_id="climate.living", windows=(WindowState("off", "unknown"),)),
        ctx(),
        eff(0),
        datetime(2026, 1, 1, 12),
    )
    assert plan.profile in ("komfort", "boost")


def test_presence_far_forces_off():
    plan = decide_zone(zone(), ctx(band="far"), eff(0), datetime(2026, 1, 1, 12))
    assert plan.profile == "off"


def test_preheat_caps_to_spar():
    plan = decide_zone(zone(room_temperature=18), ctx(band="preheat", preheat=True), eff(0), datetime(2026, 1, 1, 12))
    assert plan.profile == "spar"
    assert plan.reason == "presence_preheat_caps_to_spar"


def test_passing_through_blocks_preheat():
    plan = decide_zone(zone(), ctx(band="preheat", transition="passing_through", preheat=True), eff(0), datetime(2026, 1, 1, 12))
    assert plan.profile == "off"
    assert plan.reason == "passing_through_blocks_preheat"


def test_june_july_august_allow_only_off_or_spar_and_disable_boost():
    for month in (6, 7, 8):
        plan = decide_zone(zone(room_temperature=16), ctx(), eff(0), datetime(2026, month, 1, 12))
        assert plan.profile == "spar"
        assert not plan.is_boost_active
        assert plan.allowed_profile == "spar"
        assert plan.heat_demand is True


def test_summer_eco_allowed_but_room_above_heat_off_downshifts():
    plan = decide_zone(zone(room_temperature=23.9), ctx(), eff(12.4), datetime(2026, 7, 1, 12))

    assert plan.allowed_profile == "spar"
    assert plan.profile == "off"
    assert plan.target_temperature == 10.0
    assert plan.reason == "room_temperature_above_target_no_heating"
    assert plan.heat_demand is False


def test_kitchen_uses_same_indoor_heat_demand_as_living_area():
    plan = decide_zone(zone(zone="kitchen", room_temperature=23.9), ctx(), eff(12.4), datetime(2026, 7, 1, 12))

    assert plan.allowed_profile == "spar"
    assert plan.profile == "off"
    assert plan.reason == "room_temperature_above_target_no_heating"


def test_comfort_allowed_but_room_above_comfort_heat_off_downshifts():
    plan = decide_zone(zone(room_temperature=23.3), ctx(), eff(10), datetime(2026, 1, 1, 12))

    assert plan.allowed_profile == "komfort"
    assert plan.profile == "off"
    assert plan.reason == "room_temperature_above_target_no_heating"


def test_indoor_heat_demand_below_heat_on_uses_allowed_profile():
    plan = decide_zone(zone(room_temperature=19.8), ctx(), eff(12.4), datetime(2026, 7, 1, 12))

    assert plan.allowed_profile == "spar"
    assert plan.profile == "spar"
    assert plan.heat_demand is True
    assert plan.indoor_heat_demand_reason == "room_temperature_below_heat_on_below"


def test_indoor_hysteresis_holds_last_state_between_thresholds():
    warmish_off = decide_zone(zone(room_temperature=21.0, last_mode="off"), ctx(), eff(12.4), datetime(2026, 7, 1, 12))
    warmish_heat = decide_zone(zone(room_temperature=21.0, last_mode="spar"), ctx(), eff(12.4), datetime(2026, 7, 1, 12))

    assert warmish_off.profile == "off"
    assert warmish_off.reason == "no_heat_demand"
    assert warmish_heat.profile == "spar"
    assert warmish_heat.indoor_heat_demand_reason == "indoor_hysteresis_holds_heat"


def test_living_area_window_blocker_wins_over_summer_spar():
    for zone_name in ("living_room", "kitchen"):
        for blocker in (WindowState("off", "on"), WindowState("on", "off")):
            plan = decide_zone(
                ZoneInput(
                    zone_name,
                    room_temperature=21,
                    thermostat_entity_id=f"climate.{zone_name}",
                    windows=(blocker,),
                ),
                ctx(),
                eff(0),
                datetime(2026, 7, 1, 12),
            )

            assert plan.profile == "off"
            assert plan.target_temperature == 10.0
            assert plan.reason == "window_blocks_heating"
            assert plan.allowed_profile == "off"


def test_terrace_door_open_blocks_immediately():
    now = datetime(2026, 7, 1, 18)
    for zone_name in ("living_room", "kitchen"):
        plan = decide_zone(
            ZoneInput(zone_name, thermostat_entity_id=f"climate.{zone_name}", windows=(WindowState("on", "off"),)),
            ctx(),
            eff(0),
            now,
        )
        assert plan.profile == "off"
        assert plan.reason == "window_blocks_heating"


def test_terrace_door_tilted_blocks_immediately():
    now = datetime(2026, 7, 1, 18)
    for zone_name in ("living_room", "kitchen"):
        plan = decide_zone(
            ZoneInput(zone_name, thermostat_entity_id=f"climate.{zone_name}", windows=(WindowState("off", "on"),)),
            ctx(),
            eff(0),
            now,
        )
        assert plan.profile == "off"
        assert plan.reason == "window_blocks_heating"


def test_other_opening_changes_cannot_lift_terrace_block():
    now = datetime(2026, 7, 1, 18)
    terrace_open = WindowState("on", "off")

    for zone_name in ("living_room", "kitchen"):
        for other_opening in (WindowState("off", "off"), WindowState("on", "off"), WindowState("unknown", "off")):
            plan = decide_zone(
                ZoneInput(zone_name, thermostat_entity_id=f"climate.{zone_name}", windows=(other_opening, terrace_open)),
                ctx(),
                eff(0),
                now,
            )

            assert plan.profile == "off"
            assert plan.reason == "window_blocks_heating"
            assert plan.target_temperature == 10.0


def test_stale_master_opening_is_fail_safe():
    stale = window_state_from_master_value("stale")

    assert stale.open_state == "unknown"
    assert stale.blocks_heating is True


def test_unknown_and_unavailable_master_openings_remain_fail_safe():
    for value in ("unknown", "unavailable", None, ""):
        assert window_state_from_master_value(value).blocks_heating is True


def test_free_time_early_night_holds_comfort_outside_summer():
    plan = decide_zone(zone(), ctx(activity="free_time", day_state="early_night"), eff(14), datetime(2026, 10, 1, 21))
    assert plan.profile == "komfort"
    assert plan.raw_target_temperature == 22.0
    assert plan.target_temperature == 23.0


def test_night_temperature_ramp_targets():
    late_evening = decide_zone(zone(), ctx(day_state="late_evening"), eff(14), datetime(2026, 10, 1, 21))
    early_night = decide_zone(zone(), ctx(day_state="early_night"), eff(14), datetime(2026, 10, 1, 22))
    late_night = decide_zone(zone(), ctx(day_state="late_night"), eff(14), datetime(2026, 10, 2, 1))

    assert late_evening.profile == "komfort"
    assert late_evening.raw_target_temperature == 23.0
    assert late_evening.target_temperature == 24.0
    assert early_night.profile == "komfort"
    assert early_night.raw_target_temperature == 22.0
    assert early_night.target_temperature == 23.0
    assert late_night.profile == "spar"
    assert late_night.raw_target_temperature == 21.0
    assert late_night.target_temperature == 22.0


def test_dynamic_wakeup_cutoff_forces_off():
    now = datetime(2026, 1, 1, 22)
    plan = decide_zone(zone(), ctx(wakeup=now + timedelta(hours=7, minutes=59)), eff(0), now)
    assert plan.profile == "off"
    assert plan.reason == "dynamic_wakeup_cutoff"


def test_missing_thermostat_blocks_apply_but_still_calculates_plan():
    plan = decide_zone(ZoneInput("living_room"), ctx(), eff(0), datetime(2026, 1, 1, 12))
    assert plan.profile in ("komfort", "boost")
    assert "thermostat_entity_missing" in plan.blocked_by


def test_policy_visibility_snapshot_uses_policy_thresholds():
    snapshot = policy_visibility_snapshot(7, 18)
    assert snapshot["active_month_band"] == "summer"
    assert snapshot["thresholds"]["off"] == 19.5
    assert snapshot["comfort_structurally_disabled"] is True
    assert snapshot["boost_structurally_disabled"] is True
    assert snapshot["setpoints"]["spar"] == 21.0


def test_policy_tuning_defaults_keep_existing_behavior():
    tuning = default_policy_tuning()
    assert setpoint_for("off", 0, tuning) == 10.0
    assert setpoint_for("spar", 18, tuning) == 21.0
    assert setpoint_for("spar", 10, tuning) == 21.5
    assert setpoint_for("komfort", 18, tuning) == 22.5
    assert setpoint_for("komfort", 10, tuning) == 23.0
    assert setpoint_for("komfort", 0, tuning) == 23.5
    assert setpoint_for("boost", 18, tuning) == 24.5


def test_floor_slab_delta_adds_to_thermostat_target_but_keeps_policy_target():
    plan = decide_zone(zone(room_temperature=21), ctx(), eff(14), datetime(2026, 1, 1, 12))
    assert plan.raw_target_temperature == 21.0
    assert plan.floor_slab_delta == 2.0
    assert plan.target_temperature == 23.0
    assert plan.as_dict()["policy_target_temperature"] == 21.0
    assert plan.as_dict()["thermostat_target_temperature"] == 23.0


def test_floor_slab_delta_zero_in_summer_changes_nothing():
    plan = decide_zone(zone(room_temperature=21), ctx(), eff(18), datetime(2026, 7, 1, 12))
    assert plan.floor_slab_delta == 0.0
    assert plan.raw_target_temperature == plan.target_temperature


def test_dynamic_floor_slab_delta_anchor_points_and_interpolation():
    assert floor_slab_delta_for_cold_index(12) == 0.0
    assert floor_slab_delta_for_cold_index(4) == 1.0
    assert floor_slab_delta_for_cold_index(-4) == 2.0
    assert floor_slab_delta_for_cold_index(10) == 0.25
    assert floor_slab_delta_for_cold_index(-2) == 1.75


def test_dynamic_floor_slab_delta_fallback_and_plan_fields():
    tuning = default_policy_tuning()
    missing = dynamic_floor_slab_delta(FloorSlabDeltaInput(static_fallback_delta=1.0), tuning)
    mild = dynamic_floor_slab_delta(
        FloorSlabDeltaInput(yesterday_temperature=12, today_temperature=14, tomorrow_temperature=16, static_fallback_delta=2.0),
        tuning,
    )
    plan = decide_zone(zone(room_temperature=19.0), ctx(), eff(10), datetime(2026, 1, 1, 12), floor_slab_delta=mild)

    assert missing.current == 1.0
    assert missing.quality == "fallback"
    assert mild.current == 0.0
    assert mild.quality == "ok"
    assert plan.raw_target_temperature == plan.as_dict()["policy_target_temperature"]
    assert plan.floor_slab_delta == plan.as_dict()["floor_slab_delta_current"]
    assert plan.target_temperature == plan.as_dict()["thermostat_target_temperature"]


def test_plan_hash_changes_when_floor_slab_delta_changes():
    base = decide_zone(zone(room_temperature=21), ctx(), eff(14), datetime(2026, 1, 1, 12))
    tuned = policy_tuning_from_options({threshold_option_key("winter", "floor_slab_delta"): 0.0})
    changed = decide_zone(zone(room_temperature=21), ctx(), eff(14), datetime(2026, 1, 1, 12), tuning=tuned)
    assert base.plan_hash != changed.plan_hash
    assert changed.floor_slab_delta == 0.0


def test_room_comfort_labels_and_quality():
    assert evaluate_room_comfort(21, 45, 0).label == "angenehm"
    assert evaluate_room_comfort(22, 70, 0).label == "feucht"
    assert evaluate_room_comfort(24, 78, 0).label == "schwül"
    assert evaluate_room_comfort(22, 30, 0).label == "trocken"
    degraded = evaluate_room_comfort(22, None, 0)
    assert degraded.quality == "degraded"
    assert degraded.label == "angenehm"


def test_policy_tuning_options_override_setpoints():
    tuning = policy_tuning_from_options({OPT_SETPOINT_SPAR: 20.0})
    assert setpoint_for("spar", 18, tuning) == 20.0
    assert tuning.source_for(OPT_SETPOINT_SPAR) == "user option"


def test_summer_off_threshold_option_changes_decision():
    default_plan = decide_zone(zone(), ctx(), eff(20), datetime(2026, 7, 1, 12), tuning=default_policy_tuning())
    tuned = policy_tuning_from_options({threshold_option_key("summer", "off_threshold"): 21.0})
    tuned_plan = decide_zone(zone(), ctx(), eff(20), datetime(2026, 7, 1, 12), tuning=tuned)

    assert default_plan.profile == "off"
    assert tuned_plan.profile == "spar"


def test_plan_hash_changes_when_relevant_tuning_changes():
    base = decide_zone(zone(), ctx(), eff(18), datetime(2026, 5, 1, 12), tuning=default_policy_tuning())
    tuned = decide_zone(
        zone(),
        ctx(),
        eff(18),
        datetime(2026, 5, 1, 12),
        tuning=policy_tuning_from_options({OPT_SETPOINT_SPAR: 20.0}),
    )

    assert base.plan_hash != tuned.plan_hash
    assert base.policy_config_hash != tuned.policy_config_hash


def test_invalid_tuning_options_fall_back_to_defaults():
    tuning = policy_tuning_from_options({OPT_LUX_REFERENCE: 0, OPT_SETPOINT_SPAR: "bad"})
    assert tuning.lux_reference == 30000.0
    assert tuning.setpoint_spar == 21.0
    assert tuning.source_for(OPT_LUX_REFERENCE) == "invalid_fallback_default"
    assert tuning.source_for(OPT_SETPOINT_SPAR) == "invalid_fallback_default"

