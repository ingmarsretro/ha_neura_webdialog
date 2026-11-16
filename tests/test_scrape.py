"""Parser and payload tests. They do not need Home Assistant or the heat pump."""

from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from pathlib import Path


def _load_package():
    root = Path(__file__).resolve().parents[1] / "custom_components" / "neura_webdialog"
    package_name = "neura_webdialog_under_test"
    package = types.ModuleType(package_name)
    package.__path__ = [str(root)]  # type: ignore[attr-defined]
    sys.modules[package_name] = package

    def load(name: str):
        full_name = f"{package_name}.{name}"
        spec = importlib.util.spec_from_file_location(full_name, root / f"{name}.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[full_name] = module
        assert spec is not None and spec.loader is not None
        spec.loader.exec_module(module)
        return module

    const = load("const")
    scrape = load("scrape")
    return const, scrape


CONST, SCRAPE = _load_package()

SCHEMA_HTML = """
<html>
  <body>
    <input type="hidden" name="SESSIONID" value="ABC123">
    <input id="screed" value="23.5°C">
    <input id="room" value="21°C" />
    <input
      id="heater_rod"
      value="ON">
    <input id="cylinder" value="48.2°C">
    <input id="flow" value="35°C">
    <input id="return" value="28.5 °C">
    <input id="comp_in" value="15.5°C">
    <input id="comp_out" value="40°C">
    <input id="cylinder_pump" value="OFF">
    <input id="heatpump_2" value="ON">
    <input id="circulator_pump" value="OFF">
  </body>
</html>
"""


class ScrapeTests(unittest.TestCase):
    def test_php_floatval_matches_datasauger(self) -> None:
        cases = {
            "23.5°C": 23.5,
            "23°C": 23.0,
            "23,5°C": 23.0,
            "  18.25 °C": 18.25,
            "": 0.0,
            "ON": 0.0,
            "-1.5°C": -1.5,
        }
        for raw, expected in cases.items():
            self.assertEqual(SCRAPE.php_floatval(raw), expected)

    def test_mqtt_number_format_matches_php_cast(self) -> None:
        self.assertEqual(SCRAPE.format_mqtt_number(23.5), "23.5")
        self.assertEqual(SCRAPE.format_mqtt_number(23.0), "23")
        self.assertEqual(SCRAPE.format_mqtt_number(0.0), "0")
        self.assertEqual(SCRAPE.format_mqtt_number(-5.0), "-5")
        self.assertEqual(SCRAPE.format_mqtt_number(-1.5), "-1.5")

    def test_bool_is_only_exact_on(self) -> None:
        self.assertTrue(SCRAPE.interpret_value("ON", "bool"))
        self.assertFalse(SCRAPE.interpret_value("OFF", "bool"))
        self.assertFalse(SCRAPE.interpret_value("on", "bool"))
        self.assertFalse(SCRAPE.interpret_value("ON ", "bool"))

    def test_schema_page_and_topics(self) -> None:
        page = SCRAPE.parse_page(SCHEMA_HTML)
        self.assertEqual(SCRAPE.extract_session_id(page), "ABC123")
        values, missing = SCRAPE.read_points(page)
        self.assertEqual(missing, [])
        self.assertEqual(
            values,
            {
                "screed": 23.5,
                "room": 21.0,
                "heater_rod": True,
                "cylinder": 48.2,
                "flow": 35.0,
                "return": 28.5,
                "comp_in": 15.5,
                "comp_out": 40.0,
                "cylinder_pump": False,
                "heatpump_2": True,
                "circulator_pump": False,
            },
        )
        messages = SCRAPE.build_mqtt_messages(values, login_ok=True)
        self.assertEqual(
            messages,
            [
                ("Neura/loginStatus", "1"),
                ("Neura/status/Estrichtemperatur", "23.5"),
                ("Neura/status/Raumtemperatur", "21"),
                ("Neura/status/Boiler_E_patrone", "1"),
                ("Neura/status/Boilertemperatur", "48.2"),
                ("Neura/status/Vorlauf", "35"),
                ("Neura/status/Ruecklauf", "28.5"),
                ("Neura/status/Kompressor_ein", "15.5"),
                ("Neura/status/Kompressor_aus", "40"),
                ("Neura/status/Umschaltventil_Boilerladung", "0"),
                ("Neura/status/Waermepumpe", "1"),
                ("Neura/status/Umwaelzpumpe", "0"),
            ],
        )
        topics = [point.mqtt_topic for point in CONST.DATA_POINTS]
        self.assertEqual([topic for topic, _payload in messages[1:]], topics)

    def test_failed_login_publishes_only_status_zero(self) -> None:
        self.assertEqual(
            SCRAPE.build_mqtt_messages({"screed": 20.0}, login_ok=False),
            [("Neura/loginStatus", "0")],
        )

    def test_missing_field_is_skipped(self) -> None:
        html = '<input id="screed" value="19°C"><input id="room" value="20°C">'
        values, missing = SCRAPE.read_points(SCRAPE.parse_page(html))
        self.assertNotIn("flow", values)
        self.assertIn("flow", missing)
        messages = SCRAPE.build_mqtt_messages(values, login_ok=True)
        topics = [topic for topic, _payload in messages]
        self.assertIn("Neura/status/Estrichtemperatur", topics)
        self.assertNotIn("Neura/status/Vorlauf", topics)
        self.assertLess(
            topics.index("Neura/status/Estrichtemperatur"),
            topics.index("Neura/status/Raumtemperatur"),
        )

    def test_windows_1252_degree_sign(self) -> None:
        raw = '<input id="screed" value="21.5\xb0C">'.encode("latin-1")
        values, _missing = SCRAPE.read_points(SCRAPE.parse_page(SCRAPE.decode_html(raw)))
        self.assertEqual(values["screed"], 21.5)

    def test_login_form_and_host(self) -> None:
        page = SCRAPE.parse_page('<input name="PASSWORD" type="password" value="">')
        self.assertTrue(SCRAPE.page_has_login_form(page))
        self.assertIsNone(SCRAPE.extract_session_id(page))
        self.assertEqual(SCRAPE.normalize_base_url("192.0.2.10"), "http://192.0.2.10")
        self.assertEqual(
            SCRAPE.normalize_base_url("http://192.0.2.10/neura/mobile/jsp/login.jsp"),
            "http://192.0.2.10",
        )
        self.assertEqual(
            SCRAPE.unique_host_id("https://Pump.Local:8443/foo"),
            "pump.local:8443",
        )
        with self.assertRaises(ValueError):
            SCRAPE.normalize_base_url("   ")
        with self.assertRaises(ValueError):
            SCRAPE.normalize_base_url("ftp://192.0.2.10")


if __name__ == "__main__":
    unittest.main()
