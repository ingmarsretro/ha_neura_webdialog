"""Shared device info."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN, PATH_LOGIN
from .settings import NeuraSettings


def neura_device_info(entry: ConfigEntry) -> DeviceInfo:
    """Device page for the heat pump web interface."""

    settings = NeuraSettings.from_entry(entry)
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name="Neura Webdialog",
        manufacturer="Neura",
        model="Webdialog",
        configuration_url=f"{settings.base_url}{PATH_LOGIN}",
    )
