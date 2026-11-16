"""Config flow for Neura Webdialog."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

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
    DOMAIN,
)
from .mqtt_client import check_connection
from .neura_client import NeuraAuthError, NeuraClient, NeuraConnectionError, NeuraError
from .scrape import normalize_base_url, unique_host_id
from .settings import merged_raw

_LOGGER = logging.getLogger(__name__)

_TEXT = selector.TextSelector()
_PASSWORD = selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD))
_SCAN = selector.NumberSelector(
    selector.NumberSelectorConfig(
        min=10,
        max=3600,
        step=1,
        mode=selector.NumberSelectorMode.BOX,
        unit_of_measurement="s",
    )
)
_PORT = selector.NumberSelector(
    selector.NumberSelectorConfig(min=1, max=65535, step=1, mode=selector.NumberSelectorMode.BOX)
)


def _password_marker(defaults: dict[str, Any], key: str, *, required: bool) -> Any:
    typed = defaults.get(key) or ""
    if typed:
        marker = vol.Required if required else vol.Optional
        return marker(key, default=typed)
    if required:
        return vol.Required(key)
    return vol.Optional(key)


def _connection_fields(defaults: dict[str, Any], *, require_password: bool) -> dict[Any, Any]:
    return {
        vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, DEFAULT_HOST)): _TEXT,
        vol.Required(CONF_USERNAME, default=defaults.get(CONF_USERNAME, DEFAULT_USERNAME)): _TEXT,
        _password_marker(defaults, CONF_PASSWORD, required=require_password): _PASSWORD,
        vol.Required(
            CONF_SCAN_INTERVAL,
            default=int(defaults.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)),
        ): _SCAN,
    }


def _mqtt_fields(defaults: dict[str, Any]) -> dict[Any, Any]:
    return {
        vol.Required(
            CONF_MQTT_ENABLED,
            default=bool(defaults.get(CONF_MQTT_ENABLED, True)),
        ): selector.BooleanSelector(),
        vol.Optional(CONF_MQTT_HOST, default=defaults.get(CONF_MQTT_HOST, DEFAULT_MQTT_HOST)): _TEXT,
        vol.Required(CONF_MQTT_PORT, default=int(defaults.get(CONF_MQTT_PORT, DEFAULT_MQTT_PORT))): _PORT,
        vol.Optional(CONF_MQTT_USERNAME, default=defaults.get(CONF_MQTT_USERNAME, "")): _TEXT,
        _password_marker(defaults, CONF_MQTT_PASSWORD, required=False): _PASSWORD,
        vol.Optional(
            CONF_MQTT_CLIENT_ID,
            default=defaults.get(CONF_MQTT_CLIENT_ID, DEFAULT_MQTT_CLIENT_ID),
        ): _TEXT,
    }


def _connection_schema(defaults: dict[str, Any], *, require_password: bool) -> vol.Schema:
    return vol.Schema(_connection_fields(defaults, require_password=require_password))


def _mqtt_schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(_mqtt_fields(defaults))


def _full_schema(defaults: dict[str, Any]) -> vol.Schema:
    fields = _connection_fields(defaults, require_password=False)
    fields.update(_mqtt_fields(defaults))
    return vol.Schema(fields)


def _clean_connection(user_input: dict[str, Any], previous: dict[str, Any] | None, *, require_password: bool) -> dict[str, Any]:
    previous = previous or {}
    password = str(user_input.get(CONF_PASSWORD) or "")
    if not password:
        password = "" if require_password else str(previous.get(CONF_PASSWORD) or "")
    return {
        CONF_HOST: str(user_input[CONF_HOST]).strip(),
        CONF_USERNAME: str(user_input[CONF_USERNAME]).strip(),
        CONF_PASSWORD: password,
        CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
    }


def _clean_mqtt(user_input: dict[str, Any], previous: dict[str, Any] | None) -> dict[str, Any]:
    previous = previous or {}
    username = str(user_input.get(CONF_MQTT_USERNAME) or "").strip()
    password = str(user_input.get(CONF_MQTT_PASSWORD) or "")
    if not username:
        password = ""
    elif not password:
        password = str(previous.get(CONF_MQTT_PASSWORD) or "")
    client_id = str(user_input.get(CONF_MQTT_CLIENT_ID) or "").strip() or DEFAULT_MQTT_CLIENT_ID
    return {
        CONF_MQTT_ENABLED: bool(user_input.get(CONF_MQTT_ENABLED, True)),
        CONF_MQTT_HOST: str(user_input.get(CONF_MQTT_HOST) or "").strip(),
        CONF_MQTT_PORT: int(user_input.get(CONF_MQTT_PORT) or DEFAULT_MQTT_PORT),
        CONF_MQTT_USERNAME: username,
        CONF_MQTT_PASSWORD: password,
        CONF_MQTT_CLIENT_ID: client_id,
    }


def _local_errors(connection: dict[str, Any], mqtt: dict[str, Any] | None = None) -> dict[str, str]:
    errors: dict[str, str] = {}
    try:
        normalize_base_url(connection[CONF_HOST])
    except ValueError:
        errors[CONF_HOST] = "invalid_host"
    scan = connection[CONF_SCAN_INTERVAL]
    if not 10 <= scan <= 3600:
        errors[CONF_SCAN_INTERVAL] = "invalid_scan_interval"
    if mqtt is not None:
        port = mqtt[CONF_MQTT_PORT]
        if not 1 <= port <= 65535:
            errors[CONF_MQTT_PORT] = "invalid_port"
        if mqtt[CONF_MQTT_ENABLED] and not mqtt[CONF_MQTT_HOST]:
            errors[CONF_MQTT_HOST] = "invalid_host"
    return errors


async def _test_neura(host: str, username: str, password: str) -> str | None:
    if not password:
        return "invalid_auth"
    client = NeuraClient(host, username, password)
    try:
        await client.async_read()
    except NeuraAuthError:
        return "invalid_auth"
    except NeuraConnectionError:
        return "cannot_connect"
    except NeuraError:
        _LOGGER.exception("Neura page could not be parsed during setup")
        return "unknown"
    except Exception:
        _LOGGER.exception("Unexpected Neura setup error")
        return "unknown"
    return None


async def _test_mqtt(hass, mqtt: dict[str, Any]) -> str | None:
    if not mqtt[CONF_MQTT_ENABLED]:
        return None
    try:
        await hass.async_add_executor_job(
            _check_mqtt,
            mqtt[CONF_MQTT_HOST],
            mqtt[CONF_MQTT_PORT],
            mqtt[CONF_MQTT_USERNAME],
            mqtt[CONF_MQTT_PASSWORD],
            mqtt[CONF_MQTT_CLIENT_ID],
        )
    except Exception:
        _LOGGER.exception("MQTT connection test failed")
        return "mqtt_cannot_connect"
    return None


def _check_mqtt(host: str, port: int, username: str, password: str, client_id: str) -> None:
    check_connection(host=host, port=port, username=username, password=password, client_id=client_id)


def _host_taken(hass, host: str, current_entry_id: str | None = None) -> bool:
    target = unique_host_id(host)
    return any(
        item.unique_id == target and item.entry_id != current_entry_id
        for item in hass.config_entries.async_entries(DOMAIN)
    )


class NeuraConfigFlow(ConfigFlow, domain=DOMAIN):
    """Set up a Neura heat pump web interface."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        self._connection: dict[str, Any] = {}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> NeuraOptionsFlow:
        return NeuraOptionsFlow()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        defaults = dict(user_input or {})
        if user_input is not None:
            connection = _clean_connection(user_input, None, require_password=True)
            errors.update(_local_errors(connection))
            if not errors:
                error = await _test_neura(connection[CONF_HOST], connection[CONF_USERNAME], connection[CONF_PASSWORD])
                if error:
                    errors["base"] = error
                elif _host_taken(self.hass, connection[CONF_HOST]):
                    errors["base"] = "already_configured"
                else:
                    self._connection = connection
                    return await self.async_step_mqtt()
            defaults = connection
        return self.async_show_form(step_id="user", data_schema=_connection_schema(defaults, require_password=True), errors=errors)

    async def async_step_mqtt(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        defaults = dict(user_input or {})
        if user_input is not None:
            mqtt = _clean_mqtt(user_input, None)
            errors.update(_local_errors(self._connection, mqtt))
            if not errors:
                error = await _test_mqtt(self.hass, mqtt)
                if error:
                    errors["base"] = error
                else:
                    data = {**self._connection, **mqtt}
                    await self.async_set_unique_id(unique_host_id(data[CONF_HOST]))
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(title=f"Neura {unique_host_id(data[CONF_HOST])}", data=data)
            defaults = mqtt
        return self.async_show_form(step_id="mqtt", data_schema=_mqtt_schema(defaults), errors=errors)

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        entry = self._get_reconfigure_entry()
        return await _async_settings_step(self, entry, user_input, reconfigure=True)


class NeuraOptionsFlow(OptionsFlow):
    """Edit credentials, poll interval, and MQTT settings."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        entry = self.config_entry
        assert entry is not None
        return await _async_settings_step(self, entry, user_input, reconfigure=False)


async def _async_settings_step(flow, entry: ConfigEntry, user_input: dict[str, Any] | None, *, reconfigure: bool) -> FlowResult:
    errors: dict[str, str] = {}
    previous = merged_raw(entry)
    defaults = dict(previous)
    defaults[CONF_PASSWORD] = ""
    defaults[CONF_MQTT_PASSWORD] = ""
    if user_input is not None:
        connection = _clean_connection(user_input, previous, require_password=False)
        mqtt = _clean_mqtt(user_input, previous)
        errors.update(_local_errors(connection, mqtt))
        if not errors and _host_taken(flow.hass, connection[CONF_HOST], entry.entry_id):
            errors["base"] = "already_configured"
        if not errors:
            error = await _test_neura(connection[CONF_HOST], connection[CONF_USERNAME], connection[CONF_PASSWORD])
            if error:
                errors["base"] = error
        if not errors:
            error = await _test_mqtt(flow.hass, mqtt)
            if error:
                errors["base"] = error
        if not errors:
            data = {**connection, **mqtt}
            # Options are cleared so a later edit cannot override this save.
            flow.hass.config_entries.async_update_entry(
                entry,
                data=data,
                options={},
                unique_id=unique_host_id(data[CONF_HOST]),
            )
            schedule_reload = getattr(flow.hass.config_entries, "async_schedule_reload", None)
            if schedule_reload is not None:
                schedule_reload(entry.entry_id)
            else:
                flow.hass.async_create_task(flow.hass.config_entries.async_reload(entry.entry_id))
            if reconfigure:
                return flow.async_abort(reason="reconfigure_successful")
            return flow.async_create_entry(title="", data={})
        defaults.update(connection)
        defaults.update(mqtt)
        defaults[CONF_PASSWORD] = str(user_input.get(CONF_PASSWORD) or "")
        defaults[CONF_MQTT_PASSWORD] = str(user_input.get(CONF_MQTT_PASSWORD) or "")
    step_id = "reconfigure" if reconfigure else "init"
    return flow.async_show_form(step_id=step_id, data_schema=_full_schema(defaults), errors=errors)
