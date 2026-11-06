"""Exercise the coordinator's real stateful methods without an HA runtime."""
from __future__ import annotations

import ast
from dataclasses import replace
from datetime import datetime, timedelta
from math import isfinite
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from custom_components.benni_climate_policy.const import CONF_ZONE_TEMPERATURE, HEATING_ZONES
from custom_components.benni_climate_policy.models import (
    ClimateContextSnapshot, EffectiveTemperatureBreakdown, SourceValue, WindowState,
    ZoneInput, ZonePlan,
)
from custom_components.benni_climate_policy.policy import (
    decide_zone, indoor_heat_option_key, policy_tuning_from_options, setpoint_for, thermostat_target_for,
    threshold_for_month_config,
)
from custom_components.benni_climate_policy.tuning_options import validated_options_update


def coordinator():
    # Compile production methods verbatim; no copied algorithm or global HA stubs.
    source = ast.parse(Path("custom_components/benni_climate_policy/coordinator.py").read_text(encoding="utf-8"))
    methods = {
        "_hysteresis_requirement", "_hold_hysteresis_plan", "_apply_hysteresis",
        "_boosted_plan", "_apply_stateful_boosts", "_commit_zone_profiles", "policy_tuning",
    }
    constants = {
        "BOOST_STANDARD_DURATION", "BOOST_PRE_NIGHT_DURATION", "HEAT_STRENGTH",
        "IMMEDIATE_DECISION_REASONS",
    }
    nodes = []
    for node in source.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in constants for t in node.targets):
            nodes.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name == "_state_value":
            nodes.append(node)
        elif isinstance(node, ast.ClassDef) and node.name == "ClimatePolicyCoordinator":
            node.body = [m for m in node.body if isinstance(m, ast.FunctionDef) and m.name in methods]
            nodes.append(node)
    namespace = dict(globals(), ZONE_BATHROOM="bathroom", isfinite=isfinite)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "coordinator.py", "exec"), namespace)
    instance = namespace["ClimatePolicyCoordinator"]()
    instance._zone_profile_state = dict.fromkeys(HEATING_ZONES)
    instance._zone_profile_reason = dict.fromkeys(HEATING_ZONES)
    instance._zone_hysteresis_pending = {}
    instance._numeric_fallback_keys = set()
    instance._boost_until = dict.fromkeys(HEATING_ZONES)
    instance._boost_reason = dict.fromkeys(HEATING_ZONES)
    instance._last_day_state = "afternoon"
    return instance


def context(**values):
    defaults = dict(
        activity_state="idle", bio_state="awake", day_context="werktag",
        day_state="afternoon", presence_band="home", presence_household="nicht_leer",
        presence_personal="zuhause", presence_preheat_active="off",
        presence_transition="none", workday_state="werktag", planned_wakeup_time=None,
    )
    defaults.update(values)
    return ClimateContextSnapshot(**{k: SourceValue(v, "sensor.test", "ok", False) for k, v in defaults.items()})


def inputs(room=16, windows=()):
    return {z: ZoneInput(z, room_temperature=room, thermostat_entity_id=f"climate.{z}", windows=windows) for z in HEATING_ZONES}


def regular_plans(zone_inputs, ctx, now, tuning, teff=0):
    effective = EffectiveTemperatureBreakdown(teff, 0, 0, 0, 0, 0, teff, "ok")
    return {z: decide_zone(i, ctx, effective, now, tuning=tuning) for z, i in zone_inputs.items()}


def process(coord, plans, zone_inputs, ctx, now, tuning):
    plans = {
        zone: coord._apply_hysteresis(
            zone, plan, now, tuning, room_temperature=zone_inputs[zone].room_temperature
        )
        for zone, plan in plans.items()
    }
    coord._apply_stateful_boosts(plans, zone_inputs, ctx, now, tuning)
    coord._commit_zone_profiles(dict(plans, bathroom=ZonePlan(zone="bathroom", profile="off", target_temperature=10, raw_target_temperature=10, reason="test")))
    return plans


@pytest.mark.parametrize("teff", [15.4, 15.7])
def test_off_to_spar_starts_immediately_on_measured_heat_demand(teff):
    now = datetime(2026, 11, 6, 11)
    tuning = policy_tuning_from_options({indoor_heat_option_key("living_area", "spar", "heat_on_below"): 19.9})
    coord = coordinator()
    coord._zone_profile_state = dict.fromkeys(HEATING_ZONES, "off")
    coord._zone_hysteresis_pending = {zone: ("off", "spar", now - timedelta(minutes=5)) for zone in HEATING_ZONES}
    ctx = context()
    zone_inputs = {
        zone: replace(inp, room_temperature=room, last_mode="off")
        for (zone, inp), room in zip(inputs().items(), (19.4, 19.8), strict=True)
    }
    plans = regular_plans(zone_inputs, ctx, now, tuning, teff)

    assert all(plan.profile == "spar" and plan.heat_demand for plan in plans.values())
    assert process(coord, plans, zone_inputs, ctx, now, tuning) == plans
    assert all(plan.target_temperature > 10 for plan in plans.values())
    assert coord._zone_hysteresis_pending == {}


@pytest.mark.parametrize("room,fallback", [(None, False), (float("-inf"), False), (19.5, True)])
def test_off_to_spar_still_waits_without_valid_room_measurement(room, fallback):
    now = datetime(2026, 11, 6, 11)
    tuning = policy_tuning_from_options({})
    coord = coordinator()
    coord._zone_profile_state = dict.fromkeys(HEATING_ZONES, "off")
    if fallback:
        coord._numeric_fallback_keys = {CONF_ZONE_TEMPERATURE.format(zone=zone) for zone in HEATING_ZONES}
    ctx, zone_inputs = context(), inputs(room=room)
    plans = regular_plans(zone_inputs, ctx, now, tuning, teff=15.4)

    assert all(plan.profile == "spar" and plan.heat_demand for plan in plans.values())
    result = process(coord, plans, zone_inputs, ctx, now, tuning)
    assert {plan.profile for plan in result.values()} == {"off"}
    assert {plan.reason for plan in result.values()} == {"hysteresis_wait_off_exit_duration"}


@pytest.mark.parametrize("restriction", ["window", "sleep", "far", "outdoor", "at_threshold"])
def test_off_to_spar_respects_existing_restrictions(restriction):
    now = datetime(2026, 11, 6, 11)
    tuning = policy_tuning_from_options({indoor_heat_option_key("living_area", "spar", "heat_on_below"): 19.9})
    coord = coordinator()
    coord._zone_profile_state = dict.fromkeys(HEATING_ZONES, "off")
    ctx = context(bio_state="sleep" if restriction == "sleep" else "awake",
                  presence_band="far" if restriction == "far" else "home")
    zone_inputs = {
        zone: replace(inp, last_mode="off")
        for zone, inp in inputs(
            room=19.9 if restriction == "at_threshold" else 19.5,
            windows=(WindowState("on", "off"),) if restriction == "window" else (),
        ).items()
    }
    plans = regular_plans(zone_inputs, ctx, now, tuning, teff=16 if restriction == "outdoor" else 15.4)

    assert all(plan.profile == "off" and plan.heat_demand is False for plan in plans.values())
    assert process(coord, plans, zone_inputs, ctx, now, tuning) == plans


@pytest.fixture(
    params=[(10, {"threshold_autumn_boost_disabled": True}), (9, {}), (11, {"threshold_late_autumn_boost_disabled": True})],
    ids=["october-disabled", "september-default", "november-disabled"],
)
def disabled(request):
    month, options = request.param
    tuning = policy_tuning_from_options(options)
    assert threshold_for_month_config(month, tuning)["boost"] is None
    return datetime(2026, month, 9, 12), tuning


def test_disabled_spar_to_comfort_does_not_start_boost(disabled):
    now, tuning = disabled
    coord = coordinator()
    coord._zone_profile_state = dict.fromkeys(HEATING_ZONES, "spar")
    coord._zone_hysteresis_pending = {z: ("spar", "komfort", now - timedelta(minutes=31)) for z in HEATING_ZONES}
    ctx, zone_inputs = context(), inputs()
    plans = regular_plans(zone_inputs, ctx, now, tuning)
    assert {p.profile for p in plans.values()} == {"komfort"}
    result = process(coord, plans, zone_inputs, ctx, now, tuning)
    assert result == plans
    assert not any(coord._boost_until.values())
    assert not any(coord._boost_reason.values())


def test_disabled_pre_night_trigger_preserves_ramp(disabled):
    now, tuning = disabled
    coord = coordinator()
    ctx, zone_inputs = context(day_state="early_night"), inputs()
    plans = regular_plans(zone_inputs, ctx, now, tuning)
    assert {p.profile for p in plans.values()} == {"komfort"}
    result = process(coord, plans, zone_inputs, ctx, now, tuning)
    assert result == plans
    assert not any(coord._boost_until.values())


@pytest.mark.parametrize("teff,expected", [(0, "komfort"), (15.5, "spar"), (25, "off")])
def test_disabled_boost_clears_timer_and_hysteresis_without_promoting_plan(disabled, teff, expected):
    now, tuning = disabled
    coord = coordinator()
    ctx, zone_inputs = context(), inputs()
    for z in HEATING_ZONES:
        coord._zone_profile_state[z] = "boost"
        coord._boost_until[z] = now + timedelta(minutes=30)
        coord._boost_reason[z] = "boost_transition_to_comfort_room_delta"
        coord._zone_hysteresis_pending[z] = ("boost", expected, now - timedelta(minutes=5))
    plans = regular_plans(zone_inputs, ctx, now, tuning, teff)
    assert {p.profile for p in plans.values()} == {expected}
    result = process(coord, plans, zone_inputs, ctx, now, tuning)
    assert result == plans
    assert coord._zone_hysteresis_pending == {}
    assert not any(coord._boost_until.values())
    assert not any(coord._boost_reason.values())
    assert all(not p.is_boost_active and p.boost_until is None for p in result.values())
    assert all(coord._zone_profile_state[z] == expected for z in HEATING_ZONES)


@pytest.mark.parametrize("month,options", [(1, {}), (10, {}), (9, {"threshold_early_autumn_boost_disabled": False})])
@pytest.mark.parametrize("trigger,teff,duration", [("transition", 8, 45), ("pre-night", 0, 15), ("policy", 0, 45)])
def test_enabled_band_preserves_boost_triggers(month, options, trigger, teff, duration):
    now = datetime(2026, month, 9, 12)
    tuning = policy_tuning_from_options(options)
    assert threshold_for_month_config(month, tuning)["boost"] is not None
    if trigger == "transition":
        teff = float(threshold_for_month_config(month, tuning)["boost"]) + 1
    coord = coordinator()
    coord._zone_profile_state = dict.fromkeys(HEATING_ZONES, "spar")
    ctx = context(day_state="early_night" if trigger == "pre-night" else "afternoon")
    zone_inputs = inputs()
    plans = regular_plans(zone_inputs, ctx, now, tuning, teff)
    # Test the manager trigger directly; colder-profile hysteresis is independently unchanged.
    coord._apply_stateful_boosts(plans, zone_inputs, ctx, now, tuning)
    expected_reason = {"transition": "boost_transition_to_comfort_room_delta", "pre-night": "pre_night_thermal_boost", "policy": "boost_threshold_and_room_delta"}[trigger]
    for z in HEATING_ZONES:
        assert plans[z].profile == "boost"
        assert plans[z].reason == expected_reason
        assert coord._boost_until[z] == now + timedelta(minutes=duration)


def test_live_tuning_disable_cancels_previously_enabled_boost():
    now = datetime(2026, 10, 9, 12)
    coord = coordinator()
    ctx, zone_inputs = context(), inputs()
    enabled = policy_tuning_from_options({})
    plans = regular_plans(zone_inputs, ctx, now, enabled)
    coord._apply_stateful_boosts(plans, zone_inputs, ctx, now, enabled)
    coord._zone_profile_state = dict.fromkeys(HEATING_ZONES, "boost")
    assert all(coord._boost_until.values())
    disabled = policy_tuning_from_options({"threshold_autumn_boost_disabled": True})
    plans = regular_plans(zone_inputs, ctx, now, disabled)
    assert process(coord, plans, zone_inputs, ctx, now, disabled) == plans
    assert not any(coord._boost_until.values())
    assert not any(coord._boost_reason.values())


def test_saved_boost_disable_applies_on_season_change_and_fresh_coordinator():
    key = "threshold_late_autumn_boost_disabled"
    options = validated_options_update({}, {key: True})
    october = datetime(2026, 10, 31, 23, 55)
    november = datetime(2026, 11, 1, 0)
    ctx, zone_inputs = context(), inputs()
    coord = coordinator()
    coord.entry = SimpleNamespace(options=options)
    tuning = coord.policy_tuning

    plans = regular_plans(zone_inputs, ctx, october, tuning)
    assert {p.profile for p in process(coord, plans, zone_inputs, ctx, october, tuning).values()} == {"boost"}
    assert all(until > november for until in coord._boost_until.values())

    restarted = coordinator()
    restarted.entry = SimpleNamespace(options=dict(options))
    for current in (coord, restarted):
        tuning = current.policy_tuning
        plans = regular_plans(zone_inputs, ctx, november, tuning)
        assert {p.profile for p in plans.values()} == {"komfort"}
        assert process(current, plans, zone_inputs, ctx, november, tuning) == plans
        assert not any(current._boost_until.values())
        assert not any(current._boost_reason.values())

    restarted.entry.options = validated_options_update(options, {key: False})
    tuning = restarted.policy_tuning
    plans = regular_plans(zone_inputs, ctx, november, tuning)
    assert {p.profile for p in plans.values()} == {"boost"}
    assert {p.profile for p in process(restarted, plans, zone_inputs, ctx, november, tuning).values()} == {"komfort"}
    later = november + timedelta(minutes=30)
    plans = regular_plans(zone_inputs, ctx, later, tuning)
    result = process(restarted, plans, zone_inputs, ctx, later, tuning)
    assert {p.reason for p in result.values()} == {"boost_threshold_and_room_delta"}
    assert set(restarted._boost_until.values()) == {later + timedelta(minutes=45)}


@pytest.mark.parametrize("restriction,expected", [("window", "off"), ("far", "off"), ("sleep", "off"), ("waking", "off"), ("indoor", "off"), ("preheat", "spar")])
@pytest.mark.parametrize("boost_disabled", [True, False])
def test_safety_and_presence_rules_keep_priority(restriction, expected, boost_disabled):
    now = datetime(2026, 10, 9, 12)
    tuning = policy_tuning_from_options({"threshold_autumn_boost_disabled": boost_disabled})
    coord = coordinator()
    coord._zone_profile_state = dict.fromkeys(HEATING_ZONES, "boost")
    coord._boost_until = dict.fromkeys(HEATING_ZONES, now + timedelta(minutes=30))
    coord._boost_reason = dict.fromkeys(HEATING_ZONES, "pre_night_thermal_boost")
    ctx = context(**{
        "far": {"presence_band": "far"}, "sleep": {"bio_state": "sleep"},
        "waking": {"bio_state": "waking"},
        "preheat": {"presence_band": "preheat", "presence_preheat_active": "on"},
    }.get(restriction, {}))
    zone_inputs = inputs(room=30 if restriction == "indoor" else 16, windows=(WindowState("on", "off"),) if restriction == "window" else ())
    plans = regular_plans(zone_inputs, ctx, now, tuning)
    result = process(coord, plans, zone_inputs, ctx, now, tuning)
    assert result == plans
    assert {p.profile for p in result.values()} == {expected}


def test_enabled_hysteresis_and_running_timer_remain_active():
    now = datetime(2026, 1, 9, 12)
    tuning = policy_tuning_from_options({})
    coord = coordinator()
    coord._zone_profile_state = dict.fromkeys(HEATING_ZONES, "boost")
    until = now + timedelta(minutes=30)
    coord._boost_until = dict.fromkeys(HEATING_ZONES, until)
    coord._boost_reason = dict.fromkeys(HEATING_ZONES, "existing_boost")
    ctx, zone_inputs = context(), inputs(room=20)
    plans = regular_plans(zone_inputs, ctx, now, tuning, teff=8)
    assert {p.profile for p in plans.values()} == {"komfort"}
    result = process(coord, plans, zone_inputs, ctx, now, tuning)
    for z in HEATING_ZONES:
        assert result[z].profile == "boost"
        assert result[z].reason == "existing_boost"
        assert result[z].boost_until == until.isoformat()
        assert z in coord._zone_hysteresis_pending
