const DOMAIN = "benni_climate_policy";

const ENTITIES = {
  systemReady: "binary_sensor.climate_system_ready",
  applyReady: "binary_sensor.climate_policy_apply_ready",
  applyActive: "switch.climate_policy_apply_active",
  effectiveTemp: "sensor.climate_effective_outdoor_temperature",
  forecastTemp3h: "sensor.climate_forecast_temperature_3h",
  outdoorFeelsLike: "sensor.climate_outdoor_feels_like_temperature",
  applyStatus: "sensor.climate_policy_apply_status",
  lastApply: "sensor.climate_policy_last_apply",
  debugSummary: "sensor.climate_debug_summary",
  weatherCondition: "sensor.benni_device_weather_condition",
  contextPresencePersonal: "sensor.benni_combined_context_presence_personal",
  contextPresenceBand: "sensor.benni_combined_context_presence_band",
  contextPresenceHousehold: "sensor.benni_combined_context_presence_household",
  contextDayContext: "sensor.benni_combined_context_day_context",
  contextBioState: "sensor.benni_combined_context_bio_state",
  bathroomFanMode: "sensor.bathroom_fan_mode",
  bathroomFanPlanHash: "sensor.bathroom_fan_plan_hash",
  bathroomFanBlocked: "binary_sensor.bathroom_fan_apply_blocked",
};
const DEBUG_API_PATH = `${DOMAIN}/debug`;
const DEBUG_REFRESH_MS = 60000;
const DEBUG_VIEWS = new Set(["overview", "zones", "weather", "thresholds", "apply", "debug"]);
const JSON_CACHE = new WeakMap();

const ZONES = {
  living_room: {
    label: "Wohnzimmer",
    tempKey: "living_room_temperature",
    tempEntity: "sensor.benni_device_living_climate",
    mode: "sensor.living_room_climate_mode",
    target: "sensor.living_room_climate_target_temp",
    planHash: "sensor.living_room_climate_plan_hash",
    pendingHash: "sensor.living_room_climate_pending_plan_hash",
    lastAppliedHash: "sensor.living_room_climate_last_applied_plan_hash",
    applyReason: "sensor.living_room_climate_apply_reason",
    blocked: "binary_sensor.living_room_climate_apply_blocked",
  },
  kitchen: {
    label: "Küche",
    tempKey: "kitchen_temperature",
    tempEntity: "sensor.benni_device_kitchen_climate",
    mode: "sensor.kitchen_climate_mode",
    target: "sensor.kitchen_climate_target_temp",
    planHash: "sensor.kitchen_climate_plan_hash",
    pendingHash: "sensor.kitchen_climate_pending_plan_hash",
    lastAppliedHash: "sensor.kitchen_climate_last_applied_plan_hash",
    applyReason: "sensor.kitchen_climate_apply_reason",
    blocked: "binary_sensor.kitchen_climate_apply_blocked",
  },
  bathroom: {
    label: "Bad",
    tempKey: "bathroom_temperature",
    tempEntity: "sensor.benni_device_bath_climate",
    mode: "sensor.bathroom_climate_mode",
    target: "sensor.bathroom_climate_target_temp",
    planHash: "sensor.bathroom_climate_plan_hash",
    pendingHash: "sensor.bathroom_climate_pending_plan_hash",
    lastAppliedHash: "sensor.bathroom_climate_last_applied_plan_hash",
    applyReason: "sensor.bathroom_climate_apply_reason",
    blocked: "binary_sensor.bathroom_climate_apply_blocked",
  },
};

const LIVING_AREA_WINDOWS = [
  ["Wohnzimmerfenster links", "sensor.benni_combined_openings", "living_window_left"],
  ["Wohnzimmerfenster rechts", "sensor.benni_combined_openings", "living_window_right"],
  ["Terrassentür Küche", "sensor.benni_combined_openings", "kitchen_patio_door"],
];

const NAV = [
  ["overview", "Übersicht", "mdi:view-dashboard-outline"],
  ["zones", "Räume", "mdi:home-thermometer-outline"],
  ["weather", "Wetter", "mdi:weather-partly-cloudy"],
  ["apply", "Automatik", "mdi:toggle-switch-outline"],
  ["thresholds", "Tuning", "mdi:tune-vertical-variant"],
  ["debug", "Diagnose", "mdi:alert-circle-outline"],
];

const THRESHOLD_BANDS = [
  ["winter", "Winter", "Dez - Feb"],
  ["late_winter", "Spätwinter", "März"],
  ["spring", "Frühling", "April"],
  ["late_spring", "Frühsommer", "Mai"],
  ["summer", "Sommerpause", "Jun - Aug"],
  ["early_autumn", "Spätsommer", "September"],
  ["autumn", "Herbst", "Oktober"],
  ["late_autumn", "Vorwinter", "November"],
];

const TUNING_GROUPS = [
  ["setpoints", "Setpoints", "mdi:thermostat", [
    ["setpoint_off", "Off"],
    ["setpoint_spar", "Eco"],
    ["setpoint_komfort", "Komfort"],
    ["setpoint_boost", "Boost"],
  ]],
  ["effective", "Heizrelevante Außentemperatur", "mdi:thermometer-lines", [
    ["floor_slab_tau", "Bodenplatten-Tau"],
    ["lux_bonus_max", "Maximaler Lux-Bonus"],
    ["lux_reference", "Lux-Referenz"],
    ["feels_like_damping", "Dämpfung gefühlte Temperatur"],
    ["forecast_weight", "Forecast-Gewichtung"],
  ]],
  ["floor_slab", "Bodenplatten-Delta", "mdi:layers-triple-outline", [
    ["floor_slab_mode", "Modus"],
    ["floor_slab_min_delta", "Min. Delta"],
    ["floor_slab_max_delta", "Max. Delta"],
    ["floor_slab_anchor_warm_index", "Warm ab Index"],
    ["floor_slab_anchor_warm_delta", "Warm Delta"],
    ["floor_slab_anchor_mild_index", "Mild Index"],
    ["floor_slab_anchor_mild_delta", "Mild Delta"],
    ["floor_slab_anchor_cool_index", "Kühl Index"],
    ["floor_slab_anchor_cool_delta", "Kühl Delta"],
    ["floor_slab_anchor_cold_index", "Kalt Index"],
    ["floor_slab_anchor_cold_delta", "Kalt Delta"],
    ["floor_slab_anchor_freezing_index", "Frost Index"],
    ["floor_slab_anchor_freezing_delta", "Frost Delta"],
  ]],
  ["indoor_living", "Innenbedarf Wohnbereich", "mdi:home-thermometer-outline", [
    ["indoor_living_area_spar_heat_on_below", "Eco einschalten unter"],
    ["indoor_living_area_spar_heat_off_at", "Eco ausschalten ab"],
    ["indoor_living_area_spar_min_hold_minutes", "Eco Mindestdauer"],
    ["indoor_living_area_komfort_heat_on_below", "Komfort einschalten unter"],
    ["indoor_living_area_komfort_heat_off_at", "Komfort ausschalten ab"],
    ["indoor_living_area_komfort_min_hold_minutes", "Komfort Mindestdauer"],
    ["indoor_living_area_boost_heat_on_below", "Boost einschalten unter"],
    ["indoor_living_area_boost_heat_off_at", "Boost ausschalten ab"],
    ["indoor_living_area_boost_min_hold_minutes", "Boost Mindestdauer"],
  ]],
  ["indoor_bathroom", "Innenbedarf Bad", "mdi:bathtub-outline", [
    ["indoor_bathroom_grundwaerme_heat_on_below", "Eco einschalten unter"],
    ["indoor_bathroom_grundwaerme_heat_off_at", "Eco ausschalten ab"],
    ["indoor_bathroom_grundwaerme_min_hold_minutes", "Eco Mindestdauer"],
    ["indoor_bathroom_komfort_heat_on_below", "Komfort einschalten unter"],
    ["indoor_bathroom_komfort_heat_off_at", "Komfort ausschalten ab"],
    ["indoor_bathroom_komfort_min_hold_minutes", "Komfort Mindestdauer"],
  ]],
  ["boost", "Boost", "mdi:rocket-launch-outline", [
    ["boost_delta", "Boost-Delta"],
    ["boost_activation_delta", "Aktivierungsdelta zum Raum"],
  ]],
  ["apply", "Apply", "mdi:timer-sand", [
    ["apply_cooldown_seconds", "Apply-Cooldown"],
    ["startup_block_seconds", "Startup-Ruhezeit"],
  ]],
  ["bath", "Bad", "mdi:shower-head", [
    ["bath_setpoint_protection", "Schutz-Setpoint"],
    ["bath_setpoint_ground", "Bad Eco-Setpoint"],
    ["bath_setpoint_comfort", "Komfort-Setpoint"],
    ["bath_comfort_suppression_teff", "Komfort bis Heizwert"],
    ["bath_humidity_acute_threshold", "Aktiv-Luftfeuchte"],
    ["bath_humidity_acute_rise_threshold", "Aktiv-Anstieg 5 Min."],
    ["bath_humidity_end_threshold", "End-Luftfeuchte"],
    ["bath_dewpoint_acute_threshold", "Aktiv-Taupunkt"],
    ["bath_humidity_ground_heat_threshold", "Grundwärme Feuchte"],
    ["bath_dewpoint_ground_heat_threshold", "Grundwärme Taupunkt"],
    ["bath_humidity_ground_heat_teff_limit", "Grundwärme bis Heizwert"],
    ["bath_humidity_ground_heat_target", "Grundwärme Feuchte-Ziel"],
    ["bath_humidity_ground_heat_off_at", "Grundwärme Feuchte aus ab"],
    ["bath_ah_delta_afterrun_on", "Nachlauf ab AH-Delta"],
    ["bath_ah_delta_afterrun_off", "Nachlauf Ende AH-Delta"],
    ["bath_ah_delta_stoss", "Stoßlüftung AH-Delta"],
    ["bath_fan_heat_coordination_delta", "Heiz-/Lüfter-Delta"],
    ["bath_fan_acute_max_minutes", "Aktiv max. Minuten"],
    ["bath_fan_afterrun_max_minutes", "Nachlauf max. Minuten"],
    ["bath_fan_stoss_interval_hours", "Stoßlüftung Intervall"],
    ["bath_fan_stoss_duration_minutes", "Stoßlüftung Dauer"],
    ["bath_fan_hard_cap_minutes", "Harte Laufzeitgrenze (gegen 24/7)"],
    ["bath_fan_cooldown_minutes", "Cooldown-Sperre nach Grenze"],
    ["bath_diffuser_max_minutes", "Diffuser max. Minuten"],
  ]],
];

const CSS = `
:host, * { box-sizing: border-box; }
:host {
  --bcp-bg: #070b1c;
  --bcp-surface: rgba(27, 31, 54, .86);
  --bcp-surface-strong: rgba(35, 40, 70, .94);
  --bcp-panel: #0d1228;
  --bcp-panel-soft: rgba(17, 23, 47, .82);
  --bcp-line: rgba(151, 161, 208, .18);
  --bcp-text: #f5f6ff;
  --bcp-muted: #b5bad6;
  --bcp-faint: #7c83aa;
  --bcp-accent: #22c7ff;
  --bcp-purple: #a56cff;
  --bcp-pink: #ff62b7;
  --bcp-green: #50fa7b;
  --bcp-blue: #45a6ff;
  --bcp-cyan: #00e5ff;
  --bcp-yellow: #f1fa8c;
  --bcp-ok: #50fa7b;
  --bcp-warn: #ffb86c;
  --bcp-error: #ff5555;
  --bcp-info: #45a6ff;
  display: block;
  min-height: 100vh;
  color: var(--bcp-text);
  font-family: var(--paper-font-body1_-_font-family, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif);
}
.app {
  display: grid;
  grid-template-columns: 250px minmax(0, 1fr);
  min-height: 100vh;
  background:
    radial-gradient(circle at 78% 6%, rgba(34, 199, 255, .11), transparent 28%),
    linear-gradient(135deg, #070b1c 0%, #10142a 52%, #090d20 100%);
}
.sidebar {
  border-right: 1px solid var(--bcp-line);
  background: linear-gradient(180deg, rgba(12, 17, 36, .96), rgba(8, 12, 28, .98));
  padding: 24px 14px;
  display: flex;
  flex-direction: column;
  gap: 24px;
}
.brand { display: grid; grid-template-columns: 46px 1fr; gap: 12px; align-items: center; padding: 0 4px 10px; }
.brand-badge {
  display: grid;
  place-items: center;
  width: 46px;
  height: 46px;
  border-radius: 8px;
  background: linear-gradient(135deg, var(--bcp-purple), var(--bcp-accent));
  color: #08111f;
  box-shadow: 0 14px 34px rgba(34, 199, 255, .22);
}
.brand b { display: block; font-size: 16px; line-height: 1.2; }
.brand small { color: var(--bcp-muted); font-size: 12px; }
.nav { display: flex; flex-direction: column; gap: 8px; }
.nav button {
  display: grid;
  grid-template-columns: 24px 1fr;
  gap: 12px;
  align-items: center;
  width: 100%;
  min-height: 44px;
  border: 1px solid transparent;
  border-radius: 8px;
  padding: 9px 12px;
  background: transparent;
  color: var(--bcp-muted);
  text-align: left;
  cursor: pointer;
  font: inherit;
}
.nav button:hover { background: rgba(255, 255, 255, .04); color: var(--bcp-text); }
.nav button.active {
  background: linear-gradient(90deg, rgba(165, 108, 255, .30), rgba(34, 199, 255, .09));
  border-color: rgba(165, 108, 255, .24);
  color: var(--bcp-accent);
  font-weight: 700;
}
.side-foot {
  margin-top: auto;
  border-top: 1px solid var(--bcp-line);
  padding: 18px 8px 0;
  color: var(--bcp-muted);
  font-size: 12px;
  overflow-wrap: anywhere;
}
.side-status { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; color: var(--bcp-text); }
.main { min-width: 0; padding: 24px 28px 32px; }
.head { display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; margin-bottom: 20px; }
.head h1 { margin: 0; font-size: 28px; line-height: 1.1; letter-spacing: 0; }
.head p { margin: 6px 0 0; color: var(--bcp-muted); font-size: 14px; }
.chips { display: flex; gap: 10px; flex-wrap: wrap; justify-content: flex-end; }
.grid { display: grid; gap: 16px; }
.cols-2 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.cols-3 { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.cols-4 { grid-template-columns: repeat(4, minmax(0, 1fr)); }
.section { margin-top: 18px; }
.card, .metric, .hero, .info-band {
  background: linear-gradient(145deg, rgba(31, 36, 62, .92), rgba(18, 23, 45, .86));
  border: 1px solid var(--bcp-line);
  border-radius: 8px;
  box-shadow: inset 0 1px 0 rgba(255,255,255,.03), 0 22px 60px rgba(0,0,0,.18);
}
.card { padding: 18px; min-width: 0; }
.card h2 { margin: 0 0 14px; font-size: 16px; display: flex; gap: 10px; align-items: center; }
.card h2 ha-icon { color: var(--bcp-accent); }
.hero {
  min-height: 250px;
  padding: 34px 38px;
  display: grid;
  grid-template-columns: 150px minmax(0, 1fr) 320px;
  gap: 26px;
  align-items: center;
  overflow: hidden;
  position: relative;
}
.hero::after {
  display: none;
}
.hero-icon, .round-icon, .mini-stat-icon {
  display: grid;
  place-items: center;
  flex: 0 0 auto;
  width: 106px;
  height: 106px;
  border-radius: 50%;
  background: radial-gradient(circle at 36% 25%, rgba(165, 108, 255, .75), rgba(34, 199, 255, .22) 66%, rgba(34, 199, 255, .06));
}
.hero-icon ha-icon { --mdc-icon-size: 58px; color: var(--bcp-accent); }
.hero-icon small { display: block; max-width: 120px; margin-top: 6px; color: var(--bcp-muted); font-size: 11px; line-height: 1.25; text-align: center; }
.hero h2 { margin: 0; font-size: 30px; line-height: 1.28; max-width: 760px; }
.hero p { color: var(--bcp-muted); margin: 14px 0 20px; font-size: 15px; }
.hero .accent { color: var(--bcp-accent); }
.hero .pink { color: var(--bcp-pink); }
.hero .purple { color: var(--bcp-purple); }
.hero-side { position: relative; z-index: 1; align-self: stretch; display: flex; align-items: flex-start; justify-content: flex-end; }
.cloud-temp {
  margin-top: 18px;
  padding: 18px 24px;
  border-radius: 999px;
  background: rgba(46, 43, 95, .62);
  color: #8aa6ff;
  font-size: 30px;
  font-weight: 800;
}
.weather-chip { display: block; margin-top: 10px; color: var(--bcp-muted); text-align: right; }
.metric { padding: 16px 18px; min-height: 96px; }
.metric .label { color: var(--bcp-muted); font-size: 13px; margin-bottom: 8px; }
.metric .value { font-size: 22px; font-weight: 800; overflow-wrap: anywhere; }
.metric .entity { margin-top: 7px; color: var(--bcp-faint); font-size: 11px; font-family: ui-monospace, "Cascadia Code", monospace; overflow-wrap: anywhere; }
.mini-stat { display: flex; gap: 14px; align-items: center; min-width: 0; }
.mini-stat-icon { width: 42px; height: 42px; border-radius: 8px; background: rgba(34, 199, 255, .12); }
.mini-stat-icon ha-icon { color: var(--bcp-accent); --mdc-icon-size: 26px; }
.mini-stat b { display: block; font-size: 20px; }
.mini-stat span { color: var(--bcp-muted); font-size: 12px; }
.room-card { padding: 22px; min-height: 360px; display: flex; flex-direction: column; }
.room-head { display: grid; grid-template-columns: 64px 1fr auto; gap: 16px; align-items: start; margin-bottom: 22px; }
.room-icon {
  display: grid;
  place-items: center;
  width: 58px;
  height: 58px;
  border-radius: 50%;
  background: linear-gradient(135deg, rgba(165, 108, 255, .72), rgba(34, 199, 255, .22));
}
.room-icon ha-icon { --mdc-icon-size: 34px; color: var(--bcp-text); }
.room-card h3 { margin: 0; font-size: 21px; }
.mode { color: var(--bcp-purple); font-size: 20px; font-weight: 800; }
.target { color: var(--bcp-accent); font-size: 28px; font-weight: 850; white-space: nowrap; }
.reason { display: grid; grid-template-columns: 28px 1fr; gap: 12px; align-items: start; margin: 16px 0; }
.reason ha-icon { color: var(--bcp-accent); }
.reason small { display: block; color: var(--bcp-muted); margin-bottom: 4px; }
.room-facts { margin-top: auto; border-top: 1px solid var(--bcp-line); padding-top: 12px; }
.fact-row { display: flex; justify-content: space-between; gap: 12px; padding: 8px 0; color: var(--bcp-muted); }
.fact-row b { color: var(--bcp-text); font-weight: 600; text-align: right; }
.chip-row { display: flex; flex-wrap: wrap; gap: 8px; }
.status, .pill {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  border: 1px solid var(--bcp-line);
  border-radius: 999px;
  padding: 5px 11px;
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
  background: rgba(8, 12, 28, .28);
}
.status::before { content: ""; width: 8px; height: 8px; border-radius: 50%; background: currentColor; box-shadow: 0 0 14px currentColor; }
.ok { color: var(--bcp-ok); }
.warn { color: var(--bcp-warn); }
.error { color: var(--bcp-error); }
.info { color: var(--bcp-info); }
.pill.green { color: var(--bcp-green); border-color: rgba(80, 250, 123, .26); background: rgba(80, 250, 123, .10); }
.pill.blue { color: var(--bcp-blue); border-color: rgba(69, 166, 255, .26); background: rgba(69, 166, 255, .10); }
.pill.purple { color: var(--bcp-purple); border-color: rgba(165, 108, 255, .30); background: rgba(165, 108, 255, .12); }
.pill.pink { color: var(--bcp-pink); border-color: rgba(255, 98, 183, .28); background: rgba(255, 98, 183, .11); }
.kv { display: grid; grid-template-columns: minmax(145px, .65fr) minmax(0, 1fr); gap: 12px; padding: 8px 0; border-bottom: 1px solid var(--bcp-line); }
.kv:last-child { border-bottom: 0; }
.k { color: var(--bcp-muted); font-size: 13px; }
.v { font-size: 13px; font-weight: 650; min-width: 0; overflow-wrap: anywhere; }
.mono { font-family: ui-monospace, "Cascadia Code", monospace; font-size: 12px; }
.muted { color: var(--bcp-muted); }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 10px 11px; border-bottom: 1px solid var(--bcp-line); text-align: left; vertical-align: top; font-size: 13px; }
th { color: var(--bcp-muted); font-size: 12px; font-weight: 750; }
.table-wrap { overflow-x: auto; }
.pre {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  background: rgba(6, 10, 24, .78);
  border: 1px solid var(--bcp-line);
  border-radius: 8px;
  padding: 12px;
  max-height: 340px;
  min-height: 96px;
  overflow: auto;
  scrollbar-gutter: stable;
  contain: content;
}
.json-details, .expert { border: 1px solid var(--bcp-line); border-radius: 8px; padding: 12px 14px; background: rgba(8, 12, 28, .22); }
.json-details summary, .expert summary { cursor: pointer; color: var(--bcp-muted); font-size: 13px; }
.json-details[open] summary, .expert[open] summary { margin-bottom: 10px; }
.apply-summary { min-width: 760px; }
.apply-summary td, .apply-summary th { vertical-align: middle; }
.actions { display: flex; flex-wrap: wrap; gap: 10px; }
button.action {
  display: inline-grid;
  grid-template-columns: 18px auto;
  gap: 8px;
  align-items: center;
  min-height: 40px;
  border: 1px solid var(--bcp-line);
  border-radius: 8px;
  background: rgba(255, 255, 255, .04);
  color: var(--bcp-text);
  padding: 9px 13px;
  cursor: pointer;
  font: inherit;
}
button.action:hover { border-color: rgba(34, 199, 255, .6); }
button.action.primary {
  background: linear-gradient(135deg, var(--bcp-purple), var(--bcp-accent));
  color: #ffffff;
  border-color: transparent;
}
button.action[disabled] { opacity: .48; cursor: not-allowed; }
.tuning-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 16px; }
.season-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
.season-card { padding: 14px; border: 1px solid var(--bcp-line); border-radius: 8px; background: rgba(255,255,255,.035); }
.season-card.active { border-color: rgba(165, 108, 255, .78); box-shadow: 0 0 0 1px rgba(165, 108, 255, .18); }
.season-card h3 { margin: 0 0 4px; font-size: 15px; }
.season-card small { color: var(--bcp-muted); }
.season-values { display: grid; gap: 8px; margin: 14px 0; }
.season-values label { display: grid; grid-template-columns: 1fr 96px; gap: 8px; align-items: center; color: var(--bcp-muted); font-size: 12px; }
.field-row { display: grid; grid-template-columns: minmax(128px, 1fr) 112px; gap: 10px; align-items: center; padding: 9px 0; border-bottom: 1px solid var(--bcp-line); }
.field-row:last-child { border-bottom: 0; }
.field-row.dirty, tr.dirty, .season-card.dirty { background: rgba(255, 184, 108, .08); }
.field-row input, .matrix input, .season-card input {
  min-height: 34px;
  border: 1px solid var(--bcp-line);
  border-radius: 8px;
  padding: 6px 8px;
  background: rgba(7, 11, 28, .8);
  color: var(--bcp-text);
  font: inherit;
}
.field-row input:disabled, .matrix input:disabled, .season-card input:disabled { opacity: .55; background: rgba(8, 12, 28, .45); }
.source-pill { display: inline-flex; align-items: center; border: 1px solid var(--bcp-line); border-radius: 999px; padding: 2px 7px; font-size: 11px; color: var(--bcp-muted); white-space: nowrap; }
.source-pill.user { color: var(--bcp-info); border-color: rgba(69, 166, 255, .38); }
.toolbar { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 14px; }
.segmented { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 16px; }
.segmented button {
  border: 1px solid var(--bcp-line);
  border-radius: 8px;
  background: rgba(255, 255, 255, .04);
  color: var(--bcp-muted);
  padding: 9px 12px;
  cursor: pointer;
  font: inherit;
}
.segmented button.active { color: var(--bcp-accent); border-color: rgba(34, 199, 255, .5); background: rgba(34, 199, 255, .10); }
.matrix { min-width: 980px; }
.matrix input[type="number"] { width: 92px; }
.diagnostics-package { width: 100%; min-height: 260px; resize: vertical; margin-top: 12px; }
.error-box { border: 1px solid rgba(255, 85, 85, .55); background: rgba(255, 85, 85, .10); color: var(--bcp-error); border-radius: 8px; padding: 10px 12px; margin-bottom: 12px; }
.notice { border: 1px dashed var(--bcp-line); border-radius: 8px; padding: 14px; color: var(--bcp-muted); background: rgba(255, 255, 255, .035); }
.info-band { padding: 18px 20px; display: grid; grid-template-columns: 44px 1fr auto; gap: 16px; align-items: center; }
.info-band ha-icon { color: var(--bcp-accent); --mdc-icon-size: 30px; }
.info-band b { display: block; margin-bottom: 4px; }
.apply-hero { grid-column: span 2; }
.toast { position: fixed; left: 50%; bottom: 20px; transform: translateX(-50%); background: var(--bcp-surface-strong); border: 1px solid var(--bcp-line);
  border-radius: 8px; padding: 10px 14px; box-shadow: 0 10px 30px rgba(0,0,0,.32); z-index: 10; }
@media (max-width: 1220px) {
  .hero { grid-template-columns: 116px minmax(0, 1fr); }
  .hero-side { display: none; }
  .cols-4, .tuning-grid, .season-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 820px) {
  .app { grid-template-columns: 1fr; }
  .sidebar { border-right: 0; border-bottom: 1px solid var(--bcp-line); padding: 16px 14px; }
  .nav { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .side-foot { display: none; }
  .main { padding: 18px 14px 26px; }
  .head { display: block; }
  .head h1 { font-size: 24px; }
  .chips { justify-content: flex-start; margin-top: 12px; }
  .hero { grid-template-columns: 1fr; padding: 24px 20px; min-height: 0; }
  .hero-icon { width: 82px; height: 82px; }
  .hero h2 { font-size: 24px; }
  .cols-2, .cols-3, .cols-4, .tuning-grid, .season-grid { grid-template-columns: 1fr; }
  .room-head { grid-template-columns: 52px 1fr; }
  .apply-hero { grid-column: auto; }
  .target { grid-column: 2; font-size: 24px; }
  .kv, .field-row, .season-values label, .info-band { grid-template-columns: 1fr; gap: 6px; }
}
`;

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function asText(value, missing = "missing") {
  if (value === undefined || value === null || value === "") return missing;
  if (Array.isArray(value)) return value.length ? value.join(", ") : "none";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function stateObj(hass, entityId) {
  return hass && entityId ? hass.states[entityId] : undefined;
}

function stateText(hass, entityId, missing = "missing") {
  const st = stateObj(hass, entityId);
  return st ? st.state : missing;
}

function attr(hass, entityId, name, missing = undefined) {
  const st = stateObj(hass, entityId);
  return st && st.attributes && st.attributes[name] !== undefined ? st.attributes[name] : missing;
}

function debugAttrs(hass) {
  return (stateObj(hass, ENTITIES.debugSummary) || {}).attributes || {};
}

function endpointDebug(app) {
  return app?._debugPayload || {};
}

function debugPayload(hass, app) {
  return endpointDebug(app).debug || {};
}

function plans(hass, app) {
  return endpointDebug(app).plans || {};
}

function contextSnapshot(hass, app) {
  return endpointDebug(app).context || {};
}

function effectiveBreakdown(hass, app) {
  const fromDebug = endpointDebug(app).effective_outdoor_temperature || {};
  const fromSensor = (stateObj(hass, ENTITIES.effectiveTemp) || {}).attributes || {};
  return { ...fromDebug, ...fromSensor };
}

function effectiveInputs(hass, app) {
  const fromDebug = endpointDebug(app).effective_inputs || debugPayload(hass, app).effective_inputs || {};
  const fromSensor = attr(hass, ENTITIES.effectiveTemp, "inputs", {}) || {};
  return { ...fromDebug, ...fromSensor };
}

function thresholds(hass, app) {
  return endpointDebug(app).thresholds || debugPayload(hass, app).thresholds || {};
}

function tuningOptions(hass, app) {
  return endpointDebug(app).tuning_options || debugPayload(hass, app).tuning_options || {};
}

function bathroomDebug(hass, app) {
  return endpointDebug(app).bathroom || debugPayload(hass, app).bathroom || {};
}

function statusKind(value) {
  if (value === true || value === "on" || value === "ok" || value === "applied") return "ok";
  if (value === false || value === "off" || value === "idle" || value === "skipped" || value === "dry_run") return "info";
  if (value === "missing" || value === "unknown" || value === "unavailable" || value === "blocked") return "warn";
  if (value === "error") return "error";
  return "info";
}

function statusChip(value, label = value) {
  return `<span class="status ${statusKind(value)}">${esc(label)}</span>`;
}

function icon(name) {
  return `<ha-icon icon="${esc(name)}"></ha-icon>`;
}

function kv(label, value, cls = "") {
  return `<div class="kv"><div class="k">${esc(label)}</div><div class="v ${cls}">${esc(asText(value))}</div></div>`;
}

function kvSource(label, value, source, cls = "") {
  return `<div class="kv"><div class="k">${esc(label)}<br><span class="muted">${esc(source || "default")}</span></div><div class="v ${cls}">${esc(asText(value))}</div></div>`;
}

function metric(label, value, entityId = "") {
  return `<div class="metric"><div class="label">${esc(label)}</div><div class="value">${esc(asText(value))}</div>${entityId ? `<div class="entity">${esc(entityId)}</div>` : ""}</div>`;
}

function jsonBlock(value) {
  const normalized = value ?? null;
  if (normalized && typeof normalized === "object") {
    const cached = JSON_CACHE.get(normalized);
    if (cached !== undefined) return `<div class="pre mono">${cached}</div>`;
    const text = esc(JSON.stringify(normalized, null, 2));
    JSON_CACHE.set(normalized, text);
    return `<div class="pre mono">${text}</div>`;
  }
  return `<div class="pre mono">${esc(JSON.stringify(normalized, null, 2))}</div>`;
}

function jsonDetails(summary, value) {
  return `<details class="json-details"><summary>${esc(summary)}</summary>${jsonBlock(value)}</details>`;
}

function plannedFromCalls(action, key) {
  const calls = Array.isArray(action?.service_calls) ? action.service_calls : [];
  for (const call of calls) {
    const data = call.service_data || {};
    if (key === "planned_hvac_mode" && call.service === "set_hvac_mode") return data.hvac_mode;
    if (key === "planned_temperature" && call.service === "set_temperature") return data.temperature;
  }
  return action?.details?.[key] ?? null;
}

function startupBlockNotice(actions) {
  return actions.some((action) => action?.details?.gate_reason === "startup_quiet_period")
    ? `<div class="notice">Blockiert durch Start-Ruhephase</div>`
    : "";
}

function renderApplySummary(lastApply) {
  const actions = Array.isArray(lastApply?.actions) ? lastApply.actions : [];
  if (!actions.length) return `<div class="notice">Noch kein Apply- oder Dry-Run-Ergebnis vorhanden.</div>`;
  const rows = actions.map((action) => {
    const gateReason = action.details?.gate_reason || action.details?.gate_status || "none";
    return `<tr>
      <td class="mono">${esc(action.zone)}</td>
      <td>${statusChip(action.status, reasonLabel(action.status))}</td>
      <td class="mono">${esc(reasonLabel(action.reason || "missing"))}</td>
      <td class="mono">${esc(reasonLabel(gateReason))}</td>
      <td class="mono">${esc(action.target_entity_id || "missing")}</td>
      <td class="mono">${esc(asText(plannedFromCalls(action, "planned_hvac_mode"), "none"))}</td>
      <td class="mono">${esc(asText(plannedFromCalls(action, "planned_temperature"), "none"))}</td>
    </tr>`;
  }).join("");
  return `${startupBlockNotice(actions)}<div class="table-wrap"><table class="apply-summary">
    <thead><tr><th>Zone</th><th>Status</th><th>Reason</th><th>Gate</th><th>Target Entity</th><th>HVAC Mode</th><th>Temperatur</th></tr></thead>
    <tbody>${rows}</tbody>
  </table></div>`;
}

function debugEndpointNotice(app) {
  const message = app?._debugError
    ? `Debug-Endpunkt nicht erreichbar: ${app._debugError}`
    : "Debug-Daten werden geladen oder sind noch nicht verfügbar.";
  return `<div class="notice">${esc(message)}</div>`;
}

function serviceAvailable(hass, service) {
  return Boolean(hass && hass.services && hass.services[DOMAIN] && hass.services[DOMAIN][service]);
}

function entityAvailable(hass, entityId) {
  return Boolean(stateObj(hass, entityId));
}

function zonePlan(hass, zone, app) {
  const plan = plans(hass, app)[zone] || {};
  const z = ZONES[zone];
  return {
    ...plan,
    profile: plan.profile ?? stateText(hass, z.mode),
    target_temperature: plan.target_temperature ?? stateText(hass, z.target),
    plan_hash: plan.plan_hash ?? stateText(hass, z.planHash),
    pending_plan_hash: stateText(hass, z.pendingHash, plan.plan_hash ?? "missing"),
    last_applied_plan_hash: stateText(hass, z.lastAppliedHash, "never"),
    apply_blocked: stateText(hass, z.blocked, "missing"),
    apply_reason: stateText(hass, z.applyReason, plan.apply_block_reason ?? "missing"),
  };
}

function inputItems(hass, app) {
  return endpointDebug(app).inputs || debugPayload(hass, app).inputs || [];
}

function inputItem(app, key) {
  const inputs = endpointDebug(app).inputs || debugPayload(null, app).inputs || [];
  return inputs.find((item) => item?.key === key) || null;
}

function zoneRoomTemperature(hass, app, zone) {
  const meta = ZONES[zone] || {};
  const fromInput = inputItem(app, meta.tempKey);
  if (fromInput) {
    if (fromInput.status === "ok") return tempText(fromInput.state, "nicht konfiguriert");
    return fromInput.status || "nicht konfiguriert";
  }
  const entityId = meta.tempEntity;
  if (!entityId) return "nicht konfiguriert";
  const state = stateObj(hass, entityId);
  if (!state) return "nicht konfiguriert";
  return tempText(state.state, state.state || "unavailable");
}

const UX_LABELS = {
  modes: {
    off: "Aus",
    aus: "Aus",
    spar: "Eco",
    eco: "Eco",
    comfort: "Komfort",
    komfort: "Komfort",
    boost: "Boost",
    ground: "Eco",
    ground_heat: "Eco",
    grundwaerme: "Eco",
    grundwärme: "Eco",
    protection: "Schutz",
  },
  weather: {
    clear: "klar",
    clear_night: "klare Nacht",
    sunny: "sonnig",
    partlycloudy: "leicht bewölkt",
    cloudy: "bewölkt",
    overcast: "bedeckt",
    rainy: "regnerisch",
    pouring: "starker Regen",
    lightning: "Gewitter",
    lightning_rainy: "Gewitterregen",
    lightning_rainy_alt: "Gewitterregen",
    snowy: "Schnee",
    snowy_rainy: "Schneeregen",
    fog: "neblig",
    windy: "windig",
    windy_variant: "windig und bewölkt",
    exceptional: "außergewöhnlich",
  },
  context: {
    awake: "Wach",
    active: "Aktiv",
    asleep: "Schlafend",
    sleep: "Schlafend",
    sleeping: "Schlafend",
    tired: "Müde",
    free_time: "Freizeit",
    work: "Arbeit",
    workday: "Werktag",
    weekday: "Werktag",
    werktag: "Werktag",
    weekend: "Wochenende",
    wochenende: "Wochenende",
    holiday: "Feiertag",
    forenoon: "Vormittag",
    fore_noon: "Vormittag",
    afternoon: "Nachmittag",
    evening: "Abend",
    night: "Nacht",
    early_night: "Frühe Nacht",
    late_night: "Späte Nacht",
    home: "Zuhause",
    zuhause: "Zuhause",
    present: "Zuhause",
    daheim: "Zuhause",
    bei_eltern: "Bei Eltern",
    nicht_leer: "Haushalt zuhause",
    not_empty: "Haushalt zuhause",
    occupied: "Haushalt zuhause",
    leer: "Niemand zuhause",
    empty: "Niemand zuhause",
    away: "Niemand zuhause",
    not_home: "Niemand zuhause",
    none: "Keine",
    off: "Aus",
  },
  seasons: {
    winter: "Winter",
    late_winter: "Spätwinter",
    spring: "Frühling",
    late_spring: "Frühsommer",
    summer: "Sommerpause",
    early_autumn: "Spätsommer",
    autumn: "Herbst",
    late_autumn: "Vorwinter",
  },
  reasons: {
    blocked: "blockiert",
    cooldown_active: "Cooldown aktiv",
    already_at_target: "bereits am Ziel",
    skipped_already_at_target: "bereits am Ziel",
    forced_safety_downshift: "Sicherheitsabsenkung angewendet",
    none: "Keine",
    no_apply_needed: "kein Apply nötig",
    applied: "angewendet",
    failed_entity_unavailable: "Entity nicht verfügbar",
    window_blocks_heating: "Fenster blockiert Heizen",
    room_temperature_above_target_no_heating: "Raum warm genug, kein Nachheizen nötig.",
    living_area_temperature_above_target_no_heating: "Wohnbereich warm genug, kein Nachheizen nötig.",
    no_heat_demand: "Kein Wärmebedarf",
    room_temperature_above_heat_off_at: "Raum über Ausschaltgrenze",
    room_temperature_below_heat_on_below: "Raum unter Einschaltgrenze",
    indoor_hysteresis_holds_off: "Innen-Hysterese hält aus",
    indoor_hysteresis_holds_heat: "Innen-Hysterese hält Heizen",
    indoor_hysteresis_initial_allows_heat: "Innenbedarf wird initial freigegeben",
    room_temperature_missing_allows_candidate: "Raumtemperatur fehlt, erlaubte Stufe bleibt aktiv",
    dynamic_3day_cold_index: "Dynamischer 3-Tage-Kälteindex",
    dynamic_floor_slab_partial_inputs: "Dynamisches Delta mit Teilwerten",
    floor_slab_temperature_inputs_missing: "Bodenplattenwerte fehlen, statischer Fallback",
    static_floor_slab_mode: "Statischer Bodenplattenmodus",
    computed_from_raw_temperature_humidity_wind: "Aus Rohwerten berechnet",
    raw_humidity_or_wind_missing: "Rohwerte fehlen, reale Außentemperatur genutzt",
    bath_ground_heat_default: "Mindestwärme gegen Auskühlung und Feuchte",
    bath_humidity_ground_heat: "Feuchteschutz hält die Bad-Grundwärme aktiv.",
    bath_humidity_ground_heat_overrides_indoor_hysteresis: "Feuchteschutz überstimmt die Innen-Hysterese.",
    bath_over_target_forces_off: "Bad ist warm genug, Heizung bleibt aus.",
    bath_temperature_above_target_no_heating: "Bad über Zieltemperatur, kein Nachheizen nötig.",
    living_area_window_or_door_open_or_tilted: "Wohnbereich blockiert: Fenster/Tür offen oder gekippt.",
  },
  fanModes: {
    akut: "aktiv",
    acute: "aktiv",
    active: "aktiv",
    aktiv: "aktiv",
    afterrun: "Nachlauf",
    nachlauf: "Nachlauf",
    stoss: "Stoßlüftung",
    stoß: "Stoßlüftung",
    stoßlüftung: "Stoßlüftung",
    stosslueftung: "Stoßlüftung",
    off: "Aus",
    aus: "Aus",
    idle: "Aus",
  },
  effectiveOutdoor: {
    large: "Heizrelevante Außentemperatur",
    chip: "Heizwert",
    technical: "Teff / effective_outdoor_temperature",
    explanation: "Berechnet aus realer Temperatur, Wetter, Prognose, Sonneneinstrahlung und Korrekturen.",
  },
};

function normalizeUxKey(value) {
  return String(value ?? "")
    .trim()
    .toLowerCase()
    .replaceAll("-", "_")
    .replaceAll(" ", "_");
}

function readableFallback(value, missing = "Unbekannt") {
  const text = asText(value, "");
  if (!text || ["missing", "unknown", "unavailable"].includes(text.toLowerCase())) return missing;
  const words = text.replaceAll("_", " ").replaceAll("-", " ").trim();
  if (!words) return missing;
  return words.charAt(0).toUpperCase() + words.slice(1);
}

function displayValue(value, missing = "unbekannt") {
  const text = asText(value, missing);
  if (text === "missing" || text === "unknown" || text === "unavailable") return missing;
  return text;
}

function parseDateValue(value) {
  if (value instanceof Date) return Number.isNaN(value.getTime()) ? null : value;
  if (typeof value === "number" && Number.isFinite(value)) return new Date(value);
  const text = asText(value, "");
  if (!text || ["missing", "unknown", "unavailable", "never", "none", "null"].includes(text.toLowerCase())) return null;
  const date = new Date(text);
  return Number.isNaN(date.getTime()) ? null : date;
}

function formatDateLocal(value, missing = "Noch keine Aktualisierung") {
  const date = parseDateValue(value);
  if (!date) return missing;
  return date.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric" });
}

function formatTimeLocal(value, missing = "Noch keine Aktualisierung") {
  const date = parseDateValue(value);
  if (!date) return missing;
  return `${date.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" })} Uhr`;
}

function formatDateTimeLocal(value, missing = "Noch keine Aktualisierung") {
  const date = parseDateValue(value);
  if (!date) return missing;
  return `${formatDateLocal(date)} · ${formatTimeLocal(date)}`;
}

function formatTimeDateLocal(value, missing = "Noch keine Aktualisierung") {
  const date = parseDateValue(value);
  if (!date) return missing;
  return `${formatTimeLocal(date)} · ${formatDateLocal(date)}`;
}

function formatRelativeOrDateTime(value, neverLabel = "Noch nie angewendet") {
  if (["never", "none", "null", "", "missing", "unknown", "unavailable"].includes(String(value ?? "").toLowerCase())) {
    return neverLabel;
  }
  return formatTimeDateLocal(value, neverLabel);
}

function localDateTime(value, missing = "Noch keine Aktualisierung") {
  return formatTimeDateLocal(value, missing);
}

function localTime(value, missing = "Noch keine Aktualisierung") {
  return formatTimeLocal(value, missing);
}

function translatePresence(value) {
  return translateContextValue("presence", value);
}

function translateContextValue(key, value) {
  const raw = normalizeUxKey(value);
  if (!raw) return "nicht geladen";
  return UX_LABELS.context[raw] || readableFallback(value, "nicht geladen");
}

function presenceSummary(hass, app) {
  const ctx = contextSnapshot(hass, app);
  return translatePresence(
    ctx.presence_personal?.value
      ?? ctx.presence_band?.value
      ?? ctx.presence_household?.value
      ?? stateText(hass, ENTITIES.contextPresencePersonal, null)
      ?? stateText(hass, ENTITIES.contextPresenceBand, null)
      ?? stateText(hass, ENTITIES.contextPresenceHousehold, "nicht geladen"),
  );
}

function numberLike(value) {
  const number = Number.parseFloat(value);
  return Number.isFinite(number) ? number : null;
}

function tempText(value, missing = "unbekannt") {
  const number = numberLike(value);
  if (number === null) return displayValue(value, missing);
  return `${number.toLocaleString("de-DE", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} °C`;
}

function modeLabel(value) {
  const raw = normalizeUxKey(value || "missing");
  return UX_LABELS.modes[raw] || readableFallback(value);
}

function effectiveOutdoorLabel(size = "large") {
  return UX_LABELS.effectiveOutdoor[size] || UX_LABELS.effectiveOutdoor.large;
}

function reasonLabel(value) {
  const raw = normalizeUxKey(value);
  return UX_LABELS.reasons[raw] || readableFallback(value);
}

function fanModeLabel(value) {
  const raw = normalizeUxKey(value);
  return UX_LABELS.fanModes[raw] || modeLabel(value);
}

function isFanActiveMode(value) {
  const raw = normalizeUxKey(value);
  return !["", "off", "aus", "idle", "missing", "unknown", "unavailable", "none"].includes(raw);
}

function fanReasonLabel(value) {
  const raw = String(value ?? "").toLowerCase();
  if (!raw || ["missing", "none", "unknown", "unavailable"].includes(raw)) return "Feuchtewerte steuern den Lüfter.";
  if (raw.includes("humidity") || raw.includes("feuchte") || raw.includes("dew") || raw.includes("taupunkt")) return "Lüfter läuft wegen Feuchte/Taupunkt.";
  if (raw.includes("afterrun") || raw.includes("nachlauf")) return "Lüfter läuft im Nachlauf.";
  if (raw.includes("stoss") || raw.includes("stoß")) return "Stoßlüftung ist aktiv.";
  return reasonLabel(value);
}

function zoneIcon(zone) {
  return {
    living_room: "mdi:sofa-outline",
    kitchen: "mdi:silverware-fork-knife",
    bathroom: "mdi:bathtub-outline",
  }[zone] || "mdi:home-thermometer-outline";
}

function zoneTone(zone) {
  return {
    living_room: "purple",
    kitchen: "green",
    bathroom: "blue",
  }[zone] || "blue";
}

function compactReason(reason, zone = "") {
  const raw = String(reason ?? "").toLowerCase();
  if (!raw || raw === "missing" || raw === "none" || raw === "unavailable") return "Keine besondere Einschränkung erkannt.";
  if (raw.includes("bath_over_target") || raw.includes("bath temperature above") || raw.includes("bath over target")) return "Bad ist warm genug, Heizung bleibt aus.";
  if (raw.includes("bath_humidity_ground_heat")) return "Feuchteschutz hält die Bad-Grundwärme aktiv.";
  if (raw.includes("room_temperature_above") || raw.includes("no_heat_demand")) return "Raum warm genug, kein Nachheizen nötig.";
  if (raw.includes("bath_temperature_above")) return "Bad ist warm genug, Heizung bleibt aus.";
  if (raw.includes("window") || raw.includes("fenster")) return "Wohnbereich blockiert: Fenster/Tür offen oder gekippt.";
  if (raw.includes("summer") || raw.includes("sommer")) return "Sommerregel aktiv: Eco statt Komfortheizen.";
  if (raw.includes("spar") || raw.includes("eco")) return "Eco-Modus ist aktiv.";
  if (raw.includes("ground") || raw.includes("grund")) return "Mindestwärme gegen Auskühlung und Feuchte.";
  if (raw.includes("comfort") || raw.includes("komfort")) return "Komfortmodus ist erlaubt.";
  if (raw.includes("boost")) return "Boost ist gerade möglich oder angefragt.";
  if (raw.includes("cooldown")) return "Cooldown verhindert zu häufiges Anwenden.";
  if (raw.includes("startup")) return "Start-Ruhezeit schützt vor Kurzschluss.";
  if (raw.includes("humidity") || raw.includes("feuchte") || raw.includes("dew")) return "Lüfter läuft wegen Feuchte/Taupunkt.";
  if (raw.includes("fan") || raw.includes("lüfter") || raw.includes("luefter")) return "Der Badlüfter wird koordiniert.";
  return `${zone ? `${ZONES[zone]?.label || zone}: ` : ""}${reasonLabel(reason)}`;
}

function livingAreaWindowStatus(hass) {
  const active = [];
  for (const [label, entityId, attrName] of LIVING_AREA_WINDOWS) {
    const value = String(attr(hass, entityId, attrName, "missing")).toLowerCase();
    const open = value === "open";
    const tilt = value === "tilted";
    if (open) active.push(`${label} offen`);
    if (tilt) active.push(`${label} gekippt`);
  }
  if (!active.length) return { blocked: false, label: "Fenster/Tür geschlossen" };
  return {
    blocked: true,
    label: active.length > 1 ? "Fenster/Tür offen oder gekippt" : active[0],
  };
}

function primaryReason(plan, zone = "") {
  const blocked = Array.isArray(plan.blocked_by) && plan.blocked_by.length ? plan.blocked_by[0] : null;
  return plan.reason || plan.apply_block_reason || plan.apply_reason || blocked || "none";
}

function weatherLabel(hass, app) {
  return outdoorFeeling(hass, app).outdoor_feeling_label;
}

function weatherConditionLabel(value) {
  const raw = normalizeUxKey(value);
  if (!raw) return "Unbekannt";
  return UX_LABELS.weather[raw] || readableFallback(value, "Unbekannt");
}

function qualityLabel(value) {
  const raw = String(value ?? "").toLowerCase();
  const map = {
    measured: "gemessen",
    estimated: "geschätzt",
    fallback: "Fallback",
    missing: "nicht geladen",
    ok: "ok",
  };
  return map[raw] || displayValue(value, "nicht geladen");
}

function seasonBandLabel(value) {
  const raw = String(value ?? "").toLowerCase().replaceAll("-", "_").replaceAll(" ", "_");
  return UX_LABELS.seasons[raw] || THRESHOLD_BANDS.find(([band]) => band === raw)?.[1] || readableFallback(value);
}

function policyTarget(plan) {
  return plan.policy_target_temperature ?? plan.raw_target_temperature ?? plan.target_temperature;
}

function thermostatTarget(plan) {
  return plan.thermostat_target_temperature ?? plan.target_temperature;
}

function allowedProfileText(plan) {
  const profile = plan.allowed_profile ?? plan.profile;
  const suffix = profile && profile !== "off" ? " wäre erlaubt" : "Aus";
  return profile && profile !== "off" ? `${modeLabel(profile)}${suffix}` : suffix;
}

function indoorDemandText(plan) {
  if (plan.heat_demand === false) return "Raum warm genug, kein Nachheizen";
  if (plan.heat_demand === true) return "Wärmebedarf vorhanden";
  return reasonLabel(plan.indoor_heat_demand_reason || "unknown");
}

function deltaText(value) {
  const number = numberLike(value);
  if (number === null) return displayValue(value);
  return `${number >= 0 ? "+" : ""}${number.toLocaleString("de-DE", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} °C`;
}

function roomComfort(plan) {
  return plan.room_comfort || {};
}

function outdoorFeelingFromParts(parts = {}) {
  const effective = numberLike(parts.effectiveTemperature ?? parts.effective_temperature);
  const real = numberLike(parts.realTemperature ?? parts.real_temperature);
  const forecast = numberLike(parts.forecastTemperature ?? parts.forecast_temperature);
  const humidity = numberLike(parts.humidity ?? parts.relative_humidity ?? parts.outdoor_humidity);
  const dewPoint = numberLike(parts.dewPoint ?? parts.dew_point);
  const lux = numberLike(parts.outdoorLux ?? parts.outdoor_lux);
  const weatherRaw = parts.weatherCondition ?? parts.weather_condition;
  const weatherKey = normalizeUxKey(weatherRaw);
  const weatherText = weatherConditionLabel(weatherRaw);
  const basis = effective ?? real ?? forecast;
  const quality = humidity === null && dewPoint === null ? "fallback" : "ok";
  const reasons = [];
  const details = {
    temperature_basis: effective !== null ? "effective_outdoor_temperature" : real !== null ? "real_temperature" : "forecast_temperature",
    weather: weatherText,
    humidity_available: humidity !== null,
    dew_point_available: dewPoint !== null,
    quality,
  };
  if (basis === null) {
    return {
      outdoor_feeling_label: weatherKey ? weatherText : "Unbekannt",
      outdoor_feeling_reason: weatherKey ? `Aus Wetterzustand ${weatherText} abgeleitet; Temperatur fehlt.` : "Keine auswertbaren Außenwerte verfügbar.",
      outdoor_feeling_parts: details,
    };
  }
  reasons.push(`${tempText(basis)} ${details.temperature_basis === "effective_outdoor_temperature" ? effectiveOutdoorLabel("technical") : "Außentemperatur"}`);
  if (weatherKey) reasons.push(weatherText);
  if (humidity !== null) reasons.push(`${Math.round(humidity)} % Luftfeuchte`);
  if (dewPoint !== null) reasons.push(`Taupunkt ${tempText(dewPoint)}`);
  if (lux !== null) reasons.push(`${Math.round(lux).toLocaleString("de-DE")} lx`);
  if (forecast !== null && real !== null) {
    const trend = forecast - real;
    if (trend >= 2) reasons.push("Prognose wärmer");
    if (trend <= -2) reasons.push("Prognose kühler");
    details.forecast_trend = trend >= 2 ? "warming" : trend <= -2 ? "cooling" : "stable";
  }

  const wet = ["rainy", "pouring", "snowy_rainy", "lightning_rainy"].includes(weatherKey);
  const snow = ["snowy", "snowy_rainy"].includes(weatherKey);
  const sunny = ["sunny", "clear"].includes(weatherKey) || (lux !== null && lux >= 18000);
  const lowSun = lux !== null && lux < 2500;
  const veryHumid = humidity !== null && humidity >= 75;
  const humid = humidity !== null && humidity >= 68;
  const muggyDew = dewPoint !== null && dewPoint >= 20;

  let label;
  if ((veryHumid || (dewPoint !== null && dewPoint >= 22)) && basis >= 26) {
    label = "drückend";
  } else if ((humid || muggyDew) && basis >= 23) {
    label = basis >= 25 ? "warm und schwül" : "schwül";
  } else if (snow) {
    label = basis < 3 ? "kalt und winterlich" : "kühl und nass";
  } else if (wet && basis < 14) {
    label = "frisch und regnerisch";
  } else if (wet && (basis < 20 || lowSun)) {
    label = "kühl und nass";
  } else if (wet) {
    label = "mild und regnerisch";
  } else if (sunny && basis >= 20 && basis < 25 && !humid) {
    label = "angenehm mild";
  } else if (sunny && basis >= 25) {
    label = "warm und sonnig";
  } else if (basis < 5) {
    label = "kalt";
  } else if (basis < 11) {
    label = "frisch";
  } else if (basis < 16) {
    label = "frisch";
  } else if (basis < 21) {
    label = "mild";
  } else if (basis < 26) {
    label = "angenehm mild";
  } else {
    label = "warm";
  }

  return {
    outdoor_feeling_label: label,
    outdoor_feeling_reason: reasons.join(" · ") || "Aus verfügbaren Außenwerten abgeleitet.",
    outdoor_feeling_parts: details,
  };
}

function outdoorFeeling(hass, app) {
  const br = effectiveBreakdown(hass, app);
  const inp = effectiveInputs(hass, app);
  const weatherResolution = inp.weather_resolution || {};
  const forecastResolution = inp.forecast_resolution || weatherResolution.forecast || {};
  return outdoorFeelingFromParts({
    effectiveTemperature: br.effective_temperature ?? stateText(hass, ENTITIES.effectiveTemp),
    realTemperature: inp.real_temperature ?? br.real_temperature,
    forecastTemperature: inp.forecast_temperature ?? forecastResolution.value ?? stateText(hass, ENTITIES.forecastTemp3h),
    weatherCondition: inp.weather_condition ?? forecastResolution.weather_condition ?? stateText(hass, ENTITIES.weatherCondition, "missing"),
    humidity: inp.outdoor_humidity ?? inp.humidity ?? forecastResolution.humidity,
    dewPoint: inp.dew_point ?? forecastResolution.dew_point,
    outdoorLux: inp.outdoor_lux,
  });
}

function modeClass(mode) {
  const raw = String(mode ?? "").toLowerCase();
  if (raw.includes("spar")) return "green";
  if (raw.includes("aus") || raw.includes("off")) return "purple";
  if (raw.includes("grund") || raw.includes("ground")) return "blue";
  if (raw.includes("comfort") || raw.includes("komfort")) return "pink";
  return "blue";
}

function zoneChipList(plan, zone) {
  const chips = [
    `<span class="pill ${modeClass(plan.profile)}">${esc(modeLabel(plan.profile))}</span>`,
  ];
  if (plan.apply_blocked === "on" || String(plan.apply_block_reason || "").toLowerCase() !== "none" || String(primaryReason(plan)).toLowerCase().includes("window")) {
    chips.push(`<span class="pill purple">${esc(compactReason(primaryReason(plan, zone)))}</span>`);
  }
  if (plan.is_boost_active) chips.push(`<span class="pill pink">Boost aktiv</span>`);
  if (String(primaryReason(plan)).toLowerCase().includes("summer")) chips.push(`<span class="pill green">Sommerregel</span>`);
  return chips.slice(0, 3).join("");
}

function roomFact(label, value) {
  return `<div class="fact-row"><span>${esc(label)}</span><b>${esc(displayValue(value))}</b></div>`;
}

function consequenceItems(hass, app) {
  const bath = bathroomDebug(hass, app);
  const fan = bath.fan_plan || {};
  const zoneItems = Object.entries(ZONES).map(([zone, meta]) => {
    const plan = zonePlan(hass, zone, app);
    if (zone === "bathroom" && isBathroomNoHeating(plan)) {
      return `<div class="reason">
        ${icon(zoneIcon(zone))}
        <div><small>Bad · ${esc(modeLabel(plan.profile))}</small><b>Bad ist warm genug, kein Nachheizen nötig.</b><br><span class="muted">${esc(compactReason(primaryReason(plan, zone), zone))}</span></div>
      </div>`;
    }
    return `<div class="reason">
      ${icon(zoneIcon(zone))}
      <div><small>${esc(meta.label)} · ${esc(primaryConsequence(plan, zone))}</small><b>${esc(modeLabel(plan.profile))} auf ${esc(tempText(policyTarget(plan)))}</b><br><span class="muted">${esc(compactReason(primaryReason(plan, zone), zone))}</span></div>
    </div>`;
  }).join("");
  const fanMode = String(fan.mode ?? stateText(hass, ENTITIES.bathroomFanMode, "missing")).toLowerCase();
  const fanReason = fan.fan_reason ?? fan.reason ?? fan.apply_block_reason ?? "";
  const showFan = !["off", "aus", "idle", "missing", "unknown", "unavailable"].includes(fanMode)
    || String(fanReason).toLowerCase().includes("humidity")
    || String(fanReason).toLowerCase().includes("feuchte")
    || String(fanReason).toLowerCase().includes("dew");
  return zoneItems + (showFan ? `<div class="reason">
    ${icon("mdi:fan")}
    <div><small>Badlüfter · ${esc(fanModeLabel(fan.mode ?? stateText(hass, ENTITIES.bathroomFanMode)))}</small><b>${esc(fanReasonLabel(fan.fan_reason ?? fan.reason ?? fan.apply_block_reason))}</b><br><span class="muted">Feuchtewerte steuern den Lüfter.</span></div>
  </div>` : "");
}

function isBathroomNoHeating(plan) {
  const reason = normalizeUxKey(primaryReason(plan, "bathroom"));
  const profile = normalizeUxKey(plan?.profile);
  return ["bath_over_target_forces_off", "bath_temperature_above_target_no_heating"].includes(reason)
    || profile === "off"
    || profile === "aus";
}

function bathroomHeroPhrase(bathroom, fanMode) {
  const fanText = isFanActiveMode(fanMode) ? "aktiv" : "aus";
  if (isBathroomNoHeating(bathroom)) return `Bad heizt nicht nach, Lüfter ist ${fanText}.`;
  return `Bad ist ${modeLabel(bathroom.profile)}, Lüfter ist ${fanText}.`;
}

function overviewSentence(hass, app) {
  const living = zonePlan(hass, "living_room", app);
  const kitchen = zonePlan(hass, "kitchen", app);
  const bathroom = zonePlan(hass, "bathroom", app);
  const fan = bathroomDebug(hass, app).fan_plan || {};
  const fanMode = fan.mode ?? stateText(hass, ENTITIES.bathroomFanMode);
  const bathroomText = bathroomHeroPhrase(bathroom, fanMode);
  const weather = weatherLabel(hass, app);
  const windowStatus = livingAreaWindowStatus(hass);
  const livingReason = String(primaryReason(living)).toLowerCase();
  const kitchenReason = String(primaryReason(kitchen)).toLowerCase();
  if (windowStatus.blocked || livingReason.includes("window") || kitchenReason.includes("window")) {
    return `Aktuell <span class="accent">${esc(weather)}</span> draußen. <span class="pink">${esc(windowStatus.label)}</span>: Wohnbereich heizt nicht. ${esc(bathroomText)}`;
  }
  if (kitchenReason.includes("summer")) {
    return `Aktuell <span class="accent">${esc(weather)}</span> draußen. Küche bleibt wegen Sommerregel im <span class="purple">${esc(modeLabel(kitchen.profile))}</span>. ${esc(bathroomText)}`;
  }
  return `Aktuell <span class="accent">${esc(weather)}</span> draußen. Wohnzimmer ist <span class="purple">${esc(modeLabel(living.profile))}</span>, Küche ist <span class="purple">${esc(modeLabel(kitchen.profile))}</span>. ${esc(bathroomText)}`;
}

function primaryConsequence(plan, zone) {
  const reason = String(primaryReason(plan, zone)).toLowerCase();
  if (zone === "bathroom" && isBathroomNoHeating(plan)) return "Aus";
  if (reason.includes("window")) return "Heizen blockiert";
  if (reason.includes("summer") || String(plan.profile).toLowerCase().includes("spar")) return "Eco aktiv";
  if (String(plan.profile).toLowerCase().includes("grund")) return "Eco aktiv";
  return modeLabel(plan.profile);
}

function weatherChip(hass, app) {
  const inputs = effectiveInputs(hass, app);
  return weatherConditionLabel(inputs.weather_condition ?? stateText(hass, ENTITIES.weatherCondition, "Wetter"));
}

function policyConsequence(hass, app) {
  const apply = stateText(hass, ENTITIES.applyActive);
  const ready = stateText(hass, ENTITIES.applyReady);
  const status = stateText(hass, ENTITIES.applyStatus);
  const windowStatus = livingAreaWindowStatus(hass);
  if (windowStatus.blocked) {
    return "Fenster oder Tür sind offen/gekippt. Die Policy blockiert Heizen im offenen Wohnbereich und hält das Bad mit Eco separat.";
  }
  if (apply === "on") return `Auto-Apply ist aktiv. Die Policy kann Änderungen anwenden, sobald Ready ${ready} ist.`;
  if (status !== "missing") return `Auto-Apply ist aus. Änderungen bleiben als Plan sichtbar; manuelles Anwenden oder Dry Run ist möglich.`;
  return "Die Policy zeigt aktuell die geplante Wärmeabgabe.";
}

function targetEntityIssues(hass, app) {
  return Object.values(plans(hass, app))
    .map((plan) => plan?.target_entity_id)
    .filter((entityId) => entityId && !stateObj(hass, entityId));
}

function lastApplyActions(hass, app) {
  const payload = debugPayload(hass, app);
  const lastApply = endpointDebug(app).last_apply_result || payload.last_apply_result || null;
  return Array.isArray(lastApply?.actions) ? lastApply.actions : [];
}

function hasSafetyDownshift(hass, app) {
  const actionMatch = lastApplyActions(hass, app).some((action) =>
    action?.details?.forced_safety_downshift === true
    || normalizeUxKey(action?.reason) === "forced_safety_downshift"
    || normalizeUxKey(action?.details?.safety_downshift_reason));
  if (actionMatch) return true;
  return Object.values(plans(hass, app)).some((plan) =>
    ["bath_over_target_forces_off", "bath_temperature_above_target_no_heating"].includes(normalizeUxKey(primaryReason(plan))));
}

function hasFanSignal(hass, app) {
  const fan = bathroomDebug(hass, app).fan_plan || {};
  const mode = fan.mode ?? stateText(hass, ENTITIES.bathroomFanMode, "missing");
  const reason = String(fan.fan_reason ?? fan.reason ?? fan.apply_block_reason ?? "").toLowerCase();
  return isFanActiveMode(mode)
    || reason.includes("humidity")
    || reason.includes("feuchte")
    || reason.includes("dew")
    || reason.includes("taupunkt");
}

function plansAreSynchronized(hass, app) {
  return Object.keys(ZONES).every((zone) => {
    const plan = zonePlan(hass, zone, app);
    return plan.plan_hash && plan.last_applied_plan_hash && plan.plan_hash === plan.last_applied_plan_hash;
  });
}

function heroIndicator(hass, app) {
  const inputIssues = importantInputIssues(hass, app);
  const targetIssues = targetEntityIssues(hass, app);
  if (inputIssues.length || targetIssues.length) {
    return {
      icon: "mdi:alert-circle-outline",
      label: "Eingaben prüfen",
      title: inputIssues[0] || `Thermostat nicht verfügbar: ${targetIssues[0]}`,
    };
  }
  if (hasSafetyDownshift(hass, app)) {
    return {
      icon: "mdi:shield-alert-outline",
      label: "Sicherheitsabsenkung",
      title: "Eine sichere Absenkung oder Heizsperre hat Vorrang.",
    };
  }
  const windowStatus = livingAreaWindowStatus(hass);
  const windowPlan = Object.keys(ZONES).some((zone) => String(primaryReason(zonePlan(hass, zone, app))).toLowerCase().includes("window"));
  if (windowStatus.blocked || windowPlan) {
    return {
      icon: "mdi:window-open-variant",
      label: "Wohnbereich blockiert",
      title: windowStatus.blocked ? windowStatus.label : "Fenster/Tür blockiert den Wohnbereich.",
    };
  }
  if (hasFanSignal(hass, app)) {
    return {
      icon: "mdi:fan-alert",
      label: "Feuchte/Lüfter aktiv",
      title: "Der Badlüfter oder auffällige Feuchtewerte bestimmen den Zustand.",
    };
  }
  if (stateText(hass, ENTITIES.applyActive) !== "on") {
    return {
      icon: "mdi:pause-circle-outline",
      label: "Apply aus",
      title: "Automatik ist aus; Änderungen bleiben als Plan sichtbar.",
    };
  }
  return {
    icon: plansAreSynchronized(hass, app) ? "mdi:check-circle-outline" : "mdi:check-decagram-outline",
    label: plansAreSynchronized(hass, app) ? "Stabil und synchron" : "Stabil geplant",
    title: plansAreSynchronized(hass, app)
      ? "Alle Pläne sind synchron mit dem letzten Apply."
      : "Keine auffälligen Blocker erkannt; geplante Änderungen sind sichtbar.",
  };
}

function miniStat(iconName, value, label) {
  return `<div class="card mini-stat"><span class="mini-stat-icon">${icon(iconName)}</span><div><b>${esc(displayValue(value))}</b><span>${esc(label)}</span></div></div>`;
}

function renderOverview(hass, app) {
  const living = zonePlan(hass, "living_room", app);
  const kitchen = zonePlan(hass, "kitchen", app);
  const bathroom = zonePlan(hass, "bathroom", app);
  const loaded = Object.keys(hass?.states || {}).some((id) =>
    id.includes("climate_policy") || id.includes("climate_effective") || id.includes("climate_system_ready"));
  const br = effectiveBreakdown(hass, app);
  const inputs = effectiveInputs(hass, app);
  const ctx = contextSnapshot(hass, app);
  const indicator = heroIndicator(hass, app);
  return `
    <section class="hero">
      <div class="hero-icon" title="${esc(indicator.title)}">${icon(indicator.icon)}<small>${esc(indicator.label)}</small></div>
      <div>
        <h2>${overviewSentence(hass, app)}</h2>
        <p>${esc(policyConsequence(hass, app))}</p>
        <div class="chip-row">
          ${statusChip(stateText(hass, ENTITIES.systemReady), stateText(hass, ENTITIES.systemReady) === "on" ? "System bereit" : "System prüfen")}
          ${statusChip(stateText(hass, ENTITIES.applyActive), stateText(hass, ENTITIES.applyActive) === "on" ? "Apply: An" : "Apply: Aus")}
          ${statusChip(loaded ? "ok" : "missing", loaded ? "Integration geladen" : "Integration fehlt")}
        </div>
      </div>
      <div class="hero-side"><div><div class="cloud-temp">${esc(tempText(stateText(hass, ENTITIES.effectiveTemp)))}</div><span class="weather-chip">${esc(weatherChip(hass, app))}</span></div></div>
    </section>

    <div class="section grid cols-4">
      ${miniStat("mdi:home-group", "3", "Räume im Plan")}
      ${miniStat("mdi:thermometer-lines", tempText(stateText(hass, ENTITIES.effectiveTemp)), effectiveOutdoorLabel("large"))}
      ${miniStat("mdi:white-balance-sunny", outdoorFeeling(hass, app).outdoor_feeling_label, "Außengefühl")}
      ${miniStat("mdi:play-circle-outline", formatRelativeOrDateTime(stateText(hass, ENTITIES.lastApply)), "Letzter Apply")}
    </div>

    <div class="section grid cols-4">
      <div class="card">
        <h2>${icon("mdi:account-clock-outline")}Kontext</h2>
        ${kv("Anwesenheit", presenceSummary(hass, app))}
        ${kv("Tagesstatus", translateContextValue("day_context", ctx.day_context?.value ?? stateText(hass, ENTITIES.contextDayContext, null)))}
        ${kv("Bio-Status", translateContextValue("bio_state", ctx.bio_state?.value ?? stateText(hass, ENTITIES.contextBioState, null)))}
      </div>
      <div class="card">
        <h2>${icon("mdi:weather-partly-cloudy")}Außenbedingungen</h2>
        ${kv("Reale Temperatur", tempText(inputs.real_temperature ?? br.real_temperature))}
        ${kv("Gefühlt", tempText(stateText(hass, ENTITIES.outdoorFeelsLike)))}
        ${kv("Forecast in 3h", tempText(stateText(hass, ENTITIES.forecastTemp3h)))}
      </div>
      <div class="card">
        <h2>${icon("mdi:thermometer-lines")}${esc(effectiveOutdoorLabel("large"))}</h2>
        ${kv("Licht (Lux)", inputs.outdoor_lux ?? "nicht geladen")}
        ${kv("Wetterkorrektur", tempText(br.weather_offset ?? "missing"))}
        ${kv("Prognosekorrektur", tempText(br.forecast_offset ?? "missing"))}
        ${kv(effectiveOutdoorLabel("large"), tempText(br.effective_temperature ?? stateText(hass, ENTITIES.effectiveTemp)))}
        ${kv("Außengefühl", outdoorFeeling(hass, app).outdoor_feeling_label)}
      </div>
      <div class="card">
        <h2>${icon("mdi:shield-check-outline")}Konsequenzen</h2>
        ${consequenceItems(hass, app)}
      </div>
    </div>

    <div class="section info-band">
      ${icon("mdi:lightbulb-outline")}
      <div><b>Gut zu wissen</b><span class="muted">${esc(UX_LABELS.effectiveOutdoor.explanation)}</span></div>
    </div>
  `;
}

function renderContext(hass, app) {
  const ctx = contextSnapshot(hass, app);
  if (!Object.keys(ctx).length) {
    return debugEndpointNotice(app);
  }
  const labels = {
    activity_state: "Aktivität",
    bio_state: "Bio-Status",
    day_context: "Tageskontext",
    day_state: "Tagesstatus",
    presence_band: "Anwesenheitsband",
    presence_household: "Haushalt",
    presence_personal: "Persönlich",
    presence_preheat_active: "Vorheizen aktiv",
    presence_transition: "Anwesenheitswechsel",
    planned_wakeup_time: "Geplanter Wakeup",
  };
  const rows = Object.entries(labels).map(([key, label]) => {
    const item = ctx[key] || {};
    return `<tr>
      <td>${esc(label)}</td>
      <td class="mono">${esc(translateContextValue(key, item.value))}</td>
      <td class="mono">${esc(asText(item.source_entity_id))}</td>
      <td>${statusChip(item.quality || "missing", qualityLabel(item.quality || "missing"))}</td>
      <td>${esc(asText(item.fallback_used, "false"))}</td>
    </tr>`;
  }).join("");
  return `<div class="table-wrap">
    <table><thead><tr><th>Wert</th><th>Zustand</th><th>Quelle</th><th>Qualität</th><th>Fallback</th></tr></thead><tbody>${rows}</tbody></table>
  </div>`;
}

function renderZones(hass, app) {
  const zoneCards = Object.entries(ZONES).map(([zone, meta]) => {
    const plan = zonePlan(hass, zone, app);
    const reason = compactReason(primaryReason(plan, zone), zone);
    const comfort = roomComfort(plan);
    const bath = zone === "bathroom" ? bathroomDebug(hass, app) : {};
    const fan = bath.fan_plan || {};
    const diag = fan.diagnostics || {};
    const updateAt = plan.updated_at ?? stateObj(hass, meta.mode)?.last_changed ?? stateObj(hass, meta.target)?.last_changed;
    return `<div class="card room-card">
      <div class="room-head">
        <div class="room-icon">${icon(zoneIcon(zone))}</div>
        <div>
          <h3>${esc(meta.label)}</h3>
          <div class="muted">Modus</div>
          <div class="mode">${esc(modeLabel(plan.profile))}</div>
        </div>
        <div class="target">${esc(tempText(policyTarget(plan)))}</div>
      </div>
      <div class="reason">
        ${icon(zone === "bathroom" ? "mdi:water-outline" : "mdi:leaf-outline")}
        <div><small>Wichtigster Grund</small><b>${esc(reason)}</b></div>
      </div>
      <div class="chip-row">${zoneChipList(plan, zone)}${zone === "bathroom" ? `<span class="pill blue">Lüfter: ${esc(fanModeLabel(fan.mode ?? stateText(hass, ENTITIES.bathroomFanMode)))}</span>` : ""}</div>
      <div class="room-facts">
        ${roomFact("Aktuelle Temperatur", zoneRoomTemperature(hass, app, zone))}
        ${roomFact("Außenfreigabe", allowedProfileText(plan))}
        ${roomFact("Innenbedarf", indoorDemandText(plan))}
        ${roomFact("Policy-Ziel", tempText(policyTarget(plan)))}
        ${roomFact("Bodenplatten-Delta", `${deltaText(plan.floor_slab_delta)}${plan.floor_slab_delta_quality ? ` · ${qualityLabel(plan.floor_slab_delta_quality)}` : ""}`)}
        ${roomFact("Thermostat-Ziel", `${tempText(thermostatTarget(plan))}${numberLike(plan.floor_slab_delta) ? ` (${deltaText(plan.floor_slab_delta)})` : ""}`)}
        ${roomFact("Thermostat real", tempText(stateText(hass, meta.target, thermostatTarget(plan))))}
        ${comfort.label ? roomFact("Raumgefühl", `${displayValue(comfort.label)} · ${displayValue(comfort.reason)}`) : ""}
        ${comfort.perceived_temperature !== undefined ? roomFact("Gefühlte Raumtemp.", tempText(comfort.perceived_temperature)) : ""}
        ${roomFact("Konsequenz", primaryConsequence(plan, zone))}
        ${roomFact("Sync", plan.plan_hash === plan.last_applied_plan_hash ? "Synchron" : "Ausstehend")}
        ${roomFact("Letztes Update", localDateTime(updateAt))}
      </div>
      <details class="expert section">
        <summary>Experten-Details</summary>
        ${kv("Plan Hash", plan.plan_hash, "mono")}
        ${kv("Pending Hash", plan.pending_plan_hash, "mono")}
        ${kv("Letzter Apply Hash", plan.last_applied_plan_hash, "mono")}
        ${kv("Policy Target", policyTarget(plan))}
        ${kv("Floor Slab Delta", deltaText(plan.floor_slab_delta))}
        ${kv("Floor Slab Reason", reasonLabel(plan.floor_slab_delta_reason))}
        ${kv("Allowed Profile", modeLabel(plan.allowed_profile))}
        ${kv("Indoor Demand", indoorDemandText(plan))}
        ${kv("Indoor Rule", `${tempText(plan.indoor_heat_on_below)} / ${tempText(plan.indoor_heat_off_at)} · ${displayValue(plan.indoor_min_hold_minutes, "0")} Min.`)}
        ${kv("Thermostat Target", thermostatTarget(plan))}
        ${kv("Room Comfort Quality", qualityLabel(comfort.quality))}
        ${kv("Policy Reason", plan.reason ?? "missing")}
        ${kv("Apply Blocker", plan.apply_block_reason ?? plan.apply_reason)}
        ${kv("Decision Path", plan.decision_path || [])}
        ${zone === "bathroom" ? `${kv("Lüfter Grund", fanReasonLabel(fan.fan_reason ?? fan.reason))}${kv("AH Delta", diag.ah_delta ?? "missing")}${kv("Taupunkt", diag.dewpoint ?? "missing")}` : ""}
      </details>
    </div>`;
  }).join("");
  return `<div class="card">
    <div class="room-head">
      <div class="hero-icon">${icon("mdi:check-circle-outline")}</div>
      <div>
        <h2>Aktive Raumentscheidungen</h2>
        <p class="muted">Die Policy fasst Wohnzimmer, Küche und Bad zusammen. Details zu Lüfter, Feuchte und Sensoren findest du in den aufklappbaren Raumdetails und in der Diagnose.</p>
      </div>
      <div class="chip-row">
        <span class="pill blue">3 Räume aktiv</span>
        <span class="pill purple">${esc(effectiveOutdoorLabel("chip"))} ${esc(tempText(stateText(hass, ENTITIES.effectiveTemp)))}</span>
      </div>
    </div>
  </div>
  <div class="section grid cols-3">${zoneCards}</div>
  <div class="section info-band">
    ${icon("mdi:lightbulb-outline")}
    <div><b>Tipp zur Optimierung</b><span class="muted">${esc(compactReason(primaryReason(livingOrFirstPlan(hass, app), "living_room")))}</span></div>
  </div>`;
}

function livingOrFirstPlan(hass, app) {
  return zonePlan(hass, "living_room", app) || Object.keys(ZONES).map((zone) => zonePlan(hass, zone, app))[0] || {};
}

function sourcePill(source) {
  const cls = source === "user option" ? "source-pill user" : "source-pill";
  return `<span class="${cls}">${esc(source || "default")}</span>`;
}

function tuningDraftValue(app, data, key) {
  if (app && app._tuningDraft && Object.prototype.hasOwnProperty.call(app._tuningDraft, key)) {
    return app._tuningDraft[key];
  }
  return data.values?.[key];
}

function isDirty(app, data, key) {
  if (!app || !app._tuningDraft || !Object.prototype.hasOwnProperty.call(app._tuningDraft, key)) return false;
  return String(app._tuningDraft[key] ?? "") !== String(data.values?.[key] ?? "");
}

function numberInput(app, data, key, disabled = false) {
  const value = tuningDraftValue(app, data, key);
  return `<input type="number" step="0.1" data-tuning-key="${esc(key)}" value="${esc(value ?? "")}" ${disabled ? "disabled" : ""}>`;
}

function boolInput(app, data, key) {
  const checked = tuningDraftValue(app, data, key) === true || tuningDraftValue(app, data, key) === "true";
  return `<input type="checkbox" data-tuning-key="${esc(key)}" ${checked ? "checked" : ""}>`;
}

function tuningInput(app, data, key) {
  if (key === "floor_slab_mode") {
    const value = String(tuningDraftValue(app, data, key) ?? "dynamic_3day");
    return `<select data-tuning-key="${esc(key)}">
      <option value="dynamic_3day" ${value === "dynamic_3day" ? "selected" : ""}>dynamic_3day</option>
      <option value="static_fallback" ${value === "static_fallback" ? "selected" : ""}>static_fallback</option>
    </select>`;
  }
  return numberInput(app, data, key);
}

function fieldRows(app, data, fields) {
  return fields.map(([key, label]) => {
    const dirty = isDirty(app, data, key);
    return `<div class="field-row ${dirty ? "dirty" : ""}">
      <div><b>${esc(label)}</b><br><span class="mono muted">${esc(key)}</span></div>
      ${tuningInput(app, data, key)}
      ${sourcePill(data.sources?.[key])}
    </div>`;
  }).join("");
}

function renderThresholds(hass, app) {
  const data = tuningOptions(hass, app);
  const current = thresholds(hass, app);
  if (!data.values) {
    return debugEndpointNotice(app);
  }
  app?._ensureTuningDraft(data);
  const updateAvailable = serviceAvailable(hass, "update_options");
  const resetAvailable = serviceAvailable(hass, "reset_options");
  const dirtyKeys = app?._dirtyTuningKeys(data) || [];
  const error = app?._tuningError || "";
  const activeBand = String(current.active_month_band ?? current.band ?? "").toLowerCase().replaceAll("-", "_").replaceAll(" ", "_");
  const tab = app?._tuningTab || "season";
  const tabs = [
    ["season", "Saisonmatrix"],
    ["setpoints", "Setpoints"],
    ["living", "Wohnbereich"],
    ["bath", "Bad & Lüfter"],
    ["weather", "Wetter & Heizwert"],
    ["automation", "Automatik"],
    ["advanced", "Erweitert"],
  ].map(([id, label]) => `<button data-tuning-tab="${esc(id)}" class="${tab === id ? "active" : ""}">${esc(label)}</button>`).join("");
  const groupCard = (sectionName) => {
    const group = TUNING_GROUPS.find(([section]) => section === sectionName);
    if (!group) return "";
    const [section, title, iconName, fields] = group;
    return `<div class="card">
      <div class="toolbar">
        <h2>${icon(iconName)}${esc(title)}</h2>
        <button class="action" data-action="tuning-reset-section-${esc(section)}" ${resetAvailable ? "" : "disabled"}>${icon("mdi:restore")}<span>Zurücksetzen</span></button>
      </div>
      ${fieldRows(app, data, fields)}
    </div>`;
  };
  const seasonRows = THRESHOLD_BANDS.map(([band, label, months]) => {
    const bandData = data.threshold_bands?.[band] || {};
    const keys = bandData.keys || {};
    const comfortDisabled = tuningDraftValue(app, data, keys.comfort_disabled) === true || tuningDraftValue(app, data, keys.comfort_disabled) === "true";
    const boostDisabled = tuningDraftValue(app, data, keys.boost_disabled) === true || tuningDraftValue(app, data, keys.boost_disabled) === "true";
    const rowDirty = Object.values(keys).some((key) => isDirty(app, data, key));
    const active = activeBand === band;
    const sources = Object.values(keys).map((key) => data.sources?.[key]).filter(Boolean);
    return `<tr class="${active ? "active" : ""} ${rowDirty ? "dirty" : ""}">
      <td><b>${esc(seasonBandLabel(band) || label)}</b>${active ? `<br><span class="pill purple">Aktiv</span>` : ""}</td>
      <td>${esc(months)}</td>
      <td>${numberInput(app, data, keys.off_threshold)}</td>
      <td>${comfortDisabled ? `<span class="muted">deaktiviert</span>` : numberInput(app, data, keys.comfort_threshold)}</td>
      <td>${boostDisabled ? `<span class="muted">deaktiviert</span>` : numberInput(app, data, keys.boost_threshold)}</td>
      <td>${numberInput(app, data, keys.floor_slab_delta)}</td>
      <td>${boolInput(app, data, keys.comfort_disabled)}</td>
      <td>${boolInput(app, data, keys.boost_disabled)}</td>
      <td>${[...new Set(sources)].map(sourcePill).join(" ") || sourcePill("default")}</td>
      <td><button class="action" data-action="tuning-reset-band-${esc(band)}" ${resetAvailable ? "" : "disabled"}>${icon("mdi:restore")}<span>Reset</span></button></td>
    </tr>`;
  }).join("");
  const seasonPanel = `<div class="card">
    <h2>${icon("mdi:calendar-range")}Saisonmatrix</h2>
    <div class="table-wrap">
      <table class="matrix">
        <thead><tr><th>Saison/Band</th><th>Monate</th><th>Aus ab</th><th>Komfort bis</th><th>Boost bis</th><th>Bodenplatten-Delta</th><th>Komfort aus</th><th>Boost aus</th><th>Quelle</th><th>Reset</th></tr></thead>
        <tbody>${seasonRows}</tbody>
      </table>
    </div>
  </div>`;
  const setpointsPanel = `<div class="grid cols-2">
    ${groupCard("setpoints")}
    <div class="card">${fieldRows(app, data, [
      ["bath_setpoint_protection", "Bad Schutz"],
      ["bath_setpoint_ground", "Bad Eco"],
      ["bath_setpoint_comfort", "Bad Komfort"],
    ])}</div>
  </div>`;
  const livingPanel = `<div class="grid cols-2">
    <div class="card">
      <h2>${icon("mdi:home-thermometer-outline")}Raumkontext</h2>
      ${kv("Wohnzimmer", `Basis aus gemeinsamen Setpoints; aktuelle Temperatur ${zoneRoomTemperature(hass, app, "living_room")}`)}
      ${kv("Küche", `Basis aus gemeinsamen Setpoints; aktuelle Temperatur ${zoneRoomTemperature(hass, app, "kitchen")}`)}
      ${kv("Fensterlogik", livingAreaWindowStatus(hass).label)}
      <p class="muted">Wohnzimmer und Küche teilen sich Fensterlogik und Innenbedarf. Außen erlaubt die Stufe, innen entscheidet der Bedarf.</p>
    </div>
    <div class="card">
      <h2>${icon("mdi:vector-combine")}Aktuelle Planwerte</h2>
      ${Object.entries(ZONES).map(([zone, meta]) => {
        const plan = zonePlan(hass, zone, app);
        return kv(meta.label, `${allowedProfileText(plan)} · ${indoorDemandText(plan)} · Policy ${tempText(policyTarget(plan))} · Thermostat ${tempText(thermostatTarget(plan))} · Delta ${deltaText(plan.floor_slab_delta)}`);
      }).join("")}
    </div>
    ${groupCard("indoor_living")}
  </div>`;
  const weatherPanel = `<div class="grid cols-2">${groupCard("effective")}${groupCard("floor_slab")}${renderEffective(hass, app)}</div>`;
  const automationPanel = `<div class="grid cols-2">${groupCard("boost")}${groupCard("apply")}</div>`;
  const bathFields = [
    ["bath_comfort_suppression_teff", "Komfort bis Heizwert"],
    ["bath_humidity_acute_threshold", "Aktiv-Luftfeuchte"],
    ["bath_humidity_acute_rise_threshold", "Aktiv-Anstieg 5 Min."],
    ["bath_humidity_end_threshold", "End-Luftfeuchte"],
    ["bath_dewpoint_acute_threshold", "Aktiv-Taupunkt"],
    ["bath_humidity_ground_heat_threshold", "Grundwärme Feuchte"],
    ["bath_dewpoint_ground_heat_threshold", "Grundwärme Taupunkt"],
    ["bath_humidity_ground_heat_teff_limit", "Grundwärme bis Heizwert"],
    ["bath_humidity_ground_heat_target", "Grundwärme Feuchte-Ziel"],
    ["bath_humidity_ground_heat_off_at", "Grundwärme Feuchte aus ab"],
    ["bath_ah_delta_afterrun_on", "Nachlauf ab AH-Delta"],
    ["bath_ah_delta_afterrun_off", "Nachlauf Ende AH-Delta"],
    ["bath_ah_delta_stoss", "Stoßlüftung AH-Delta"],
    ["bath_fan_heat_coordination_delta", "Heiz-/Lüfter-Delta"],
    ["bath_fan_acute_max_minutes", "Aktiv max. Minuten"],
    ["bath_fan_afterrun_max_minutes", "Nachlauf max. Minuten"],
    ["bath_fan_stoss_interval_hours", "Stoßlüftung Intervall"],
    ["bath_fan_stoss_duration_minutes", "Stoßlüftung Dauer"],
  ];
  const bathPanel = `<div class="grid cols-2"><div class="card"><h2>${icon("mdi:fan")}Bad & Lüfter</h2>${fieldRows(app, data, bathFields)}</div><div class="card"><h2>${icon("mdi:bathtub-outline")}Bad Status</h2>${kv("Badmodus", modeLabel(zonePlan(hass, "bathroom", app).profile))}${kv("Außenfreigabe", allowedProfileText(zonePlan(hass, "bathroom", app)))}${kv("Innenbedarf", indoorDemandText(zonePlan(hass, "bathroom", app)))}${kv("Lüfter", fanModeLabel(bathroomDebug(hass, app).fan_plan?.mode ?? stateText(hass, ENTITIES.bathroomFanMode)))}${kv("Grund", compactReason(primaryReason(zonePlan(hass, "bathroom", app), "bathroom")))}</div>${groupCard("indoor_bathroom")}</div>`;
  const advancedPanel = `<div class="grid cols-2">${groupCard("setpoints")}${groupCard("effective")}${groupCard("floor_slab")}${groupCard("indoor_living")}${groupCard("indoor_bathroom")}${groupCard("boost")}${groupCard("apply")}${groupCard("bath")}</div>`;
  const panels = { season: seasonPanel, setpoints: setpointsPanel, living: livingPanel, bath: bathPanel, weather: weatherPanel, automation: automationPanel, advanced: advancedPanel };
  return `${error ? `<div class="error-box">${esc(error)}</div>` : ""}
  <div class="card">
    <div class="toolbar">
      <div>
        <h2>${icon("mdi:tune-vertical-variant")}Heizstrategie je Jahreszeit</h2>
        <span class="muted">Ruhiger Arbeitsbereich für Setpoints, saisonale Schwellen und Expertenparameter. Ungespeicherte Änderungen werden markiert.</span>
      </div>
      <div class="actions">
        ${actionButton("tuning-reset-all", "Alles zurücksetzen", "mdi:restore", false, resetAvailable)}
        <button class="action primary" data-action="tuning-save" ${updateAvailable && dirtyKeys.length > 0 ? "" : "disabled"}>${icon("mdi:content-save-outline")}<span>${esc(dirtyKeys.length ? `Speichern (${dirtyKeys.length})` : "Speichern")}</span></button>
      </div>
    </div>
    <div class="grid cols-4">
      ${miniStat("mdi:calendar-check-outline", seasonBandLabel(current.active_month_band ?? current.band ?? "unbekannt"), "Aktives Saisonband")}
      ${miniStat("mdi:sofa-outline", tempText(data.values?.setpoint_komfort ?? "missing"), "Komfort-Setpoint")}
      ${miniStat("mdi:leaf-outline", tempText(data.values?.setpoint_spar ?? "missing"), "Eco-Setpoint")}
      ${miniStat("mdi:bathtub-outline", tempText(data.values?.bath_setpoint_ground ?? "missing"), "Bad Eco")}
    </div>
  </div>
  <div class="section segmented">${tabs}</div>
  <div class="section">${panels[tab] || seasonPanel}</div>
  <div class="section info-band">
    ${icon("mdi:information-outline")}
    <div class="actions">
      <span class="muted">Änderungen werden lokal im Integrationsoptionen-Service gespeichert; die fachliche Policy-Logik bleibt unverändert.</span>
    </div>
  </div>`;
}

function renderEffective(hass, app) {
  const br = effectiveBreakdown(hass, app);
  const inp = effectiveInputs(hass, app);
  const sourceEntities = inp.source_entities || {};
  const weatherResolution = inp.weather_resolution || {};
  const forecastResolution = inp.forecast_resolution || weatherResolution.forecast || {};
  const feelsLikeResolution = inp.feels_like_resolution || weatherResolution.feels_like || {};
  const feeling = outdoorFeeling(hass, app);
  return `<div class="grid cols-2">
    <div class="card">
      <h2>${icon("mdi:database-eye-outline")}Inputs</h2>
      ${kv("Reale Außentemperatur", tempText(inp.real_temperature ?? br.real_temperature ?? "missing"))}
      ${metric("Gefühlte Außentemperatur", stateText(hass, ENTITIES.outdoorFeelsLike), ENTITIES.outdoorFeelsLike)}
      ${kv("Wetterzustand", weatherConditionLabel(inp.weather_condition ?? "missing"))}
      ${metric("Forecast +3h", stateText(hass, ENTITIES.forecastTemp3h), ENTITIES.forecastTemp3h)}
      ${kv("Licht (Lux)", inp.outdoor_lux ?? "nicht geladen")}
      ${kv("Sonnenstand", inp.sun_elevation ?? "nicht geladen")}
    </div>
    <div class="card">
      <h2>${icon("mdi:thermometer-lines")}Breakdown</h2>
      ${kv("Bodenplatten-Einfluss", tempText(br.floor_slab_offset ?? "missing"))}
      ${kv("Gefühlt-Korrektur", tempText(br.feels_like_offset ?? "missing"))}
      ${kv("Wetterkorrektur", tempText(br.weather_offset ?? "missing"))}
      ${kv("Prognosekorrektur", tempText(br.forecast_offset ?? "missing"))}
      ${kv("Lichtbonus", tempText(br.lux_bonus ?? "missing"))}
      ${kv(`${effectiveOutdoorLabel("large")} (${effectiveOutdoorLabel("technical")})`, tempText(br.effective_temperature ?? stateText(hass, ENTITIES.effectiveTemp)))}
      ${kv("Datenqualität", qualityLabel(br.input_quality ?? "missing"))}
      ${kv("Außengefühl", feeling.outdoor_feeling_label)}
      ${kv("Begründung", feeling.outdoor_feeling_reason)}
    </div>
    <div class="card">
      <h2>${icon("mdi:link-variant")}Source Entities</h2>
      ${Object.entries(sourceEntities).map(([k, v]) => kv(k, v)).join("") || kv("Quellen", "nicht geladen")}
    </div>
    <div class="card">
      <h2>${icon("mdi:weather-partly-cloudy")}Weather Resolver</h2>
      ${kv("Forecast +3h Wert", forecastResolution.value ?? inp.forecast_temperature ?? "missing")}
      ${kv("Forecast Quelle", forecastResolution.source ?? "missing")}
      ${kv("Forecast Qualität", qualityLabel(forecastResolution.quality ?? "missing"))}
      ${kv("Weather Entity", forecastResolution.weather_entity ?? sourceEntities.weather_entity ?? "missing")}
      ${kv("Zielzeit +3h", localDateTime(forecastResolution.target_time ?? "missing"))}
      ${kv("Forecast Zeitpunkt", localDateTime(forecastResolution.forecast_datetime ?? "missing"))}
      ${kv("Forecast Grund", compactReason(forecastResolution.reason ?? "missing"))}
      ${kv("Forecast Fallback", forecastResolution.fallback_used ?? false)}
      ${kv("Feels-like Wert", feelsLikeResolution.value ?? inp.feels_like_temperature ?? "missing")}
      ${kv("Feels-like Quelle", feelsLikeResolution.source ?? "missing")}
      ${kv("Feels-like Qualität", qualityLabel(feelsLikeResolution.quality ?? "missing"))}
      ${kv("Feels-like Grund", compactReason(feelsLikeResolution.reason ?? "missing"))}
      ${kv("Feels-like Fallback", feelsLikeResolution.fallback_used ?? false)}
    </div>
  </div>`;
}

function renderWeather(hass, app) {
  const br = effectiveBreakdown(hass, app);
  const inp = effectiveInputs(hass, app);
  const feeling = outdoorFeeling(hass, app);
  return `<div class="card">
    <div class="room-head">
      <div class="hero-icon">${icon("mdi:weather-partly-cloudy")}</div>
      <div>
        <h2>Außenlage und ${esc(effectiveOutdoorLabel("chip"))}</h2>
        <p class="muted">${esc(UX_LABELS.effectiveOutdoor.explanation)}</p>
      </div>
      <div class="target">${esc(tempText(br.effective_temperature ?? stateText(hass, ENTITIES.effectiveTemp)))}</div>
    </div>
    <div class="grid cols-4">
      ${miniStat("mdi:thermometer", tempText(inp.real_temperature ?? br.real_temperature ?? "missing"), "Real draußen")}
      ${miniStat("mdi:thermometer-water", tempText(inp.feels_like_temperature ?? stateText(hass, ENTITIES.outdoorFeelsLike)), "Gefühlt")}
      ${miniStat("mdi:weather-cloudy-clock", tempText(inp.forecast_temperature ?? stateText(hass, ENTITIES.forecastTemp3h)), "Prognose +3h")}
      ${miniStat("mdi:weather-partly-cloudy", weatherConditionLabel(inp.weather_condition ?? stateText(hass, ENTITIES.weatherCondition, "missing")), "Wetterzustand")}
      ${miniStat("mdi:emoticon-outline", feeling.outdoor_feeling_label, "Außengefühl")}
    </div>
  </div>
  <div class="section">${renderEffective(hass, app)}</div>`;
}

function actionButton(id, label, iconName, primary, available) {
  return `<button class="action ${primary ? "primary" : ""}" data-action="${esc(id)}" ${available ? "" : "disabled"} title="${available ? "" : "missing service/button"}">
    ${icon(iconName)}<span>${esc(available ? label : `${label}: missing service/button`)}</span>
  </button>`;
}

function plannedActionCard(hass, app, zone) {
  const meta = ZONES[zone];
  const plan = zonePlan(hass, zone, app);
  const current = zoneRoomTemperature(hass, app, zone);
  const applyNeeded = plan.plan_hash && plan.last_applied_plan_hash ? plan.plan_hash !== plan.last_applied_plan_hash : plan.apply_needed;
  return `<div class="card">
    <h2>${icon(zoneIcon(zone))}${esc(meta.label)}</h2>
    ${kv("Geplante Aktion", `${modeLabel(plan.profile)} auf ${tempText(policyTarget(plan))}`)}
    ${kv("Thermostat-Ziel", `${tempText(thermostatTarget(plan))}${numberLike(plan.floor_slab_delta) ? ` (${deltaText(plan.floor_slab_delta)})` : ""}`)}
    ${kv("Aktuelle Temperatur", current)}
    ${kv("Apply nötig", applyNeeded === true ? "Ja" : applyNeeded === false ? "Nein" : "unbekannt")}
    ${kv("Grund", compactReason(primaryReason(plan, zone), zone))}
    <div class="chip-row">
      <span class="pill ${modeClass(plan.profile)}">Modus: ${esc(modeLabel(plan.profile))}</span>
      ${plan.apply_blocked === "on" ? `<span class="pill purple">Begrenzt</span>` : ""}
    </div>
  </div>`;
}

function renderApply(hass, app) {
  const applyNow = serviceAvailable(hass, "apply_now");
  const dryRun = serviceAvailable(hass, "dry_run");
  const payload = debugPayload(hass, app);
  const lastApply = endpointDebug(app).last_apply_result || payload.last_apply_result || null;
  const applyActive = stateText(hass, ENTITIES.applyActive);
  const lastApplyState = stateText(hass, ENTITIES.lastApply);
  const lastApplyTime = lastApply?.timestamp
    ?? (["never", "missing", "unknown", "unavailable"].includes(String(lastApplyState).toLowerCase()) ? lastApplyState : lastApplyState)
    ?? stateObj(hass, ENTITIES.lastApply)?.last_changed;
  return `<div class="grid cols-4">
    <div class="card apply-hero">
      <div class="room-head">
        <div class="hero-icon">${icon(applyActive === "on" ? "mdi:robot-outline" : "mdi:robot-off-outline")}</div>
        <div>
          <h2>Automatik derzeit ${applyActive === "on" ? "an" : "aus"}</h2>
          <p class="muted">${esc(applyActive === "on" ? "Die Policy darf passende Heizänderungen automatisch anwenden." : "Die Automatik ist deaktiviert. Du kannst Einstellungen manuell anwenden oder einen Dry Run durchführen.")}</p>
          ${statusChip(payload.manual_apply_possible ?? attr(hass, ENTITIES.applyStatus, "manual_apply_possible", "missing"), "Manuelles Anwenden möglich")}
        </div>
      </div>
    </div>
    <div class="card">
      <h2>${icon("mdi:calendar-clock")}Letzter Apply</h2>
      <div class="target">${esc(formatRelativeOrDateTime(lastApplyTime))}</div>
      <p class="muted">${esc(lastApply ? formatDateTimeLocal(lastApplyTime) : "Bisher wurde noch nichts angewendet.")}</p>
    </div>
    <div class="card">
      <h2>${icon("mdi:flask-outline")}Dry Run</h2>
      <div class="target">${esc(dryRun ? "Verfügbar" : "Fehlt")}</div>
      <p class="muted">Simulierte Vorschau jederzeit möglich.</p>
    </div>
    <div class="card">
      <h2>${icon("mdi:shield-check-outline")}Sicherheit</h2>
      <div class="target">${esc(stateText(hass, ENTITIES.applyReady) === "on" ? "Bereit" : "Geschützt")}</div>
      <p class="muted">Cooldown und Sperren verhindern zu häufige Änderungen.</p>
    </div>
  </div>
  <div class="section card">
    <h2>${icon("mdi:gesture-tap-button")}Schnellaktionen</h2>
    <div class="actions">
      ${actionButton("dry-run-global", "Global Dry Run", "mdi:flask-outline", false, dryRun)}
      ${actionButton("apply-global", "Global anwenden", "mdi:play-outline", true, applyNow)}
      ${actionButton("apply-living_room", "Wohnzimmer anwenden", "mdi:sofa-outline", false, applyNow)}
      ${actionButton("apply-kitchen", "Küche anwenden", "mdi:silverware-fork-knife", false, applyNow)}
      ${actionButton("apply-bathroom", "Bad anwenden", "mdi:bathtub-outline", false, applyNow)}
      ${actionButton("apply-bathroom_fan", "Badlüfter anwenden", "mdi:fan", false, applyNow)}
    </div>
  </div>
  <div class="section card">
    <h2>${icon("mdi:clipboard-check-outline")}Was würde jetzt passieren?</h2>
    <p class="muted">Vorschau auf Basis der aktuellen Bedingungen und Pläne.</p>
    <div class="grid cols-3">
      ${plannedActionCard(hass, app, "living_room")}
      ${plannedActionCard(hass, app, "kitchen")}
      ${plannedActionCard(hass, app, "bathroom")}
    </div>
  </div>
  <div class="section card">
    <h2>${icon("mdi:console-line")}Expertenbereich: Apply-Details</h2>
    <details class="expert">
      <summary>Letzten Apply-Versuch und Dry-Run-Service-Calls anzeigen</summary>
      ${renderApplySummary(lastApply)}
      ${lastApply ? jsonDetails("Details als JSON anzeigen", lastApply) : ""}
      ${lastApply?.dry_run ? jsonDetails("Dry-Run-Service-Calls als JSON anzeigen", lastApply.actions.map((a) => ({
        zone: a.zone,
        reason: a.reason,
        target_entity_id: a.target_entity_id,
        service_calls: a.service_calls,
        details: a.details,
      }))) : `<div class="notice">Kein Dry Run aktiv oder noch nicht ausgeführt.</div>`}
    </details>
  </div>`;
}

function renderInputs(hass, app) {
  const inputs = inputItems(hass, app);
  if (!inputs.length) {
    return debugEndpointNotice(app);
  }
  const rows = inputs.map((item) => `<tr>
    <td>${esc(item.role || "other")}</td>
    <td class="mono">${esc(item.key || "")}</td>
    <td class="mono">${esc(asText(item.entity_id))}</td>
    <td class="mono">${esc(asText(item.state))}</td>
    <td>${statusChip(item.status || "missing")}</td>
    <td>${esc(item.source || "missing")}</td>
  </tr>`).join("");
  return `<div class="table-wrap">
    <table><thead><tr><th>Rolle</th><th>Key</th><th>Entity ID</th><th>State</th><th>Status</th><th>Quelle</th></tr></thead><tbody>
      ${rows || `<tr><td colspan="6" class="muted">not exposed yet</td></tr>`}
    </tbody></table>
  </div>`;
}

function importantInputIssues(hass, app) {
  return inputItems(hass, app)
    .filter((item) => !["ok", undefined, null].includes(item.status))
    .map((item) => `${item.key}: ${item.status} (${item.entity_id || "keine Entity"})`);
}

function diagnosticPackage(hass, app, format = "markdown") {
  const full = endpointDebug(app);
  const payload = debugPayload(hass, app);
  const planMap = plans(hass, app);
  const perf = full.performance || payload.performance || {};
  const effective = effectiveBreakdown(hass, app);
  const effectiveInputsData = effectiveInputs(hass, app);
  const context = contextSnapshot(hass, app);
  const bath = bathroomDebug(hass, app);
  const fan = bath.fan_plan || {};
  const status = {
    timestamp: full.timestamp || new Date().toISOString(),
    integration_version: full.integration_version || payload.integration_version || "unknown",
    system_ready: payload.system_ready ?? stateText(hass, ENTITIES.systemReady),
    auto_apply: payload.apply_active ?? stateText(hass, ENTITIES.applyActive),
    apply_status: stateText(hass, ENTITIES.applyStatus),
    apply_status_label: reasonLabel(stateText(hass, ENTITIES.applyStatus)),
    effective_outdoor_temperature: effective.effective_temperature ?? stateText(hass, ENTITIES.effectiveTemp),
    weather_resolver: {
      real_temperature: effectiveInputsData.real_temperature,
      forecast_temperature: effectiveInputsData.forecast_temperature,
      feels_like_temperature: effectiveInputsData.feels_like_temperature,
      weather_condition: effectiveInputsData.weather_condition,
      forecast_reason: effectiveInputsData.forecast_resolution?.reason,
      feels_like_reason: effectiveInputsData.feels_like_resolution?.reason,
    },
    outdoor_feeling: outdoorFeeling(hass, app),
    context: {
      presence_personal: context.presence_personal?.value,
      presence_household: context.presence_household?.value,
      presence_band: context.presence_band?.value,
      day_state: context.day_state?.value,
      bio_state: context.bio_state?.value,
    },
    plans: Object.fromEntries(Object.entries(planMap).map(([zone, plan]) => [zone, {
      profile: plan.profile,
      target_temperature: plan.target_temperature,
      policy_target_temperature: policyTarget(plan),
      floor_slab_delta: plan.floor_slab_delta,
      thermostat_target_temperature: thermostatTarget(plan),
      room_comfort: plan.room_comfort,
      policy_reason: plan.reason,
      apply_blocker: plan.apply_block_reason,
      decision_path: plan.decision_path,
      plan_hash: plan.plan_hash,
      policy_config_hash: plan.policy_config_hash,
    }])),
    bathroom_fan: {
      mode: fanModeLabel(fan.mode),
      reason: fanReasonLabel(fan.reason || fan.fan_reason),
      target_switch_state: fan.target_switch_state,
      apply_blocker: fan.apply_block_reason,
      plan_hash: fan.plan_hash,
    },
    performance: {
      recalculate_count: perf.recalculate_count,
      last_recalculate_reason: perf.last_recalculate_reason,
      forecast_cache: {
        hit: perf.weather_forecast_cache_hit,
        age: perf.weather_forecast_cache_age,
        last_fetch_at: perf.weather_forecast_last_fetch_at,
      },
      entity_publish_changed_count: perf.entity_publish_changed_count,
      entity_publish_skipped_count: perf.entity_publish_skipped_count,
    },
    last_apply: payload.last_apply_result || full.last_apply_result || null,
    input_issues: importantInputIssues(hass, app),
  };
  if (format === "json") return JSON.stringify(status, null, 2);
  const lineForZone = (zone, label) => {
    const plan = status.plans[zone] || {};
    return `- ${label}: ${modeLabel(plan.profile)} Policy ${tempText(plan.policy_target_temperature)}, Thermostat ${tempText(plan.thermostat_target_temperature)}, Grund: ${compactReason(plan.policy_reason, zone)}`;
  };
  return `# Benni Climate Policy Diagnosepaket

## Status
- Zeitstempel: ${formatTimeDateLocal(status.timestamp)}
- Integration Version: ${status.integration_version}
- System ready: ${status.system_ready}
- Auto apply: ${status.auto_apply}
- Apply status: ${status.apply_status_label}
- ${effectiveOutdoorLabel("large")}: ${tempText(status.effective_outdoor_temperature)}

## Wetter / ${effectiveOutdoorLabel("chip")} (${effectiveOutdoorLabel("technical")})
- Real: ${tempText(status.weather_resolver.real_temperature)}
- Forecast +3h: ${tempText(status.weather_resolver.forecast_temperature)}
- Feels-like: ${tempText(status.weather_resolver.feels_like_temperature)}
- Zustand: ${weatherConditionLabel(status.weather_resolver.weather_condition)}
- Außengefühl: ${status.outdoor_feeling.outdoor_feeling_label}
- Grund Außengefühl: ${status.outdoor_feeling.outdoor_feeling_reason}
- Forecast reason: ${reasonLabel(status.weather_resolver.forecast_reason)}

## Kontext
- Anwesenheit: ${presenceSummary(hass, app)}
- Presence personal: ${translateContextValue("presence_personal", status.context.presence_personal)}
- Presence household: ${translateContextValue("presence_household", status.context.presence_household)}
- Presence band: ${translateContextValue("presence_band", status.context.presence_band)}
- Bio: ${translateContextValue("bio_state", status.context.bio_state)}
- Day state: ${translateContextValue("day_state", status.context.day_state)}

## Aktuelle Entscheidung
${lineForZone("living_room", "Wohnzimmer")}
${lineForZone("kitchen", "Küche")}
${lineForZone("bathroom", "Bad")}
- Badlüfter: ${fanModeLabel(status.bathroom_fan.mode)}, Grund: ${fanReasonLabel(status.bathroom_fan.reason || status.bathroom_fan.apply_blocker)}

## Hash-Basis
- Living plan hash: ${displayValue(status.plans.living_room?.plan_hash)}
- Kitchen plan hash: ${displayValue(status.plans.kitchen?.plan_hash)}
- Bathroom plan hash: ${displayValue(status.plans.bathroom?.plan_hash)}
- Policy config hash: ${displayValue(status.plans.living_room?.policy_config_hash || status.plans.bathroom?.policy_config_hash)}

## Performance
- recalculate_count: ${displayValue(status.performance.recalculate_count)}
- last_recalculate_reason: ${reasonLabel(status.performance.last_recalculate_reason)}
- forecast_cache_hit: ${displayValue(status.performance.forecast_cache.hit)}
- forecast_cache_age: ${displayValue(status.performance.forecast_cache.age)}
- entity_publish_changed_count: ${displayValue(status.performance.entity_publish_changed_count)}
- entity_publish_skipped_count: ${displayValue(status.performance.entity_publish_skipped_count)}

## Letzter Apply / Dry Run
- Status: ${reasonLabel(status.last_apply?.status ?? "kein Apply")}
- Reason: ${reasonLabel(status.last_apply?.reason ?? "kein Apply")}
- Actions: ${Array.isArray(status.last_apply?.actions) ? status.last_apply.actions.length : 0}

## Input-Status kompakt
${status.input_issues.length ? status.input_issues.map((item) => `- ${item}`).join("\n") : "- Keine missing/unavailable/conflict Inputs im Snapshot."}
`;
}

function renderDebug(hass, app) {
  const dbg = debugAttrs(hass);
  const payload = debugPayload(hass, app);
  const full = endpointDebug(app);
  const planMap = plans(hass, app);
  if (!Object.keys(full).length) {
    return debugEndpointNotice(app);
  }
  const paths = Object.entries(planMap).map(([zone, plan]) => ({
    zone,
    reason: plan.reason,
    apply_block_reason: plan.apply_block_reason,
    decision_path: plan.decision_path,
  }));
  const skipReason = payload.last_apply_result?.reason
    || attr(hass, ENTITIES.applyStatus, "reason", null)
    || Object.values(planMap).map((p) => p.apply_block_reason).filter(Boolean).join(", ")
    || "none";
  const perf = full.performance || payload.performance || {};
  const packageText = app?._diagnosticsPackage || "";
  const tab = app?._debugTab || "status";
  const tabs = [
    ["status", "Status"],
    ["decision", "Entscheidung"],
    ["package", "Diagnosepaket"],
    ["raw", "Rohdaten"],
  ].map(([id, label]) => `<button data-debug-tab="${esc(id)}" class="${tab === id ? "active" : ""}">${esc(label)}</button>`).join("");
  const statusPanel = `<div class="section grid cols-2">
    <div class="card"><h2>${icon("mdi:speedometer")}Performance</h2>
      ${kv("Letzte Bewertung", perf.last_evaluate_duration_ms ?? "nicht geladen", "mono")}
      ${kv("Durchschnitt Bewertung", perf.average_evaluate_duration_ms ?? "nicht geladen", "mono")}
      ${kv("p95 Bewertung", perf.p95_evaluate_duration_ms ?? "nicht geladen", "mono")}
      ${kv("Letzter Apply", perf.last_apply_duration_ms ?? "nicht geladen", "mono")}
      ${kv("Letzter Forecast", perf.last_forecast_duration_ms ?? "nicht geladen", "mono")}
      ${kv("Aktuelle Last", perf.update_load ?? "nicht geladen")}
      ${kv("Debug Endpoint", app?._debugLastFetch ? localDateTime(app._debugLastFetch) : "nie", "mono")}
    </div>
    <div class="card"><h2>${icon("mdi:account-clock-outline")}Letzter Kontext-Snapshot</h2>
      ${renderContext(hass, app)}
    </div>
    <div class="card"><h2>${icon("mdi:clipboard-pulse-outline")}Letzter Apply-Versuch</h2>
      ${renderApplySummary(payload.last_apply_result)}
      ${jsonDetails("Apply-Versuch als JSON anzeigen", payload.last_apply_result || attr(hass, ENTITIES.applyStatus, "result", null))}
    </div>
    <div class="card"><h2>${icon("mdi:block-helper")}Letzter Skip-/Blockgrund</h2>${kv("Grund", compactReason(skipReason))}${kv("Raw", skipReason, "mono")}</div>
  </div>`;
  const decisionPanel = `<div class="section grid cols-2">
    <div class="card"><h2>${icon("mdi:routes")}Letzter Entscheidungsweg</h2>
      ${paths.map((item, index) => `<div class="fact-row"><span>${index + 1}. ${esc(ZONES[item.zone]?.label || item.zone)}</span><b>${esc(compactReason(item.reason || item.apply_block_reason, item.zone))}</b></div>`).join("")}
      ${jsonDetails("Pfad als JSON anzeigen", paths)}
    </div>
    <div class="card"><h2>${icon("mdi:fingerprint")}Hash-Basis</h2>${jsonDetails("Hash-Basis als JSON anzeigen", Object.fromEntries(Object.entries(planMap).map(([zone, plan]) => [zone, {
      zone: plan.zone,
      profile: plan.profile,
      policy_target_temperature: policyTarget(plan),
      floor_slab_delta: plan.floor_slab_delta,
      thermostat_target_temperature: thermostatTarget(plan),
      blocked_by: plan.blocked_by,
      effective_outdoor_temperature: plan.effective_outdoor_temperature,
      plan_hash: plan.plan_hash,
    }])))}</div>
    <div class="card"><h2>${icon("mdi:database-search-outline")}Konfigurierte Inputs</h2>
      ${renderInputs(hass, app)}
    </div>
    <div class="card"><h2>${icon("mdi:tune-vertical-variant")}Thresholds</h2>${jsonDetails("Thresholds als JSON anzeigen", thresholds(hass, app))}</div>
  </div>`;
  const packagePanel = `<div class="section card">
    <h2>${icon("mdi:clipboard-text-outline")}Diagnosepaket</h2>
    <p class="muted">Kompaktes Copy/Paste-Paket für Codex/Claude ohne große Forecast-Listen oder volatile Massendaten.</p>
    <div class="actions">
      ${actionButton("diagnostics-copy", "Diagnosepaket kopieren", "mdi:content-copy", false, true)}
      ${actionButton("diagnostics-show", "Diagnosepaket anzeigen", "mdi:eye-outline", false, true)}
      ${actionButton("diagnostics-copy-json", "Als JSON kopieren", "mdi:code-json", false, true)}
    </div>
    ${packageText ? `<textarea class="pre mono diagnostics-package" readonly>${esc(packageText)}</textarea>` : ""}
    ${jsonDetails("Diagnosepaket JSON anzeigen", JSON.parse(diagnosticPackage(hass, app, "json")))}
  </div>`;
  const rawPanel = `<div class="section grid cols-2">
    <div class="card"><h2>${icon("mdi:code-json")}Debug Summary</h2>${jsonDetails("Recorder-sichere Attribute anzeigen", dbg)}</div>
    <div class="card"><h2>${icon("mdi:database-eye-outline")}Debug Endpoint</h2>${jsonDetails("Kompletten Endpoint anzeigen", full)}</div>
  </div>`;
  const panels = { status: statusPanel, decision: decisionPanel, package: packagePanel, raw: rawPanel };
  return `<div class="grid cols-4">
    ${miniStat("mdi:refresh", perf.recalculate_count ?? dbg.recalculate_count ?? "unbekannt", "Recalculate Count")}
    ${miniStat("mdi:lightning-bolt-outline", reasonLabel(payload.last_recalculate_reason ?? dbg.last_recalculate_reason ?? skipReason), "Letzter Grund")}
    ${miniStat("mdi:cloud-check-outline", payload.forecast_cache_status ?? dbg.forecast_cache_status ?? "unbekannt", "Forecast-Cache")}
    ${miniStat("mdi:publish", payload.publish_count_24h ?? dbg.publish_count_24h ?? "unbekannt", "Publish 24h")}
  </div>
  <div class="section segmented">${tabs}</div>
  ${panels[tab] || statusPanel}`;
}

const RENDERERS = {
  overview: renderOverview,
  zones: renderZones,
  weather: renderWeather,
  thresholds: renderThresholds,
  apply: renderApply,
  debug: renderDebug,
};

class BcpApp extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._view = "overview";
    this._timer = null;
    this._tuningDraft = null;
    this._tuningBase = null;
    this._tuningError = "";
    this._tuningTab = "season";
    this._debugTab = "status";
    this._diagnosticsPackage = "";
    this._diagnosticsPackageFormat = "markdown";
    this._debugPayload = null;
    this._debugError = "";
    this._debugFetchInFlight = null;
    this._debugLastFetch = 0;
    this._lastHtml = "";
  }

  set hass(value) {
    this._hass = value;
    this._ensureDebugFetch();
    this._scheduleRender();
  }

  get hass() {
    return this._hass;
  }

  connectedCallback() {
    this._render();
  }

  disconnectedCallback() {
    clearTimeout(this._timer);
  }

  _scheduleRender() {
    clearTimeout(this._timer);
    this._timer = setTimeout(() => this._render(), 120);
  }

  _ensureDebugFetch(force = false) {
    if (!this._hass || !this._hass.callApi || this._debugFetchInFlight) return;
    if (!force && !this._viewNeedsDebug()) return;
    const now = Date.now();
    if (!force && this._debugLastFetch && now - this._debugLastFetch < DEBUG_REFRESH_MS) return;
    this._fetchDebugPayload(force);
  }

  async _fetchDebugPayload(force = false) {
    if (!this._hass || !this._hass.callApi) return;
    if (!force && this._debugFetchInFlight) return;
    if (!force && !this._viewNeedsDebug()) return;
    const now = Date.now();
    if (!force && this._debugLastFetch && now - this._debugLastFetch < DEBUG_REFRESH_MS) return;
    // A refresh after saving supersedes requests that may contain the old settings.
    const request = {};
    this._debugFetchInFlight = request;
    this._debugLastFetch = now;
    try {
      const payload = await this._hass.callApi("GET", DEBUG_API_PATH);
      if (this._debugFetchInFlight !== request) return;
      this._debugPayload = payload;
      this._debugError = "";
    } catch (err) {
      if (this._debugFetchInFlight === request) {
        this._debugError = err.message || String(err);
      }
    } finally {
      if (this._debugFetchInFlight === request) {
        this._debugFetchInFlight = null;
        this._scheduleRender();
      }
    }
  }

  _render() {
    const nav = NAV.map(([id, label, iconName]) => `<button data-view="${id}" class="${id === this._view ? "active" : ""}">
      ${icon(iconName)}<span>${esc(label)}</span>
    </button>`).join("");
    const view = NAV.find(([id]) => id === this._view) || NAV[0];
    const renderer = RENDERERS[view[0]] || renderOverview;
    const hass = this._hass;
    if (hass && this._viewNeedsDebug() && !this._debugPayload && !this._debugFetchInFlight) {
      this._ensureDebugFetch();
    }
    const sys = stateText(hass, ENTITIES.systemReady);
    const apply = stateText(hass, ENTITIES.applyActive);
    const effective = stateText(hass, ENTITIES.effectiveTemp);
    const subtitles = {
      overview: "Bedingungen, Konsequenzen und Policy-Zustand auf einen Blick",
      zones: "Übersicht und Status deiner Räume",
      weather: "Außenwerte, Prognose und Heizwert-Berechnung",
      apply: "Apply, Dry Run und Vorschau",
      thresholds: "Heizstrategie je Jahreszeit optimieren",
      debug: "Tiefgehende Analyse und Systeminformationen",
    };
    let content;
    try {
      content = hass ? renderer(hass, this) : `<div class="notice">Home Assistant state wird geladen.</div>`;
    } catch (err) {
      content = `<div class="notice">Render-Fehler: ${esc(err.message || err)}</div>`;
    }

    const html = `<style>${CSS}</style>
      <div class="app">
        <aside class="sidebar">
          <div class="brand"><div class="brand-badge">${icon("mdi:home-thermometer-outline")}</div><div><b>Benni Climate Policy</b><small>Smart Climate Control</small></div></div>
          <nav class="nav">${nav}</nav>
          <div class="side-foot">
            <div class="side-status">${statusChip(sys, sys === "on" ? "System bereit" : "System prüfen")}</div>
            <div>${esc(sys === "on" ? "Alle Dienste online" : "Bitte Status prüfen")}</div>
            <br>Panel: /${esc("benni-climate-policy")}
          </div>
        </aside>
        <main class="main">
          <header class="head">
            <div><h1>${esc(view[1])}</h1><p>${esc(subtitles[view[0]] || "benni_climate_policy")}</p></div>
            <div class="chips">
              ${statusChip(sys, sys === "on" ? "Bereit" : `Ready ${sys}`)}
              ${statusChip(apply, apply === "on" ? "Apply an" : "Apply aus")}
              ${statusChip(effective === "missing" ? "missing" : "ok", `${effectiveOutdoorLabel("chip")} ${tempText(effective)}`)}
            </div>
          </header>
          <div id="content">${content}</div>
        </main>
      </div>`;
    if (this._lastHtml === html) return;
    this._lastHtml = html;
    this.shadowRoot.innerHTML = html;
    this.shadowRoot.querySelectorAll("[data-view]").forEach((btn) => {
      btn.addEventListener("click", () => {
        this._view = btn.dataset.view;
        this._ensureDebugFetch();
        this._render();
      });
    });
    this.shadowRoot.querySelectorAll("[data-action]").forEach((btn) => {
      btn.addEventListener("click", () => this._handleAction(btn.dataset.action));
    });
    this.shadowRoot.querySelectorAll("[data-tuning-key]").forEach((input) => {
      input.addEventListener("input", () => this._handleTuningInput(input));
      input.addEventListener("change", () => this._handleTuningInput(input));
    });
    this.shadowRoot.querySelectorAll("[data-tuning-tab]").forEach((btn) => {
      btn.addEventListener("click", () => {
        this._tuningTab = btn.dataset.tuningTab;
        this._render();
      });
    });
    this.shadowRoot.querySelectorAll("[data-debug-tab]").forEach((btn) => {
      btn.addEventListener("click", () => {
        this._debugTab = btn.dataset.debugTab;
        this._render();
      });
    });
  }

  _viewNeedsDebug() {
    return DEBUG_VIEWS.has(this._view);
  }

  _ensureTuningDraft(data) {
    const values = data.values || {};
    const signature = JSON.stringify(values);
    if (!this._tuningDraft || this._tuningBaseSignature !== signature) {
      this._tuningDraft = { ...values };
      this._tuningBase = { ...values };
      this._tuningBaseSignature = signature;
      this._tuningError = "";
    }
  }

  _dirtyTuningKeys(data) {
    const values = data.values || {};
    const draft = this._tuningDraft || values;
    return Object.keys(draft).filter((key) => String(draft[key] ?? "") !== String(values[key] ?? ""));
  }

  _handleTuningInput(input) {
    if (!this._tuningDraft) return;
    const key = input.dataset.tuningKey;
    this._tuningDraft[key] = input.type === "checkbox" ? input.checked : input.value;
    this._tuningError = "";
    this._scheduleRender();
  }

  _thresholdKey(band, field) {
    return `threshold_${band}_${field}`;
  }

  _validateNumber(key, value, { min = null, max = null, integer = false } = {}) {
    if (value === "" || value === null || value === undefined) {
      throw new Error(`${key} darf nicht leer sein`);
    }
    const number = Number(value);
    if (!Number.isFinite(number)) throw new Error(`${key} muss eine Zahl sein`);
    if (integer && !Number.isInteger(number)) throw new Error(`${key} muss eine ganze Zahl sein`);
    if (min !== null && number < min) throw new Error(`${key} muss >= ${min} sein`);
    if (max !== null && number > max) throw new Error(`${key} muss <= ${max} sein`);
    return integer ? Math.trunc(number) : number;
  }

  _validateTuningDraft(data) {
    const draft = this._tuningDraft || {};
    const payload = {};
    const dirty = this._dirtyTuningKeys(data);
    const intKeys = new Set([
      "apply_cooldown_seconds",
      "startup_block_seconds",
      "bath_fan_acute_max_minutes",
      "bath_fan_afterrun_max_minutes",
      "bath_fan_stoss_interval_hours",
      "bath_fan_stoss_duration_minutes",
      "bath_fan_hard_cap_minutes",
      "bath_fan_cooldown_minutes",
      "bath_diffuser_max_minutes",
    ]);
    const weightKeys = new Set(["feels_like_damping", "forecast_weight"]);
    dirty.forEach((key) => {
      if (key.endsWith("_disabled")) {
        payload[key] = draft[key] === true || draft[key] === "true";
      } else if (key === "floor_slab_mode") {
        if (!["dynamic_3day", "static_fallback"].includes(String(draft[key]))) throw new Error("floor_slab_mode ist ungültig");
        payload[key] = String(draft[key]);
      } else if (key === "lux_reference") {
        payload[key] = this._validateNumber(key, draft[key], { min: 1 });
      } else if (weightKeys.has(key)) {
        payload[key] = this._validateNumber(key, draft[key], { min: 0, max: 1 });
      } else if (key.endsWith("_min_hold_minutes")) {
        payload[key] = this._validateNumber(key, draft[key], { min: 0, integer: true });
      } else if (intKeys.has(key)) {
        payload[key] = this._validateNumber(key, draft[key], { min: 1, integer: true });
      } else if (key.endsWith("_floor_slab_delta") || key === "floor_slab_min_delta" || key === "floor_slab_max_delta" || key.endsWith("_anchor_warm_delta") || key.endsWith("_anchor_mild_delta") || key.endsWith("_anchor_cool_delta") || key.endsWith("_anchor_cold_delta") || key.endsWith("_anchor_freezing_delta")) {
        payload[key] = this._validateNumber(key, draft[key], { min: 0, max: 5 });
      } else if (key === "bath_humidity_ground_heat_teff_limit") {
        payload[key] = this._validateNumber(key, draft[key], { min: -30, max: 35 });
      } else if (key === "bath_humidity_ground_heat_target" || key === "bath_humidity_ground_heat_off_at") {
        payload[key] = this._validateNumber(key, draft[key], { min: 5, max: 30 });
      } else if (key.endsWith("_heat_on_below") || key.endsWith("_heat_off_at") || key.includes("_anchor_")) {
        payload[key] = this._validateNumber(key, draft[key], { min: -30, max: 35 });
      } else if (key.endsWith("_threshold") || key.startsWith("setpoint_") || key.startsWith("bath_setpoint_")) {
        payload[key] = this._validateNumber(key, draft[key], { min: 0, max: 35 });
      } else {
        payload[key] = this._validateNumber(key, draft[key]);
      }
    });
    THRESHOLD_BANDS.forEach(([band]) => {
      const off = this._validateNumber(this._thresholdKey(band, "off_threshold"), draft[this._thresholdKey(band, "off_threshold")], { min: 0, max: 35 });
      const comfortDisabled = draft[this._thresholdKey(band, "comfort_disabled")] === true || draft[this._thresholdKey(band, "comfort_disabled")] === "true";
      const boostDisabled = draft[this._thresholdKey(band, "boost_disabled")] === true || draft[this._thresholdKey(band, "boost_disabled")] === "true";
      const comfortRaw = draft[this._thresholdKey(band, "comfort_threshold")];
      const boostRaw = draft[this._thresholdKey(band, "boost_threshold")];
      const comfort = comfortDisabled && comfortRaw === "" ? null : this._validateNumber(this._thresholdKey(band, "comfort_threshold"), comfortRaw, { min: 0, max: 35 });
      const boost = boostDisabled && boostRaw === "" ? null : this._validateNumber(this._thresholdKey(band, "boost_threshold"), boostRaw, { min: 0, max: 35 });
      this._validateNumber(this._thresholdKey(band, "floor_slab_delta"), draft[this._thresholdKey(band, "floor_slab_delta")], { min: 0, max: 5 });
      if (!comfortDisabled && comfort > off) throw new Error(`${band}: comfort_threshold darf nicht über off_threshold liegen`);
      if (!boostDisabled && comfortDisabled) throw new Error(`${band}: boost_threshold kann nicht aktiv sein, wenn comfort deaktiviert ist`);
      if (!boostDisabled && boost > comfort) throw new Error(`${band}: boost_threshold darf nicht über comfort_threshold liegen`);
    });
    return payload;
  }

  async _handleAction(action) {
    if (!this._hass) return;
    try {
      if (action === "dry-run-global") {
        await this._hass.callService(DOMAIN, "dry_run", {});
        await this._fetchDebugPayload(true);
      } else if (action === "apply-global") {
        await this._hass.callService(DOMAIN, "apply_now", {});
        await this._fetchDebugPayload(true);
      } else if (action === "tuning-save") {
        const payload = this._validateTuningDraft(tuningOptions(this._hass, this));
        if (!Object.keys(payload).length) {
          this._toast("Keine Änderungen");
          return;
        }
        await this._hass.callService(DOMAIN, "update_options", { options: payload });
        await this._fetchDebugPayload(true);
        this._tuningDraft = null;
        this._tuningBase = null;
        this._toast("Tuning gespeichert");
      } else if (action === "tuning-reset-all") {
        const data = tuningOptions(this._hass, this);
        const keys = Object.values(data.sections || {}).flat();
        await this._hass.callService(DOMAIN, "reset_options", { keys });
        await this._fetchDebugPayload(true);
        this._tuningDraft = null;
        this._tuningBase = null;
        this._toast("Tuning zurückgesetzt");
      } else if (action.startsWith("tuning-reset-section-")) {
        const section = action.replace("tuning-reset-section-", "");
        const keys = (tuningOptions(this._hass, this).sections || {})[section] || [];
        await this._hass.callService(DOMAIN, "reset_options", { keys });
        await this._fetchDebugPayload(true);
        this._tuningDraft = null;
        this._tuningBase = null;
        this._toast("Abschnitt zurückgesetzt");
      } else if (action.startsWith("tuning-reset-band-")) {
        const band = action.replace("tuning-reset-band-", "");
        const bandData = (tuningOptions(this._hass, this).threshold_bands || {})[band] || {};
        const keys = Object.values(bandData.keys || {});
        await this._hass.callService(DOMAIN, "reset_options", { keys });
        await this._fetchDebugPayload(true);
        this._tuningDraft = null;
        this._tuningBase = null;
        this._toast("Band zurückgesetzt");
      } else if (action === "diagnostics-show") {
        this._diagnosticsPackageFormat = "markdown";
        this._diagnosticsPackage = diagnosticPackage(this._hass, this, "markdown");
        this._scheduleRender();
        this._toast("Diagnosepaket angezeigt");
      } else if (action === "diagnostics-copy" || action === "diagnostics-copy-json") {
        const format = action === "diagnostics-copy-json" ? "json" : "markdown";
        const text = diagnosticPackage(this._hass, this, format);
        this._diagnosticsPackageFormat = format;
        this._diagnosticsPackage = text;
        if (navigator.clipboard?.writeText) {
          await navigator.clipboard.writeText(text);
          this._toast("Diagnosepaket kopiert");
        } else {
          this._toast("Clipboard nicht verfügbar, Paket wird angezeigt");
        }
        this._scheduleRender();
      } else if (action.startsWith("dry-run-")) {
        await this._hass.callService(DOMAIN, "dry_run", { zone: action.replace("dry-run-", "") });
        await this._fetchDebugPayload(true);
      } else if (action.startsWith("apply-")) {
        await this._hass.callService(DOMAIN, "apply_now", { zone: action.replace("apply-", "") });
        await this._fetchDebugPayload(true);
      }
      if (!action.startsWith("tuning-") && !action.startsWith("diagnostics-")) this._toast("Service ausgelöst");
    } catch (err) {
      this._tuningError = err.message || String(err);
      this._scheduleRender();
      this._toast(`Fehler: ${err.message || err}`);
    }
  }

  _toast(message) {
    const toast = document.createElement("div");
    toast.className = "toast";
    toast.textContent = message;
    this.shadowRoot.appendChild(toast);
    setTimeout(() => toast.remove(), 2400);
  }
}

if (!customElements.get("bcp-app")) {
  customElements.define("bcp-app", BcpApp);
}
