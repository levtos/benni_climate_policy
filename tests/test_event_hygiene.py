from __future__ import annotations

from pathlib import Path


ENTITY_SOURCE = Path("custom_components/benni_climate_policy/entity.py").read_text(encoding="utf-8")
SENSOR_SOURCE = Path("custom_components/benni_climate_policy/sensor.py").read_text(encoding="utf-8")
COORDINATOR_SOURCE = Path("custom_components/benni_climate_policy/coordinator.py").read_text(encoding="utf-8")
FRONTEND_SOURCE = Path("custom_components/benni_climate_policy/frontend/app/main.js").read_text(encoding="utf-8")

def _function_source(source: str, function_name: str) -> str:
    marker = f"def {function_name}"
    start = source.index(marker)
    next_def = source.find("\ndef ", start + len(marker))
    next_class = source.find("\nclass ", start + len(marker))
    candidates = [idx for idx in (next_def, next_class) if idx != -1]
    end = min(candidates) if candidates else len(source)
    return source[start:end]


def _method_source(source: str, method_name: str) -> str:
    marker = f"    async def {method_name}"
    start = source.index(marker)
    next_method = source.find("\n    def ", start + len(marker))
    next_async_method = source.find("\n    async def ", start + len(marker))
    candidates = [idx for idx in (next_method, next_async_method) if idx != -1]
    end = min(candidates) if candidates else len(source)
    return source[start:end]


def test_entity_update_handler_deduplicates_published_payloads():
    assert "_last_published_payload" in ENTITY_SOURCE
    assert "payload == self._last_published_payload" in ENTITY_SOURCE
    assert "return" in _function_source(ENTITY_SOURCE, "_handle_update")
    assert "async_write_ha_state()" in _function_source(ENTITY_SOURCE, "_handle_update")
    assert "json.dumps(payload, sort_keys=True" in ENTITY_SOURCE
    assert "record_entity_publish(changed=False)" in ENTITY_SOURCE
    assert "record_entity_publish(changed=True)" in ENTITY_SOURCE


def test_normal_plan_sensor_attributes_do_not_publish_last_calculated():
    zone_attrs = _function_source(SENSOR_SOURCE, "_compact_zone_plan")
    fan_attrs = _function_source(SENSOR_SOURCE, "_compact_fan_plan")

    assert "last_calculated" not in zone_attrs
    assert "last_calculated" not in fan_attrs


def test_coordinator_uses_15_minute_interval_not_short_polling():
    assert "async_track_time_interval" in COORDINATOR_SOURCE
    assert "timedelta(minutes=15)" in COORDINATOR_SOURCE
    assert "timedelta(seconds=1)" not in COORDINATOR_SOURCE
    assert "timedelta(seconds=3)" not in COORDINATOR_SOURCE


def test_coordinator_debounces_state_change_recalculations():
    assert "EVALUATE_DEBOUNCE_SECONDS = 2" in COORDINATOR_SOURCE
    assert "async_call_later" in COORDINATOR_SOURCE
    assert "def _schedule_evaluate" in COORDINATOR_SOURCE
    assert "state_change:" in COORDINATOR_SOURCE


def test_started_one_time_listener_is_not_unsubscribed_twice():
    assert "self._ha_started_unsub = self.hass.bus.async_listen_once" in COORDINATOR_SOURCE
    assert "self._unsub.append(self.hass.bus.async_listen_once" not in COORDINATOR_SOURCE
    assert "self._ha_started_unsub = None" in _function_source(COORDINATOR_SOURCE, "_on_started")


def test_coordinator_does_not_watch_self_generated_temperature_inputs():
    assert "SELF_GENERATED_INPUT_ENTITY_IDS" in COORDINATOR_SOURCE
    assert "def _is_watchable_entity_id" in COORDINATOR_SOURCE
    assert "value not in SELF_GENERATED_INPUT_ENTITY_IDS" in COORDINATOR_SOURCE
    assert "key != CONF_OUTDOOR_FEELS_LIKE and _is_watchable_entity_id(value)" in COORDINATOR_SOURCE


def test_room_humidity_inputs_read_core_device_humidity_attribute():
    assert 'if key.endswith("_humidity")' in COORDINATOR_SOURCE
    assert 'return "humidity"' in COORDINATOR_SOURCE
    assert "state.attributes.get(attr)" in COORDINATOR_SOURCE
    assert '"attribute": attr if state is not None and attr in state.attributes else None' in COORDINATOR_SOURCE


def test_window_inputs_read_openings_master_attributes():
    assert "OPENING_ATTRIBUTE_BY_KEY" in COORDINATOR_SOURCE
    assert '"living_window_left"' in COORDINATOR_SOURCE
    assert '"living_window_right"' in COORDINATOR_SOURCE
    assert '"kitchen_patio_door"' in COORDINATOR_SOURCE
    assert "window_state_from_master_value" in COORDINATOR_SOURCE
    assert "CORE_OPENINGS_MASTER_ENTITY" in COORDINATOR_SOURCE


def test_window_blocking_does_not_depend_on_shared_master_timestamps():
    window_source = _function_source(COORDINATOR_SOURCE, "_window_state")

    assert "last_changed" not in window_source
    assert "sustained_open_delay" not in window_source
    assert "window_state_from_master_value" in window_source


def test_debug_payload_exposes_compact_performance_diagnostics():
    assert '"performance"' in COORDINATOR_SOURCE
    assert '"last_recalculate_at"' in COORDINATOR_SOURCE
    assert '"recalculate_count"' in COORDINATOR_SOURCE
    assert '"weather_forecast_cache_hit"' in COORDINATOR_SOURCE
    assert '"entity_publish_skipped_count"' in COORDINATOR_SOURCE


def test_dry_run_does_not_force_recalculate_loop():
    apply_source = _method_source(COORDINATOR_SOURCE, "async_apply")

    assert "dry_run: bool" in apply_source
    assert "await self.async_evaluate(auto_apply=False, reason=\"apply_refresh_before_execute\")" in apply_source
    assert apply_source.count("await self.async_evaluate(auto_apply=False") == 1
    assert apply_source.count("self._notify()") <= 2
    assert "return self.last_apply_result" in apply_source


def test_weather_resolver_sensor_tests_guard_against_forecast_lists_in_attributes():
    forecast_sensor = SENSOR_SOURCE[SENSOR_SOURCE.index("class ForecastTemperature3hSensor"):SENSOR_SOURCE.index("class OutdoorFeelsLikeTemperatureSensor")]
    feels_like_sensor = SENSOR_SOURCE[SENSOR_SOURCE.index("class OutdoorFeelsLikeTemperatureSensor"):SENSOR_SOURCE.index("class ApplyStatusSensor")]

    assert '"forecast"' not in forecast_sensor
    assert '"forecast"' not in feels_like_sensor
    assert "forecast_time" in forecast_sensor


def test_effective_temperature_sensor_does_not_publish_high_frequency_raw_diagnostics():
    effective_sensor = SENSOR_SOURCE[
        SENSOR_SOURCE.index("class EffectiveOutdoorTemperatureSensor"):
        SENSOR_SOURCE.index("class ForecastTemperature3hSensor")
    ]

    assert '"outdoor_lux"' not in effective_sensor
    assert '"sun_elevation"' not in effective_sensor
    assert '"forecast_resolution":' not in effective_sensor
    assert '"feels_like_resolution":' not in effective_sensor
    assert '"debug_payload_available"' in effective_sensor


def test_forecast_sensor_target_time_uses_stable_forecast_datetime():
    forecast_sensor = SENSOR_SOURCE[
        SENSOR_SOURCE.index("class ForecastTemperature3hSensor"):
        SENSOR_SOURCE.index("class OutdoorFeelsLikeTemperatureSensor")
    ]

    assert '"target_time": diag.forecast_datetime' in forecast_sensor
    assert '"target_time": diag.target_time' not in forecast_sensor


def test_frontend_does_not_poll_debug_endpoint_for_every_hass_update():
    assert "const DEBUG_REFRESH_MS = 60000" in FRONTEND_SOURCE
    assert "const DEBUG_VIEWS = new Set" in FRONTEND_SOURCE
    assert "if (!force && !this._viewNeedsDebug()) return;" in FRONTEND_SOURCE
    assert "now - this._debugLastFetch < DEBUG_REFRESH_MS" in FRONTEND_SOURCE
