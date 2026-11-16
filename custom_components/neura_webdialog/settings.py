"""Resolved settings for one config entry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)

from .const import (
    CONF_MQTT_CLIENT_ID,
    CONF_MQTT_ENABLED,
    CONF_MQTT_HOST,
    CONF_MQTT_PASSWORD,
    CONF_MQTT_PORT,
    CONF_MQTT_USERNAME,
    DEFAULT_HOST,
    DEFAULT_MQTT_CLIENT_ID,
    DEFAULT_MQTT_HOST,
    DEFAULT_MQTT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_USERNAME,
)
from .scrape import normalize_base_url, unique_host_id


def merged_raw(entry: ConfigEntry) -> dict[str, Any]:
    """Entry data with options applied on top."""

    return {**entry.data, **entry.options}


@dataclass(frozen=True, slots=True)
class NeuraSettings:
    """Connection, poll interval, and MQTT publisher settings."""

    base_url: str
    username: str
    password: str
    scan_interval: int
    mqtt_enabled: bool
    mqtt_host: str
    mqtt_port: int
    mqtt_username: str
    mqtt_password: str
    mqtt_client_id: str

    @property
    def host_id(self) -> str:
        return unique_host_id(self.base_url)

    @classmethod
    def from_entry(cls, entry: ConfigEntry) -> NeuraSettings:
        return cls.from_mapping(merged_raw(entry))

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> NeuraSettings:
        scan_interval = int(raw.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
        scan_interval = min(3600, max(10, scan_interval))
        client_id = str(raw.get(CONF_MQTT_CLIENT_ID) or DEFAULT_MQTT_CLIENT_ID).strip()
        return cls(
            base_url=normalize_base_url(str(raw.get(CONF_HOST, DEFAULT_HOST))),
            username=str(raw.get(CONF_USERNAME, DEFAULT_USERNAME)),
            password=str(raw.get(CONF_PASSWORD, "")),
            scan_interval=scan_interval,
            mqtt_enabled=bool(raw.get(CONF_MQTT_ENABLED, True)),
            mqtt_host=str(raw.get(CONF_MQTT_HOST, DEFAULT_MQTT_HOST) or "").strip(),
            mqtt_port=int(raw.get(CONF_MQTT_PORT, DEFAULT_MQTT_PORT)),
            mqtt_username=str(raw.get(CONF_MQTT_USERNAME) or "").strip(),
            mqtt_password=str(raw.get(CONF_MQTT_PASSWORD) or ""),
            mqtt_client_id=client_id or DEFAULT_MQTT_CLIENT_ID,
        )
