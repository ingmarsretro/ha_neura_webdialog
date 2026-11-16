"""The Neura Webdialog integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import NeuraDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]

type NeuraConfigEntry = ConfigEntry[NeuraDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: NeuraConfigEntry) -> bool:
    """Set up Neura Webdialog from a config entry."""

    coordinator = NeuraDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: NeuraConfigEntry) -> bool:
    """Unload platforms for a config entry."""

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
