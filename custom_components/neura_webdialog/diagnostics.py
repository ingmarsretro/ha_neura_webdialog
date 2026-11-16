"""Diagnostics without credentials."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from .const import CONF_MQTT_CLIENT_ID, CONF_MQTT_ENABLED, CONF_MQTT_HOST, CONF_MQTT_PORT, CONF_MQTT_USERNAME
from .settings import NeuraSettings, merged_raw


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry) -> dict[str, Any]:
    """Return scrape results and connection targets, never passwords."""

    raw = merged_raw(entry)
    settings = NeuraSettings.from_entry(entry)
    coordinator = getattr(entry, "runtime_data", None)
    values = dict(coordinator.data) if coordinator is not None and coordinator.data else {}
    return {
        "base_url": settings.base_url,
        "username": settings.username,
        "scan_interval": settings.scan_interval,
        "mqtt_enabled": raw.get(CONF_MQTT_ENABLED, settings.mqtt_enabled),
        "mqtt_host": raw.get(CONF_MQTT_HOST, settings.mqtt_host),
        "mqtt_port": raw.get(CONF_MQTT_PORT, settings.mqtt_port),
        "mqtt_username": raw.get(CONF_MQTT_USERNAME, settings.mqtt_username),
        "mqtt_client_id": raw.get(CONF_MQTT_CLIENT_ID, settings.mqtt_client_id),
        "last_update_success": None if coordinator is None else coordinator.last_update_success,
        "values": values,
    }
