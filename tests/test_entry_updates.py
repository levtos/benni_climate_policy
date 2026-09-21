from __future__ import annotations

import asyncio
from types import SimpleNamespace

from custom_components.benni_climate_policy import _ConfigEntryOptionsListener


class _ConfigEntries:
    def __init__(self) -> None:
        self.reloads: list[str] = []

    async def async_reload(self, entry_id: str) -> None:
        self.reloads.append(entry_id)


def test_apply_toggle_does_not_reload_or_replace_runtime_state():
    config_entries = _ConfigEntries()
    runtime_state = {"hysteresis": object(), "last_apply": object()}
    hass = SimpleNamespace(config_entries=config_entries, data={"runtime": runtime_state})
    entry = SimpleNamespace(entry_id="test-entry", options={"apply_active": False, "cooldown_seconds": 600})
    listener = _ConfigEntryOptionsListener(entry.options)

    for value in (True, False):
        entry.options = {**entry.options, "apply_active": value}
        asyncio.run(listener(hass, entry))

    assert config_entries.reloads == []
    assert hass.data["runtime"] is runtime_state


def test_non_apply_option_change_still_reloads_entry():
    config_entries = _ConfigEntries()
    hass = SimpleNamespace(config_entries=config_entries)
    entry = SimpleNamespace(entry_id="test-entry", options={"apply_active": False, "cooldown_seconds": 600})
    listener = _ConfigEntryOptionsListener(entry.options)

    entry.options = {**entry.options, "cooldown_seconds": 900}
    asyncio.run(listener(hass, entry))

    assert config_entries.reloads == ["test-entry"]
