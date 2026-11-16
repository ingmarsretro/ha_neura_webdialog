"""Polling coordinator: scrape Neura, publish MQTT, expose the result."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DATA_POINTS, DOMAIN, LOGIN_KEY
from .mqtt_client import publish_messages
from .neura_client import NeuraAuthError, NeuraClient, NeuraConnectionError, NeuraError
from .scrape import build_mqtt_messages
from .settings import NeuraSettings

_LOGGER = logging.getLogger(__name__)


class NeuraDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetch schema.jsp on an interval and mirror the values to MQTT."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry = entry
        settings = NeuraSettings.from_entry(entry)
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=settings.scan_interval),
            config_entry=entry,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        settings = NeuraSettings.from_entry(self.entry)
        client = NeuraClient(settings.base_url, settings.username, settings.password)
        try:
            values = await client.async_read()
        except NeuraAuthError:
            _LOGGER.warning("Anmeldung an der Neura-Weboberfläche fehlgeschlagen")
            await self._async_publish(settings, build_mqtt_messages({}, login_ok=False))
            previous = dict(self.data or {})
            previous[LOGIN_KEY] = False
            return previous
        except NeuraConnectionError as err:
            raise UpdateFailed(str(err)) from err
        except NeuraError as err:
            raise UpdateFailed(str(err)) from err
        except Exception as err:
            _LOGGER.exception("Neura-Abfrage fehlgeschlagen")
            raise UpdateFailed("Neura-Abfrage fehlgeschlagen") from err

        messages = build_mqtt_messages(values, login_ok=True)
        _LOGGER.debug("MQTT-Nachrichten: %s", messages)
        await self._async_publish(settings, messages)

        merged: dict[str, Any] = {}
        if self.data:
            for point in DATA_POINTS:
                if point.key in self.data:
                    merged[point.key] = self.data[point.key]
        merged.update(values)
        merged[LOGIN_KEY] = True
        return merged

    async def _async_publish(self, settings: NeuraSettings, messages: list[tuple[str, str]]) -> None:
        if not settings.mqtt_enabled or not messages:
            return
        if not settings.mqtt_host:
            _LOGGER.error("MQTT ist aktiv, aber es ist kein Broker eingetragen")
            return
        try:
            await self.hass.async_add_executor_job(
                _publish,
                settings.mqtt_host,
                settings.mqtt_port,
                settings.mqtt_username,
                settings.mqtt_password,
                settings.mqtt_client_id,
                messages,
            )
        except Exception:
            _LOGGER.exception("MQTT-Veröffentlichung an %s fehlgeschlagen", settings.mqtt_host)


def _publish(
    host: str,
    port: int,
    username: str,
    password: str,
    client_id: str,
    messages: list[tuple[str, str]],
) -> None:
    publish_messages(
        host=host,
        port=port,
        username=username,
        password=password,
        client_id=client_id,
        messages=messages,
    )
