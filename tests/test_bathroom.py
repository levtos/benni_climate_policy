from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from custom_components.benni_climate_policy.bathroom import (
    OPT_BATH_HUMIDITY_GROUND_HEAT_OFF_AT,
    OPT_BATH_HUMIDITY_GROUND_HEAT_TARGET,
    OPT_BATH_SETPOINT_GROUND,
    OPT_BATH_SETPOINT_COMFORT,
    BathroomClimateInput,
    BathroomHumidityInput,
    absolute_humidity_gm3,
    bath_outdoor_bonus,
    bath_tuning_from_options,
    decide_bathroom_climate,
    decide_bathroom_diffuser,
    decide_bathroom_fan,
    dew_point_celsius,
    humidity_diagnostics,
)
from custom_components.benni_climate_policy.models import (
    ClimateContextSnapshot,
    EffectiveTemperatureBreakdown,
    SourceValue,
)
from custom_components.benni_climate_policy.policy import (
    indoor_heat_option_key,
    policy_tuning_from_options,
)
from custom_components.benni_climate_policy.tuning_options import (
    default_option_values,
    validated_options_update,
)


def sv(value):
    return SourceValue(value, "sensor.test", "ok", False)


def ctx(*, day_state="afternoon", workday="werktag"):
    return ClimateContextSnapshot(
        activity_state=sv("idle"),
        bio_state=sv("awake"),
        day_context=sv(workday),
        day_state=sv(day_state),
        presence_band=sv("home"),
        presence_household=sv("nicht_leer"),
        presence_personal=sv("zuhause"),
        presence_preheat_active=sv("off"),
        presence_transition=sv("none"),
        workday_state=sv(workday),
        planned_wakeup_time=sv(None),
    )


def eff(temp):
    return EffectiveTemperatureBreakdown(temp, 0, 0, 0, 0, 0, temp, "ok" if temp is not None else "missing")


def climate_input(temp=21.0, humidity=55.0):
    return BathroomClimateInput(temp, humidity, "climate.bath")


def humidity_input(
    *,
    bath_temp=24.0,
    bath_humidity=60.0,
    living_temp=21.0,
    living_humidity=50.0,
    toilet_activity=False,
    shower_activity=False,
    usage_hold=False,
    usage_hold_until=None,
):
    return BathroomHumidityInput(
        bath_temp,
        bath_humidity,
        living_temp,
        living_humidity,
        toilet_activity_active=toilet_activity,
        shower_activity_active=shower_activity,
        fan_usage_hold_active=usage_hold,
        fan_usage_hold_until=usage_hold_until,
    )


def test_bathroom_defaults_ground_heat():
    plan = decide_bathroom_climate(climate_input(temp=18.5), ctx(), eff(10), datetime(2026, 1, 1, 12), bath_tuning_from_options({}))
    assert plan.profile == "grundwaerme"
    assert plan.target_temperature == 22.0


def test_bathroom_missing_effective_temperature_uses_protection():
    plan = decide_bathroom_climate(climate_input(), ctx(), eff(None), datetime(2026, 1, 1, 12), bath_tuning_from_options({}))
    assert plan.profile == "protection"
    assert plan.target_temperature == 16.0
    assert plan.reason == "effective_temperature_missing_protection"


def test_bathroom_comfort_windows_and_teff_limit():
    tuning = bath_tuning_from_options({})
    plan = decide_bathroom_climate(climate_input(), ctx(day_state="early_morning", workday="werktag"), eff(10), datetime(2026, 1, 1, 7), tuning)
    assert plan.profile == "komfort"
    assert plan.target_temperature == 23.0

    suppressed = decide_bathroom_climate(climate_input(temp=18.5), ctx(day_state="early_morning", workday="werktag"), eff(19), datetime(2026, 1, 1, 7), tuning)
    assert suppressed.profile == "grundwaerme"

    weekend = decide_bathroom_climate(climate_input(), ctx(day_state="forenoon", workday="wochenende"), eff(10), datetime(2026, 1, 3, 10), tuning)
    assert weekend.profile == "komfort"

    evening = decide_bathroom_climate(climate_input(), ctx(day_state="late_evening"), eff(10), datetime(2026, 1, 1, 22), tuning)
    assert evening.profile == "komfort"


def test_bathroom_over_target_forces_heating_off_even_when_fan_can_run():
    now = datetime(2026, 1, 1, 7)
    tuning = bath_tuning_from_options({})
    heating = decide_bathroom_climate(
        climate_input(temp=24.6),
        ctx(day_state="early_morning", workday="werktag"),
        eff(10),
        now,
        tuning,
    )
    fan = decide_bathroom_fan(
        BathroomHumidityInput(24.6, 80, 21, 45),
        heating,
        now=now,
        day_state="early_morning",
        last_fan_active_at=None,
        tuning=tuning,
    )

    assert heating.profile == "off"
    assert heating.target_temperature == 10.0
    assert heating.reason == "bath_temperature_above_target_no_heating"
    assert heating.allowed_profile == "komfort"
    assert heating.heat_demand is False
    assert fan.target_switch_state == "on"


def test_bathroom_ground_heat_stops_when_room_is_warm_enough():
    plan = decide_bathroom_climate(
        climate_input(temp=22.5),
        ctx(),
        eff(10),
        datetime(2026, 1, 1, 12),
        bath_tuning_from_options({}),
    )

    assert plan.allowed_profile == "grundwaerme"
    assert plan.profile == "off"
    assert plan.reason == "bath_temperature_above_target_no_heating"


def test_bathroom_humidity_ground_heat_overrides_warm_room_cutoff_when_cool_outside():
    plan = decide_bathroom_climate(
        climate_input(temp=21.7, humidity=72.0),
        ctx(),
        eff(12),
        datetime(2026, 6, 10, 6),
        bath_tuning_from_options({}),
    )

    assert plan.allowed_profile == "grundwaerme"
    assert plan.profile == "grundwaerme"
    assert plan.target_temperature == 22.0
    assert plan.reason == "bath_humidity_ground_heat"
    assert plan.heat_demand is True
    assert plan.indoor_heat_demand_reason == "bath_humidity_ground_heat_overrides_indoor_hysteresis"
    assert plan.indoor_heat_off_at == 22.5


def test_bathroom_humidity_ground_heat_respects_warm_weather_and_upper_cutoff():
    warm_weather = decide_bathroom_climate(
        climate_input(temp=22.6, humidity=78.0),
        ctx(),
        eff(24),
        datetime(2026, 7, 1, 6),
        bath_tuning_from_options({}),
    )

    assert warm_weather.profile == "off"
    assert warm_weather.reason == "bath_temperature_above_target_no_heating"

    already_warm = decide_bathroom_climate(
        climate_input(temp=22.6, humidity=78.0),
        ctx(),
        eff(12),
        datetime(2026, 6, 10, 6),
        bath_tuning_from_options({}),
    )

    assert already_warm.profile == "off"
    assert already_warm.reason == "bath_temperature_above_target_no_heating"


def test_bathroom_outdoor_bonus_steps():
    tuning = bath_tuning_from_options({})
    assert bath_outdoor_bonus(0, tuning) == 0.5
    assert bath_outdoor_bonus(5, tuning) == 0.3
    assert bath_outdoor_bonus(16, tuning) == -0.5
    assert bath_outdoor_bonus(10, tuning) == 0.0


@pytest.mark.parametrize("day_context", ["werktag", "wochenende", "frei", "feiertag"])
@pytest.mark.parametrize("day_state", [
    "early_night", "late_night", "early_morning", "forenoon", "midday",
    "afternoon", "late_afternoon", "evening", "late_evening",
])
def test_bathroom_comfort_windows_match_producer_values(day_context, day_state):
    plan = decide_bathroom_climate(
        climate_input(temp=20, humidity=40),
        ctx(day_state=day_state, workday=day_context),
        eff(10),
        datetime(2026, 11, 1, 10),
        bath_tuning_from_options({}),
    )
    comfort = (
        day_state == "late_evening"
        or (day_context == "werktag" and day_state == "early_morning")
        or (day_context != "werktag" and day_state == "forenoon")
    )
    assert plan.profile == ("komfort" if comfort else "grundwaerme")
    assert plan.target_temperature == (23.0 if comfort else 22.0)


@pytest.mark.parametrize(("temp", "last_mode", "expected_profile"), [
    (21.49, "off", "grundwaerme"),
    (21.5, "off", "off"),
    (22.0, "off", "off"),
    (22.0, "grundwaerme", "grundwaerme"),
    (22.49, "grundwaerme", "grundwaerme"),
    (22.5, "grundwaerme", "off"),
    (22.51, "grundwaerme", "off"),
])
def test_bathroom_ground_heat_hysteresis(temp, last_mode, expected_profile):
    plan = decide_bathroom_climate(
        BathroomClimateInput(temp, 40, "climate.bath", last_mode=last_mode),
        ctx(), eff(10), datetime(2026, 11, 1, 12), bath_tuning_from_options({}),
    )
    assert plan.profile == expected_profile
    assert plan.indoor_heat_on_below == 21.5
    assert plan.indoor_heat_off_at == 22.5
    assert plan.indoor_min_hold_minutes == 20
    assert plan.target_temperature == (22.0 if expected_profile == "grundwaerme" else 10.0)


@pytest.mark.parametrize("drying_active", [False, True])
@pytest.mark.parametrize("options", [
    {},
    {OPT_BATH_SETPOINT_GROUND: 23.0,
     OPT_BATH_HUMIDITY_GROUND_HEAT_TARGET: 19.0,
     OPT_BATH_HUMIDITY_GROUND_HEAT_OFF_AT: 20.0},
])
def test_bathroom_humidity_heat_never_lowers_normal_ground_heat(options, drying_active):
    now = datetime(2026, 11, 1, 12)
    tuning = bath_tuning_from_options(options)
    normal = decide_bathroom_climate(climate_input(temp=21.7, humidity=40), ctx(), eff(10), now, tuning)
    humid = decide_bathroom_climate(
        climate_input(temp=21.7, humidity=72), ctx(), eff(10), now, tuning,
        fan_drying_active=drying_active,
    )
    assert humid.profile == "grundwaerme"
    assert humid.target_temperature >= normal.target_temperature
    assert humid.indoor_heat_off_at >= normal.indoor_heat_off_at


def test_bathroom_new_defaults_are_valid_in_tuning_and_saved_options_still_win():
    defaults = default_option_values()
    keys = [OPT_BATH_SETPOINT_GROUND, OPT_BATH_SETPOINT_COMFORT,
            OPT_BATH_HUMIDITY_GROUND_HEAT_TARGET, OPT_BATH_HUMIDITY_GROUND_HEAT_OFF_AT]
    keys += [indoor_heat_option_key("bathroom", profile, field)
             for profile in ("grundwaerme", "komfort")
             for field in ("heat_on_below", "heat_off_at", "min_hold_minutes")]
    assert validated_options_update({}, {key: defaults[key] for key in keys})
    assert [defaults[key] for key in keys] == [22.0, 23.0, 22.0, 22.5, 21.5, 22.5, 20, 22.5, 23.5, 30]

    on_key = indoor_heat_option_key("bathroom", "grundwaerme", "heat_on_below")
    off_key = indoor_heat_option_key("bathroom", "grundwaerme", "heat_off_at")
    options = {OPT_BATH_SETPOINT_GROUND: 19.0, on_key: 18.5, off_key: 20.2}
    plan = decide_bathroom_climate(
        climate_input(temp=18, humidity=40), ctx(), eff(10), datetime(2026, 11, 1, 12),
        bath_tuning_from_options(options), indoor_tuning=policy_tuning_from_options(options),
    )
    assert plan.target_temperature == 19.0
    assert plan.indoor_heat_on_below == 18.5
    assert plan.indoor_heat_off_at == 20.2
    assert options == {OPT_BATH_SETPOINT_GROUND: 19.0, on_key: 18.5, off_key: 20.2}


def test_bathroom_tuning_changes_plan_hash():
    base = decide_bathroom_climate(climate_input(temp=18.0), ctx(), eff(10), datetime(2026, 1, 1, 12), bath_tuning_from_options({}))
    tuned = decide_bathroom_climate(
        climate_input(temp=18.0),
        ctx(),
        eff(10),
        datetime(2026, 1, 1, 12),
        bath_tuning_from_options({OPT_BATH_SETPOINT_GROUND: 18.5}),
    )
    assert tuned.target_temperature == 18.5
    assert base.plan_hash != tuned.plan_hash


def test_bathroom_humidity_ground_heat_tuning_changes_plan_hash():
    now = datetime(2026, 6, 10, 6)
    base = decide_bathroom_climate(
        climate_input(temp=21.0, humidity=72.0),
        ctx(),
        eff(12),
        now,
        bath_tuning_from_options({}),
    )
    tuned = decide_bathroom_climate(
        climate_input(temp=21.0, humidity=72.0),
        ctx(),
        eff(12),
        now,
        bath_tuning_from_options({
            OPT_BATH_HUMIDITY_GROUND_HEAT_TARGET: 23.0,
            OPT_BATH_HUMIDITY_GROUND_HEAT_OFF_AT: 23.5,
        }),
    )

    assert tuned.target_temperature == 23.0
    assert tuned.indoor_heat_off_at == 23.5
    assert tuned.plan_hash != base.plan_hash


def test_dewpoint_absolute_humidity_and_delta():
    assert dew_point_celsius(24, 80) > 20
    assert 8.0 < absolute_humidity_gm3(20, 50) < 9.5
    diagnostics = humidity_diagnostics(humidity_input(bath_temp=24, bath_humidity=70, living_temp=20, living_humidity=50))
    assert diagnostics["absolute_humidity_bathroom"] > diagnostics["absolute_humidity_living"]
    assert diagnostics["ah_delta"] > 0


def test_bathroom_fan_acute_afterrun_stoss_and_end_thresholds():
    now = datetime(2026, 1, 1, 12)
    heating = decide_bathroom_climate(climate_input(temp=22), ctx(), eff(10), now, bath_tuning_from_options({}))
    tuning = bath_tuning_from_options({})

    acute = decide_bathroom_fan(humidity_input(bath_humidity=76), heating, now=now, day_state="afternoon", last_fan_active_at=now, tuning=tuning)
    assert acute.mode == "akut"

    acute_rise = decide_bathroom_fan(
        BathroomHumidityInput(24, 65, 21, 50, previous_bathroom_humidity=49, previous_bathroom_humidity_at=now - timedelta(minutes=4)),
        heating,
        now=now,
        day_state="afternoon",
        last_fan_active_at=now,
        tuning=tuning,
    )
    assert acute_rise.mode == "akut"
    assert acute_rise.diagnostics["bathroom_humidity_rise_5m"] == 16

    afterrun = decide_bathroom_fan(humidity_input(bath_temp=22, bath_humidity=55, living_temp=21, living_humidity=50), heating, now=now, day_state="afternoon", last_fan_active_at=now, tuning=tuning)
    assert afterrun.mode == "nachluft"

    ended = decide_bathroom_fan(humidity_input(bath_temp=21, bath_humidity=45, living_temp=21, living_humidity=45), heating, now=now, day_state="afternoon", last_fan_active_at=now, tuning=tuning)
    assert ended.mode == "off"
    assert ended.reason == "bath_fan_afterrun_end_threshold"

    stoss = decide_bathroom_fan(
        humidity_input(bath_temp=22, bath_humidity=53, living_temp=21, living_humidity=50),
        heating,
        now=now,
        day_state="afternoon",
        last_fan_active_at=now - timedelta(hours=13),
        tuning=tuning,
    )
    assert stoss.mode == "stoss"

    night = decide_bathroom_fan(
        humidity_input(bath_temp=22, bath_humidity=53, living_temp=21, living_humidity=50),
        heating,
        now=now,
        day_state="early_night",
        last_fan_active_at=now - timedelta(hours=13),
        tuning=tuning,
    )
    assert night.mode == "off"


def test_bathroom_fan_heating_coordination_blocks_only_non_acute():
    now = datetime(2026, 1, 1, 12)
    heating = decide_bathroom_climate(climate_input(temp=17), ctx(day_state="early_morning"), eff(10), now, bath_tuning_from_options({}))
    tuning = bath_tuning_from_options({})

    blocked = decide_bathroom_fan(humidity_input(bath_temp=17, bath_humidity=70, living_temp=20, living_humidity=45), heating, now=now, day_state="afternoon", last_fan_active_at=now, tuning=tuning)
    assert blocked.mode == "off"
    assert "bath_heating_up_blocks_fan" in blocked.blocked_by

    acute = decide_bathroom_fan(humidity_input(bath_temp=17, bath_humidity=80), heating, now=now, day_state="afternoon", last_fan_active_at=now, tuning=tuning)
    assert acute.mode == "akut"
    assert acute.diagnostics["heating_fan_coordination_state"] == "acute_overrides_heating"


def test_bathroom_fan_acute_max_duration_stops_stuck_humidity_or_activity():
    now = datetime(2026, 1, 1, 12)
    heating = decide_bathroom_climate(climate_input(temp=22), ctx(), eff(10), now, bath_tuning_from_options({}))
    tuning = bath_tuning_from_options({})

    fan = decide_bathroom_fan(
        BathroomHumidityInput(
            24,
            80,
            21,
            45,
            fan_active_since=now - timedelta(minutes=tuning.fan_acute_max_minutes + 1),
        ),
        heating,
        now=now,
        day_state="afternoon",
        last_fan_active_at=now - timedelta(minutes=tuning.fan_acute_max_minutes + 1),
        tuning=tuning,
    )

    assert fan.mode == "off"
    assert fan.target_switch_state == "off"
    assert fan.reason == "bath_fan_akut_max_duration_reached"
    assert fan.diagnostics["fan_max_duration_reached"] is True
    assert fan.diagnostics["fan_uncapped_mode"] == "akut"
    assert fan.diagnostics["heating_fan_coordination_state"] == "max_duration_reached"


def test_bathroom_fan_afterrun_and_regular_stoss_max_duration_stop():
    now = datetime(2026, 1, 1, 12)
    heating = decide_bathroom_climate(climate_input(temp=22), ctx(), eff(10), now, bath_tuning_from_options({}))
    tuning = bath_tuning_from_options({})

    afterrun = decide_bathroom_fan(
        humidity_input(bath_temp=22, bath_humidity=55, living_temp=21, living_humidity=50),
        heating,
        now=now,
        day_state="afternoon",
        last_fan_active_at=now - timedelta(minutes=tuning.fan_afterrun_max_minutes + 1),
        tuning=tuning,
    )
    assert afterrun.mode == "nachluft"

    capped_afterrun = decide_bathroom_fan(
        BathroomHumidityInput(
            22,
            55,
            21,
            50,
            fan_active_since=now - timedelta(minutes=tuning.fan_afterrun_max_minutes + 1),
        ),
        heating,
        now=now,
        day_state="afternoon",
        last_fan_active_at=now - timedelta(minutes=tuning.fan_afterrun_max_minutes + 1),
        tuning=tuning,
    )
    assert capped_afterrun.mode == "off"
    assert capped_afterrun.reason == "bath_fan_nachluft_max_duration_reached"

    capped_stoss = decide_bathroom_fan(
        BathroomHumidityInput(
            22,
            53,
            21,
            50,
            fan_active_since=now - timedelta(minutes=tuning.fan_stoss_duration_minutes + 1),
        ),
        heating,
        now=now,
        day_state="afternoon",
        last_fan_active_at=now - timedelta(hours=13),
        tuning=tuning,
    )
    assert capped_stoss.mode == "off"
    assert capped_stoss.reason == "bath_fan_stoss_max_duration_reached"


def test_bathroom_fan_usage_hold_forces_30_minute_run():
    now = datetime(2026, 1, 1, 12)
    heating = decide_bathroom_climate(climate_input(temp=17), ctx(day_state="early_morning"), eff(10), now, bath_tuning_from_options({}))
    tuning = bath_tuning_from_options({})

    fan = decide_bathroom_fan(
        humidity_input(
            bath_temp=17,
            bath_humidity=45,
            living_temp=21,
            living_humidity=45,
            usage_hold=True,
            usage_hold_until=now + timedelta(minutes=30),
        ),
        heating,
        now=now,
        day_state="early_night",
        last_fan_active_at=now,
        tuning=tuning,
    )

    assert fan.mode == "stoss"
    assert fan.target_switch_state == "on"
    assert fan.reason == "bath_fan_usage_hold"
    assert fan.blocked_by == []
    assert fan.diagnostics["fan_usage_hold_active"] is True
    assert fan.diagnostics["fan_usage_hold_until"] == (now + timedelta(minutes=30)).isoformat()
    assert fan.diagnostics["heating_fan_coordination_state"] == "usage_hold_overrides_heating"

    protected = decide_bathroom_fan(
        BathroomHumidityInput(
            17,
            45,
            21,
            45,
            fan_active_since=now - timedelta(minutes=tuning.fan_stoss_duration_minutes + 1),
            fan_usage_hold_active=True,
            fan_usage_hold_until=now + timedelta(minutes=30),
        ),
        heating,
        now=now,
        day_state="early_night",
        last_fan_active_at=now,
        tuning=tuning,
    )
    assert protected.mode == "stoss"
    assert protected.reason == "bath_fan_usage_hold"
    assert protected.diagnostics["fan_max_duration_reached"] is False


def test_bathroom_fan_usage_hold_wins_over_afterrun_and_plain_acute():
    now = datetime(2026, 1, 1, 12)
    heating = decide_bathroom_climate(climate_input(temp=17), ctx(day_state="early_morning"), eff(10), now, bath_tuning_from_options({}))
    tuning = bath_tuning_from_options({})

    afterrun_hold = decide_bathroom_fan(
        humidity_input(
            bath_temp=22,
            bath_humidity=70,
            living_temp=21,
            living_humidity=45,
            usage_hold=True,
            usage_hold_until=now + timedelta(minutes=30),
        ),
        heating,
        now=now,
        day_state="afternoon",
        last_fan_active_at=now,
        tuning=tuning,
    )
    assert afterrun_hold.mode == "stoss"
    assert afterrun_hold.reason == "bath_fan_usage_hold"

    acute_hold = decide_bathroom_fan(
        humidity_input(
            bath_temp=24,
            bath_humidity=80,
            living_temp=21,
            living_humidity=45,
            usage_hold=True,
            usage_hold_until=now + timedelta(minutes=30),
        ),
        heating,
        now=now,
        day_state="afternoon",
        last_fan_active_at=now,
        tuning=tuning,
    )
    assert acute_hold.mode == "stoss"
    assert acute_hold.reason == "bath_fan_usage_hold"


def test_bathroom_fan_shower_activity_is_acute():
    now = datetime(2026, 1, 1, 12)
    heating = decide_bathroom_climate(climate_input(temp=17), ctx(day_state="early_morning"), eff(10), now, bath_tuning_from_options({}))
    tuning = bath_tuning_from_options({})

    fan = decide_bathroom_fan(
        humidity_input(bath_temp=17, bath_humidity=45, living_temp=21, living_humidity=45, shower_activity=True),
        heating,
        now=now,
        day_state="afternoon",
        last_fan_active_at=now,
        tuning=tuning,
    )

    assert fan.mode == "akut"
    assert fan.target_switch_state == "on"
    assert fan.reason == "bath_fan_shower_activity_hold"
    assert fan.blocked_by == []
    assert fan.diagnostics["shower_activity_active"] is True
    assert fan.diagnostics["heating_fan_coordination_state"] == "shower_activity_overrides_heating"


def test_bathroom_fan_unknown_startup_runtime_turns_off_unprotected_modes():
    now = datetime(2026, 1, 1, 12)
    heating = decide_bathroom_climate(climate_input(temp=22), ctx(), eff(10), now, bath_tuning_from_options({}))
    tuning = bath_tuning_from_options({})

    fan = decide_bathroom_fan(
        BathroomHumidityInput(
            24,
            80,
            21,
            45,
            fan_active_since=now,
            fan_active_since_uncertain=True,
        ),
        heating,
        now=now,
        day_state="afternoon",
        last_fan_active_at=None,
        tuning=tuning,
    )

    assert fan.mode == "off"
    assert fan.target_switch_state == "off"
    assert fan.reason == "bath_fan_akut_active_since_unknown_at_startup"
    assert fan.diagnostics["fan_active_since_uncertain"] is True
    assert fan.diagnostics["fan_max_duration_reached"] is True


def test_bathroom_fan_unknown_startup_runtime_does_not_stop_usage_hold():
    now = datetime(2026, 1, 1, 12)
    heating = decide_bathroom_climate(climate_input(temp=17), ctx(day_state="early_morning"), eff(10), now, bath_tuning_from_options({}))
    tuning = bath_tuning_from_options({})

    fan = decide_bathroom_fan(
        BathroomHumidityInput(
            17,
            80,
            21,
            45,
            fan_active_since=now,
            fan_active_since_uncertain=True,
            fan_usage_hold_active=True,
            fan_usage_hold_until=now + timedelta(minutes=30),
        ),
        heating,
        now=now,
        day_state="afternoon",
        last_fan_active_at=None,
        tuning=tuning,
    )

    assert fan.mode == "stoss"
    assert fan.reason == "bath_fan_usage_hold"
    assert fan.diagnostics["fan_max_duration_reached"] is False


def _heating(now):
    return decide_bathroom_climate(climate_input(temp=22), ctx(), eff(10), now, bath_tuning_from_options({}))


def test_bathroom_fan_acute_blocked_when_venting_unhelpful():
    # Bathroom air is drier (absolute) than the living air the fan would pull in,
    # so venting is counterproductive even though relative humidity is high.
    now = datetime(2026, 6, 19, 22)
    tuning = bath_tuning_from_options({})
    fan = decide_bathroom_fan(
        BathroomHumidityInput(20, 80, 24, 85),
        _heating(now),
        now=now,
        day_state="afternoon",
        last_fan_active_at=now,
        tuning=tuning,
    )
    assert fan.diagnostics["ah_delta"] < 0
    assert fan.mode == "off"
    assert fan.target_switch_state == "off"
    assert fan.reason == "bath_fan_acute_venting_unhelpful"
    assert fan.diagnostics["drying_recommended"] is True


def test_bathroom_fan_hard_cap_reached_enters_cooldown():
    now = datetime(2026, 6, 19, 12)
    tuning = bath_tuning_from_options({})
    fan = decide_bathroom_fan(
        BathroomHumidityInput(24, 80, 21, 45, cap_deadline=now - timedelta(minutes=1)),
        _heating(now),
        now=now,
        day_state="afternoon",
        last_fan_active_at=now,
        tuning=tuning,
    )
    assert fan.diagnostics["ah_delta"] > 0
    assert fan.mode == "off"
    assert fan.reason == "bath_fan_hard_cap_reached"
    assert fan.diagnostics["hard_cap_state"] == "hard_cap_reached"
    assert fan.cap_deadline is None
    assert fan.cooldown_until == now + timedelta(minutes=tuning.fan_cooldown_minutes)


def test_bathroom_fan_within_budget_keeps_running_and_holds_deadline():
    now = datetime(2026, 6, 19, 12)
    deadline = now + timedelta(minutes=30)
    tuning = bath_tuning_from_options({})
    fan = decide_bathroom_fan(
        BathroomHumidityInput(24, 80, 21, 45, cap_deadline=deadline),
        _heating(now),
        now=now,
        day_state="afternoon",
        last_fan_active_at=now,
        tuning=tuning,
    )
    assert fan.mode == "akut"
    assert fan.cap_deadline == deadline
    assert fan.cooldown_until is None
    assert fan.diagnostics["hard_cap_state"] == "within_budget"


def test_bathroom_fan_cooldown_lockout_blocks_humidity_run():
    now = datetime(2026, 6, 19, 12)
    cooldown = now + timedelta(minutes=60)
    tuning = bath_tuning_from_options({})
    fan = decide_bathroom_fan(
        BathroomHumidityInput(24, 80, 21, 45, cooldown_until=cooldown),
        _heating(now),
        now=now,
        day_state="afternoon",
        last_fan_active_at=now,
        tuning=tuning,
    )
    assert fan.mode == "off"
    assert fan.reason == "bath_fan_cooldown_lockout"
    assert fan.cooldown_until == cooldown
    assert fan.diagnostics["drying_recommended"] is True


def test_bathroom_fan_event_refills_budget_and_clears_cooldown():
    now = datetime(2026, 6, 19, 12)
    tuning = bath_tuning_from_options({})
    fan = decide_bathroom_fan(
        BathroomHumidityInput(
            24,
            80,
            21,
            45,
            shower_activity_active=True,
            cooldown_until=now + timedelta(minutes=60),
        ),
        _heating(now),
        now=now,
        day_state="afternoon",
        last_fan_active_at=now,
        tuning=tuning,
    )
    assert fan.target_switch_state == "on"
    assert fan.cooldown_until is None
    assert fan.cap_deadline == now + timedelta(minutes=tuning.fan_hard_cap_minutes)
    assert fan.diagnostics["hard_cap_state"] == "event_refill"


def test_bathroom_cooldown_drying_heat_engages_when_cool():
    now = datetime(2026, 6, 19, 12)
    tuning = bath_tuning_from_options({})
    plan = decide_bathroom_climate(
        climate_input(temp=18.5, humidity=50.0),
        ctx(),
        eff(12),
        now,
        tuning,
        fan_drying_active=True,
    )
    assert plan.profile == "grundwaerme"
    assert plan.target_temperature == 22.0
    assert plan.reason == "bath_cooldown_drying_heat"

    # Without the drying signal low humidity stays on plain ground heat.
    baseline = decide_bathroom_climate(
        climate_input(temp=18.5, humidity=50.0),
        ctx(),
        eff(12),
        now,
        tuning,
    )
    assert baseline.reason == "bath_ground_heat_default"
    assert baseline.target_temperature == 22.0


def test_bathroom_diffuser_follows_fan_then_caps_then_off():
    now = datetime(2026, 6, 19, 12)
    tuning = bath_tuning_from_options({})
    fan_on = decide_bathroom_fan(
        humidity_input(bath_humidity=80),
        _heating(now),
        now=now,
        day_state="afternoon",
        last_fan_active_at=now,
        tuning=tuning,
    )
    assert fan_on.target_switch_state == "on"

    start = decide_bathroom_diffuser(fan_on, run_started_at=None, now=now, tuning=tuning)
    assert start.target_switch_state == "on"
    assert start.reason == "bath_diffuser_follows_fan"
    assert start.run_started_at == now

    capped = decide_bathroom_diffuser(
        fan_on,
        run_started_at=now - timedelta(minutes=tuning.diffuser_max_minutes + 1),
        now=now,
        tuning=tuning,
    )
    assert capped.target_switch_state == "off"
    assert capped.reason == "bath_diffuser_max_duration_reached"
    # Keeps the window so it does not restart while the fan keeps running.
    assert capped.run_started_at is not None

    fan_off = decide_bathroom_fan(
        humidity_input(bath_temp=21, bath_humidity=45, living_temp=21, living_humidity=45),
        _heating(now),
        now=now,
        day_state="afternoon",
        last_fan_active_at=now,
        tuning=tuning,
    )
    assert fan_off.target_switch_state == "off"
    off = decide_bathroom_diffuser(fan_off, run_started_at=start.run_started_at, now=now, tuning=tuning)
    assert off.target_switch_state == "off"
    assert off.reason == "bath_diffuser_fan_off"
    assert off.run_started_at is None
