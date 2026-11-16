"""Constants for the Neura Webdialog integration.

MQTT topics and field ids match datasauger/config.php and datasauger.php.
Payloads stay plain numbers (QoS 0, not retained), same as the PHP publisher.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

DOMAIN = "neura_webdialog"

DEFAULT_HOST = ""
DEFAULT_USERNAME = ""
DEFAULT_SCAN_INTERVAL = 60

DEFAULT_MQTT_HOST = ""
DEFAULT_MQTT_PORT = 1883
DEFAULT_MQTT_CLIENT_ID = "neura_webdialog"

CONF_MQTT_ENABLED = "mqtt_enabled"
CONF_MQTT_HOST = "mqtt_host"
CONF_MQTT_PORT = "mqtt_port"
CONF_MQTT_USERNAME = "mqtt_username"
CONF_MQTT_PASSWORD = "mqtt_password"
CONF_MQTT_CLIENT_ID = "mqtt_client_id"

PATH_LOGIN = "/neura/mobile/jsp/login.jsp"
PATH_MENU = "/neura/mobile/jsp/mainmenu.jsp"
PATH_SCHEMA = "/neura/mobile/jsp/schema.jsp"

LOGIN_KEY = "login"
LOGIN_TOPIC = "Neura/loginStatus"

Kind = Literal["float", "bool"]


@dataclass(frozen=True, slots=True)
class DataPoint:
    """One value scraped from schema.jsp."""

    key: str
    tag_id: str
    kind: Kind
    mqtt_topic: str
    icon: str
    binary_device_class: str | None = None


DATA_POINTS: tuple[DataPoint, ...] = (
    DataPoint("screed", "screed", "float", "Neura/status/Estrichtemperatur", "mdi:radiator"),
    DataPoint("room", "room", "float", "Neura/status/Raumtemperatur", "mdi:home-thermometer"),
    DataPoint(
        "heater_rod",
        "heater_rod",
        "bool",
        "Neura/status/Boiler_E_patrone",
        "mdi:heating-coil",
        "heat",
    ),
    DataPoint("cylinder", "cylinder", "float", "Neura/status/Boilertemperatur", "mdi:water-boiler"),
    DataPoint("flow", "flow", "float", "Neura/status/Vorlauf", "mdi:thermometer-chevron-up"),
    DataPoint("return", "return", "float", "Neura/status/Ruecklauf", "mdi:thermometer-chevron-down"),
    DataPoint("comp_in", "comp_in", "float", "Neura/status/Kompressor_ein", "mdi:thermometer-minus"),
    DataPoint("comp_out", "comp_out", "float", "Neura/status/Kompressor_aus", "mdi:thermometer-plus"),
    DataPoint(
        "cylinder_pump",
        "cylinder_pump",
        "bool",
        "Neura/status/Umschaltventil_Boilerladung",
        "mdi:valve",
    ),
    DataPoint(
        "heatpump_2",
        "heatpump_2",
        "bool",
        "Neura/status/Waermepumpe",
        "mdi:heat-pump",
        "running",
    ),
    DataPoint(
        "circulator_pump",
        "circulator_pump",
        "bool",
        "Neura/status/Umwaelzpumpe",
        "mdi:pump",
        "running",
    ),
)
