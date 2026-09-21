"""Benni Climate Policy integration."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant, ServiceCall

from .const import (
    CONF_APPLY_ACTIVE,
    CORE_OPENINGS_MASTER_ENTITY,
    DATA_COORDINATOR,
    DOMAIN,
    SERVICE_APPLY_NOW,
    SERVICE_APPLY_ZONE,
    SERVICE_DRY_RUN,
    SERVICE_RESET_OPTIONS,
    SERVICE_RECALCULATE,
    SERVICE_SET_APPLY_ACTIVE,
    SERVICE_UPDATE_OPTIONS,
)

PLATFORM_NAMES = ["sensor", "binary_sensor", "switch", "button"]


def _reload_relevant_options(options: dict[str, Any]) -> dict[str, Any]:
    relevant = dict(options)
    relevant.pop(CONF_APPLY_ACTIVE, None)
    return relevant


class _ConfigEntryOptionsListener:
    def __init__(self, options: dict[str, Any]) -> None:
        self._reload_options = _reload_relevant_options(options)

    async def __call__(self, hass: "HomeAssistant", entry: "ConfigEntry") -> None:
        reload_options = _reload_relevant_options(entry.options)
        if reload_options == self._reload_options:
            return
        self._reload_options = reload_options
        await hass.config_entries.async_reload(entry.entry_id)

LEGACY_ENTITY_REPLACEMENTS: dict[str, str] = {
    "sensor.context_activity_state_combined": "sensor.benni_combined_context_activity_state",
    "sensor.context_bio_state_combined": "sensor.benni_combined_context_bio_state",
    "sensor.context_day_context_combined": "sensor.benni_combined_context_day_context",
    "sensor.context_day_state_combined": "sensor.benni_combined_context_day_state",
    "sensor.context_presence_band_combined": "sensor.benni_combined_context_presence_band",
    "sensor.context_presence_household_combined": "sensor.benni_combined_context_presence_household",
    "sensor.context_presence_personal_combined": "sensor.benni_combined_context_presence_personal",
    "binary_sensor.context_presence_preheat_active_combined": "sensor.benni_combined_context_presence_preheat_active",
    "sensor.context_presence_transition_combined": "sensor.benni_combined_context_presence_transition",
    "sensor.garden_temperature_atomic": "sensor.benni_device_garden_climate",
    "sensor.weather_humidity_atomic": "sensor.benni_device_weather_humidity",
    "sensor.weather_wind_speed_atomic": "sensor.benni_device_weather_wind_speed",
    "sensor.weather_condition_atomic": "sensor.benni_device_weather_condition",
    "sensor.garden_illuminance_atomic": "sensor.benni_device_garden_lux",
    "sensor.living_temperature_atomic": "sensor.benni_device_living_climate",
    "sensor.living_humidity_atomic": "sensor.benni_device_living_climate",
    "sensor.kitchen_temperature_atomic": "sensor.benni_device_kitchen_climate",
    "sensor.kitchen_humidity_atomic": "sensor.benni_device_kitchen_climate",
    "sensor.bath_temperature_atomic": "sensor.benni_device_bath_climate",
    "sensor.bath_humidity_atomic": "sensor.benni_device_bath_climate",
    "binary_sensor.living_window_left_open_atomic": CORE_OPENINGS_MASTER_ENTITY,
    "binary_sensor.living_window_left_tilt_atomic": CORE_OPENINGS_MASTER_ENTITY,
    "binary_sensor.living_window_right_open_atomic": CORE_OPENINGS_MASTER_ENTITY,
    "binary_sensor.living_window_right_tilt_atomic": CORE_OPENINGS_MASTER_ENTITY,
    "binary_sensor.kitchen_patio_door_open_atomic": CORE_OPENINGS_MASTER_ENTITY,
    "binary_sensor.kitchen_patio_door_tilt_atomic": CORE_OPENINGS_MASTER_ENTITY,
    "sensor.benni_device_living_window_left": CORE_OPENINGS_MASTER_ENTITY,
    "sensor.benni_device_living_window_right": CORE_OPENINGS_MASTER_ENTITY,
    "sensor.benni_device_kitchen_patio_door": CORE_OPENINGS_MASTER_ENTITY,
    "binary_sensor.bath_toilet_active_combined": "sensor.benni_combined_bath_toilet_active",
    "binary_sensor.bath_shower_active_combined": "sensor.benni_combined_bath_shower_active",
}


def _replace_legacy_entities(value: Any) -> tuple[Any, bool]:
    if isinstance(value, str):
        replacement = LEGACY_ENTITY_REPLACEMENTS.get(value)
        return (replacement, True) if replacement else (value, False)
    if isinstance(value, dict):
        changed = False
        replaced: dict[Any, Any] = {}
        for key, item in value.items():
            new_item, item_changed = _replace_legacy_entities(item)
            replaced[key] = new_item
            changed = changed or item_changed
        return replaced, changed
    if isinstance(value, list):
        changed = False
        replaced_items: list[Any] = []
        for item in value:
            new_item, item_changed = _replace_legacy_entities(item)
            replaced_items.append(new_item)
            changed = changed or item_changed
        return replaced_items, changed
    return value, False


def _migrate_legacy_source_entities(hass: "HomeAssistant", entry: "ConfigEntry") -> None:
    data, data_changed = _replace_legacy_entities(dict(entry.data))
    options, options_changed = _replace_legacy_entities(dict(entry.options))
    if data_changed or options_changed:
        hass.config_entries.async_update_entry(entry, data=data, options=options)


async def async_setup_entry(hass: "HomeAssistant", entry: "ConfigEntry") -> bool:
    from homeassistant.const import Platform

    from .coordinator import ClimatePolicyCoordinator

    _migrate_legacy_source_entities(hass, entry)
    platforms = [Platform(name) for name in PLATFORM_NAMES]
    coord = ClimatePolicyCoordinator(hass, entry)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {DATA_COORDINATOR: coord}

    coord.async_start()
    await coord.async_evaluate(auto_apply=False, reason="setup_entry")
    from .view import async_setup_view

    await async_setup_view(hass)
    await hass.config_entries.async_forward_entry_setups(entry, platforms)
    _register_services(hass)
    entry.async_on_unload(entry.add_update_listener(_ConfigEntryOptionsListener(entry.options)))
    return True


async def async_unload_entry(hass: "HomeAssistant", entry: "ConfigEntry") -> bool:
    from homeassistant.const import Platform

    platforms = [Platform(name) for name in PLATFORM_NAMES]
    unloaded = await hass.config_entries.async_unload_platforms(entry, platforms)
    if unloaded:
        bucket = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
        if bucket:
            bucket[DATA_COORDINATOR].async_stop()
        if not hass.data.get(DOMAIN):
            for service in (
                SERVICE_APPLY_NOW,
                SERVICE_APPLY_ZONE,
                SERVICE_SET_APPLY_ACTIVE,
                SERVICE_RECALCULATE,
                SERVICE_DRY_RUN,
                SERVICE_UPDATE_OPTIONS,
                SERVICE_RESET_OPTIONS,
            ):
                hass.services.async_remove(DOMAIN, service)
            from .view import async_remove_view

            async_remove_view(hass)
    return unloaded


def _coordinators(hass: "HomeAssistant"):
    return [
        bucket[DATA_COORDINATOR]
        for bucket in hass.data.get(DOMAIN, {}).values()
        if isinstance(bucket, dict) and DATA_COORDINATOR in bucket
    ]


def _register_services(hass: "HomeAssistant") -> None:
    if hass.services.has_service(DOMAIN, SERVICE_APPLY_NOW):
        return

    async def _apply_now(call: "ServiceCall") -> None:
        zone = call.data.get("zone")
        for coord in _coordinators(hass):
            await coord.async_apply(zone=zone, manual=True, dry_run=False)

    async def _apply_zone(call: "ServiceCall") -> None:
        zone = call.data.get("zone")
        for coord in _coordinators(hass):
            await coord.async_apply(zone=zone, manual=True, dry_run=False)

    async def _set_apply_active(call: "ServiceCall") -> None:
        active = bool(call.data.get("active", False))
        for coord in _coordinators(hass):
            await coord.async_set_apply_active(active)

    async def _recalculate(_call: "ServiceCall") -> None:
        for coord in _coordinators(hass):
            await coord.async_evaluate(auto_apply=False, reason="service_recalculate")

    async def _dry_run(call: "ServiceCall") -> None:
        zone = call.data.get("zone")
        for coord in _coordinators(hass):
            await coord.async_apply(zone=zone, manual=True, dry_run=True)

    async def _update_options(call: "ServiceCall") -> None:
        from homeassistant.exceptions import HomeAssistantError

        updates = dict(call.data.get("options") or {})
        reset_keys = list(call.data.get("reset_keys") or ())
        try:
            for coord in _coordinators(hass):
                await coord.async_update_options(updates, reset_keys=reset_keys)
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err

    async def _reset_options(call: "ServiceCall") -> None:
        from homeassistant.exceptions import HomeAssistantError

        keys = list(call.data.get("keys") or ())
        try:
            for coord in _coordinators(hass):
                await coord.async_update_options({}, reset_keys=keys)
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err

    hass.services.async_register(DOMAIN, SERVICE_APPLY_NOW, _apply_now)
    hass.services.async_register(DOMAIN, SERVICE_APPLY_ZONE, _apply_zone)
    hass.services.async_register(DOMAIN, SERVICE_SET_APPLY_ACTIVE, _set_apply_active)
    hass.services.async_register(DOMAIN, SERVICE_RECALCULATE, _recalculate)
    hass.services.async_register(DOMAIN, SERVICE_DRY_RUN, _dry_run)
    hass.services.async_register(DOMAIN, SERVICE_UPDATE_OPTIONS, _update_options)
    hass.services.async_register(DOMAIN, SERVICE_RESET_OPTIONS, _reset_options)
