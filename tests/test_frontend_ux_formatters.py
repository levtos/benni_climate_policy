from __future__ import annotations

import json
import subprocess


def _frontend_values() -> dict:
    script = r"""
// The fixture below expects Berlin local time, independent of the runner's TZ.
process.env.TZ = "Europe/Berlin";
const fs = require("fs");
const vm = require("vm");
const source = fs.readFileSync("custom_components/benni_climate_policy/frontend/app/main.js", "utf8");
const context = {
  console,
  setTimeout,
  clearTimeout,
  HTMLElement: class {
    attachShadow() {
      return {};
    }
  },
  customElements: {
    get() { return undefined; },
    define() {},
  },
};
vm.createContext(context);
vm.runInContext(source, context);
const values = {
  modeSpar: context.modeLabel("spar"),
  modeGround: context.modeLabel("grundwaerme"),
  fanAkut: context.fanModeLabel("akut"),
  fanAfterrun: context.fanModeLabel("afterrun"),
  fanStoss: context.fanModeLabel("stoss"),
  fanOff: context.fanModeLabel("off"),
  bathOverTargetReason: context.reasonLabel("Bath over target forces off"),
  safetyReason: context.reasonLabel("forced_safety_downshift"),
  effectiveLarge: context.effectiveOutdoorLabel("large"),
  effectiveChip: context.effectiveOutdoorLabel("chip"),
  weatherRainy: context.weatherConditionLabel("rainy"),
  weatherFallback: context.weatherConditionLabel("windy_variant"),
  rainyFeeling: context.outdoorFeelingFromParts({
    effectiveTemperature: 12.9,
    realTemperature: 13.2,
    weatherCondition: "rainy",
    outdoorLux: 900,
  }),
  humidFeeling: context.outdoorFeelingFromParts({
    effectiveTemperature: 25,
    realTemperature: 25,
    weatherCondition: "sunny",
    humidity: 72,
    outdoorLux: 28000,
  }),
  missingHumidityFeeling: context.outdoorFeelingFromParts({
    effectiveTemperature: 18,
    realTemperature: 18,
    weatherCondition: "rainy",
  }),
  localTimeDate: context.formatTimeDateLocal("2026-06-03T13:20:00+02:00"),
  neverApply: context.formatRelativeOrDateTime("never"),
  contextAwake: context.translateContextValue("bio_state", "awake"),
  contextParents: context.translateContextValue("presence_personal", "bei_eltern"),
  contextHousehold: context.translateContextValue("presence_household", "nicht_leer"),
  seasonSummer: context.seasonBandLabel("summer"),
};
const fakeHass = {
  states: {
    "binary_sensor.climate_system_ready": { state: "on", attributes: {} },
    "binary_sensor.climate_policy_apply_ready": { state: "on", attributes: {} },
    "switch.climate_policy_apply_active": { state: "on", attributes: {} },
    "sensor.climate_effective_outdoor_temperature": {
      state: "12.9",
      attributes: {
        effective_temperature: 12.9,
        inputs: {
          real_temperature: 13.2,
          weather_condition: "rainy",
          outdoor_lux: 900,
        },
      },
    },
    "sensor.climate_forecast_temperature_3h": { state: "13.0", attributes: {} },
    "sensor.climate_outdoor_feels_like_temperature": { state: "12.4", attributes: {} },
    "sensor.climate_policy_apply_status": { state: "applied", attributes: {} },
    "sensor.climate_policy_last_apply": { state: "never", attributes: {} },
    "sensor.bathroom_fan_mode": { state: "akut", attributes: {} },
    "sensor.benni_combined_openings": {
      state: "closed",
      attributes: {
        living_window_left: "closed",
        living_window_right: "closed",
        kitchen_patio_door: "closed",
      },
    },
  },
};
const fakeApp = {
  _debugPayload: {
    effective_outdoor_temperature: { effective_temperature: 12.9 },
    effective_inputs: { real_temperature: 13.2, weather_condition: "rainy", outdoor_lux: 900 },
    plans: {
      living_room: { profile: "off", reason: "window_blocks_heating", target_temperature: 10, policy_target_temperature: 10 },
      kitchen: { profile: "off", reason: "window_blocks_heating", target_temperature: 10, policy_target_temperature: 10 },
      bathroom: { profile: "off", reason: "bath_over_target_forces_off", target_temperature: 10, policy_target_temperature: 10 },
    },
    bathroom: {
      fan_plan: { mode: "akut", fan_reason: "bath_fan_acute_humidity_rise_or_threshold" },
    },
  },
};
values.overviewHtml = context.renderOverview(fakeHass, fakeApp);
values.overviewSentence = context.overviewSentence(fakeHass, fakeApp);
values.consequences = context.consequenceItems(fakeHass, fakeApp);
values.fanIndicator = context.heroIndicator(fakeHass, { _debugPayload: { bathroom: { fan_plan: { mode: "akut" } } } });
values.windowIndicator = context.heroIndicator({
  states: {
    ...fakeHass.states,
    "sensor.benni_combined_openings": {
      state: "tilted",
      attributes: {
        living_window_left: "closed",
        living_window_right: "tilted",
        kitchen_patio_door: "closed",
      },
    },
  },
}, { _debugPayload: {} });
values.safetyIndicator = context.heroIndicator(fakeHass, {
  _debugPayload: {
    debug: {
      last_apply_result: {
        actions: [{ reason: "forced_safety_downshift", details: { forced_safety_downshift: true } }],
      },
    },
  },
});
console.log(JSON.stringify(values));
"""
    result = subprocess.run(
        ["node", "-e", script],
        cwd=".",
        check=True,
        encoding="utf-8",
        capture_output=True,
    )
    return json.loads(result.stdout)


def test_mode_labels_are_centralized_for_visible_ux():
    values = _frontend_values()

    assert values["modeSpar"] == "Eco"
    assert values["modeGround"] == "Eco"


def test_fan_and_new_reason_labels_are_visible_ux():
    values = _frontend_values()

    assert values["fanAkut"] == "aktiv"
    assert values["fanAfterrun"] == "Nachlauf"
    assert values["fanStoss"] == "Stoßlüftung"
    assert values["fanOff"] == "Aus"
    assert values["bathOverTargetReason"] == "Bad ist warm genug, Heizung bleibt aus."
    assert values["safetyReason"] == "Sicherheitsabsenkung angewendet"


def test_effective_outdoor_temperature_uses_ux_labels():
    values = _frontend_values()

    assert values["effectiveLarge"] == "Heizrelevante Außentemperatur"
    assert values["effectiveChip"] == "Heizwert"


def test_weather_states_are_translated():
    values = _frontend_values()

    assert values["weatherRainy"] == "regnerisch"
    assert values["weatherFallback"] == "windig und bewölkt"


def test_outdoor_feeling_uses_weather_humidity_and_fallbacks():
    values = _frontend_values()

    assert "mild" not in values["rainyFeeling"]["outdoor_feeling_label"]
    assert any(
        word in values["rainyFeeling"]["outdoor_feeling_label"]
        for word in ("frisch", "regnerisch", "kühl")
    )
    assert any(
        word in values["humidFeeling"]["outdoor_feeling_label"]
        for word in ("schwül", "warm")
    )
    assert values["missingHumidityFeeling"]["outdoor_feeling_label"]
    assert values["missingHumidityFeeling"]["outdoor_feeling_parts"]["quality"] == "fallback"


def test_local_time_formatting_handles_iso_and_never():
    values = _frontend_values()

    assert "13:20 Uhr" in values["localTimeDate"]
    assert "03.06.2026" in values["localTimeDate"]
    assert values["neverApply"] == "Noch nie angewendet"


def test_context_and_season_labels_are_translated():
    values = _frontend_values()

    assert values["contextAwake"] == "Wach"
    assert values["contextParents"] == "Bei Eltern"
    assert values["contextHousehold"] == "Haushalt zuhause"
    assert values["seasonSummer"] == "Sommerpause"


def test_overview_uses_visible_bad_fan_labels_and_room_icon():
    values = _frontend_values()

    assert 'icon="mdi:home-group"' in values["overviewHtml"]
    assert "Räume im Plan" in values["overviewHtml"]
    assert "mini-stat-icon" in values["overviewHtml"]
    assert "Bad heizt nicht nach, Lüfter ist aktiv." in values["overviewSentence"]
    assert "Akut" not in values["overviewSentence"]
    assert "Bad · Aus" in values["consequences"]
    assert "Bad ist warm genug, kein Nachheizen nötig." in values["consequences"]
    assert "Badlüfter · aktiv" in values["consequences"]
    assert "Lüfter läuft wegen Feuchte/Taupunkt." in values["consequences"]


def test_hero_indicator_uses_state_priority_icons():
    values = _frontend_values()

    assert values["fanIndicator"]["icon"] == "mdi:fan-alert"
    assert values["windowIndicator"]["icon"] == "mdi:window-open-variant"
    assert values["safetyIndicator"]["icon"] == "mdi:shield-alert-outline"
