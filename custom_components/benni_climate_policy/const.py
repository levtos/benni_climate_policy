"""Constants for Benni Climate Policy."""
from __future__ import annotations

DOMAIN = "benni_climate_policy"
INTEGRATION_VERSION = "0.1.12"
DATA_COORDINATOR = "coordinator"

CONF_APPLY_ACTIVE = "apply_active"
CONF_APPLY_COOLDOWN_SECONDS = "apply_cooldown_seconds"
CONF_STARTUP_BLOCK_SECONDS = "startup_block_seconds"
CONF_COOLDOWN_SECONDS = "cooldown_seconds"

CONF_CONTEXT_ACTIVITY = "context_activity_state"
CONF_CONTEXT_BIO = "context_bio_state"
CONF_CONTEXT_DAY_CONTEXT = "context_day_context"
CONF_CONTEXT_DAY_STATE = "context_day_state"
CONF_CONTEXT_PRESENCE_BAND = "context_presence_band"
CONF_CONTEXT_PRESENCE_HOUSEHOLD = "context_presence_household"
CONF_CONTEXT_PRESENCE_PERSONAL = "context_presence_personal"
CONF_CONTEXT_PREHEAT_ACTIVE = "context_presence_preheat_active"
CONF_CONTEXT_TRANSITION = "context_presence_transition"
CONF_CONTEXT_WORKDAY = "context_workday_state"
CONF_CONTEXT_WAKEUP = "context_planned_wakeup_time"

CONF_OUTDOOR_TEMPERATURE = "outdoor_temperature"
CONF_OUTDOOR_FEELS_LIKE = "outdoor_feels_like"
CONF_OUTDOOR_HUMIDITY = "outdoor_humidity"
CONF_OUTDOOR_WIND_SPEED = "outdoor_wind_speed"
CONF_FORECAST_TEMPERATURE = "forecast_temperature_3h"
CONF_WEATHER_ENTITY = "weather_entity"
CONF_WEATHER_CONDITION = "weather_condition"
CONF_OUTDOOR_LUX = "outdoor_lux"
CONF_SUN = "sun_entity"
CONF_SYSTEM_READY = "system_ready"

ZONE_LIVING = "living_room"
ZONE_KITCHEN = "kitchen"
ZONE_BATHROOM = "bathroom"
ZONES = (ZONE_LIVING, ZONE_KITCHEN, ZONE_BATHROOM)
HEATING_ZONES = (ZONE_LIVING, ZONE_KITCHEN)

CONF_ZONE_TEMPERATURE = "{zone}_temperature"
CONF_ZONE_HUMIDITY = "{zone}_humidity"
CONF_ZONE_THERMOSTAT = "{zone}_thermostat"

CONF_LIVING_WINDOW_LEFT_OPEN = "living_window_left_open"
CONF_LIVING_WINDOW_LEFT_TILT = "living_window_left_tilt"
CONF_LIVING_WINDOW_RIGHT_OPEN = "living_window_right_open"
CONF_LIVING_WINDOW_RIGHT_TILT = "living_window_right_tilt"
CONF_KITCHEN_PATIO_OPEN = "kitchen_patio_door_open"
CONF_KITCHEN_PATIO_TILT = "kitchen_patio_door_tilt"
CORE_OPENINGS_MASTER_ENTITY = "sensor.benni_combined_openings"
CONF_BATH_FAN = "bath_fan"
CONF_BATH_DIFFUSER = "bath_diffuser"
CONF_BATH_TOILET_ACTIVITY = "bath_toilet_activity"
CONF_BATH_SHOWER_ACTIVITY = "bath_shower_activity"

SERVICE_APPLY_NOW = "apply_now"
SERVICE_APPLY_ZONE = "apply_zone"
SERVICE_SET_APPLY_ACTIVE = "set_apply_active"
SERVICE_RECALCULATE = "recalculate"
SERVICE_DRY_RUN = "dry_run"
SERVICE_UPDATE_OPTIONS = "update_options"
SERVICE_RESET_OPTIONS = "reset_options"

DEFAULT_STARTUP_BLOCK_SECONDS = 90
DEFAULT_COOLDOWN_SECONDS = 600
DEFAULT_APPLY_ACTIVE = False

FRONTEND_DIR_URL = f"/{DOMAIN}_frontend"
FRONTEND_ENTRY = f"{FRONTEND_DIR_URL}/main.js"
PANEL_URL_PATH = "benni-climate-policy"
PANEL_ELEMENT = "bcp-app"
PANEL_TITLE = "Climate Policy"
PANEL_ICON = "mdi:thermostat"

SELF_GENERATED_INPUT_ENTITY_IDS = frozenset({
    "sensor.climate_effective_outdoor_temperature",
    "sensor.climate_forecast_temperature_3h",
    "sensor.climate_outdoor_feels_like_temperature",
})

PRESET = {
    CONF_CONTEXT_ACTIVITY: "sensor.benni_combined_context_activity_state",
    CONF_CONTEXT_BIO: "sensor.benni_combined_context_bio_state",
    CONF_CONTEXT_DAY_CONTEXT: "sensor.benni_combined_context_day_context",
    CONF_CONTEXT_DAY_STATE: "sensor.benni_combined_context_day_state",
    CONF_CONTEXT_PRESENCE_BAND: "sensor.benni_combined_context_presence_band",
    CONF_CONTEXT_PRESENCE_HOUSEHOLD: "sensor.benni_combined_context_presence_household",
    CONF_CONTEXT_PRESENCE_PERSONAL: "sensor.benni_combined_context_presence_personal",
    CONF_CONTEXT_PREHEAT_ACTIVE: "sensor.benni_combined_context_presence_preheat_active",
    CONF_CONTEXT_TRANSITION: "sensor.benni_combined_context_presence_transition",
    CONF_CONTEXT_WORKDAY: "sensor.benni_combined_context_day_context",
    CONF_OUTDOOR_TEMPERATURE: "sensor.benni_device_garden_climate",
    CONF_OUTDOOR_HUMIDITY: "sensor.benni_device_weather_humidity",
    CONF_OUTDOOR_WIND_SPEED: "sensor.benni_device_weather_wind_speed",
    CONF_WEATHER_CONDITION: "sensor.benni_device_weather_condition",
    CONF_WEATHER_ENTITY: "weather.dwd_home",
    CONF_OUTDOOR_LUX: "sensor.benni_device_garden_lux",
    CONF_SUN: "sun.sun",
    CONF_SYSTEM_READY: "binary_sensor.system_climate_ready",
    CONF_ZONE_TEMPERATURE.format(zone=ZONE_LIVING): "sensor.benni_device_living_climate",
    # Core environment sensors expose humidity as an attribute. The coordinator
    # reads that attribute for *_humidity keys and falls back to state otherwise.
    CONF_ZONE_HUMIDITY.format(zone=ZONE_LIVING): "sensor.benni_device_living_climate",
    CONF_ZONE_TEMPERATURE.format(zone=ZONE_KITCHEN): "sensor.benni_device_kitchen_climate",
    CONF_ZONE_HUMIDITY.format(zone=ZONE_KITCHEN): "sensor.benni_device_kitchen_climate",
    CONF_ZONE_TEMPERATURE.format(zone=ZONE_BATHROOM): "sensor.benni_device_bath_climate",
    CONF_ZONE_HUMIDITY.format(zone=ZONE_BATHROOM): "sensor.benni_device_bath_climate",
    CONF_LIVING_WINDOW_LEFT_OPEN: CORE_OPENINGS_MASTER_ENTITY,
    CONF_LIVING_WINDOW_LEFT_TILT: CORE_OPENINGS_MASTER_ENTITY,
    CONF_LIVING_WINDOW_RIGHT_OPEN: CORE_OPENINGS_MASTER_ENTITY,
    CONF_LIVING_WINDOW_RIGHT_TILT: CORE_OPENINGS_MASTER_ENTITY,
    CONF_KITCHEN_PATIO_OPEN: CORE_OPENINGS_MASTER_ENTITY,
    CONF_KITCHEN_PATIO_TILT: CORE_OPENINGS_MASTER_ENTITY,
    CONF_BATH_FAN: "switch.bath_fan",
    CONF_BATH_DIFFUSER: "switch.bath_diffuser_plug",
    CONF_BATH_TOILET_ACTIVITY: "sensor.benni_combined_bath_toilet_active",
    CONF_BATH_SHOWER_ACTIVITY: "sensor.benni_combined_bath_shower_active",
}
