"""HTML parsing and MQTT payload formatting compatible with the PHP datasauger."""

from __future__ import annotations

import html as html_lib
import math
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urlparse

from .const import DATA_POINTS, LOGIN_TOPIC, DataPoint

_ATTR_RE = re.compile(
    r"""([A-Za-z_:][-A-Za-z0-9_:.]*)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+))"""
)
_TAG_RE = re.compile(r"<[A-Za-z][^>]*>", re.DOTALL)


def normalize_base_url(host: str) -> str:
    """Return scheme://host[:port] from an IP, hostname, or pasted URL."""

    text = host.strip().rstrip("/")
    if not text:
        raise ValueError("empty host")
    if "://" not in text:
        text = f"http://{text}"
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("invalid host")
    return f"{parsed.scheme}://{parsed.netloc}"


def unique_host_id(host: str) -> str:
    """Stable id for one heat pump web interface."""

    return urlparse(normalize_base_url(host)).netloc.lower()


def php_floatval(raw: str) -> float:
    """Match PHP floatval(), including the °C strip used by datasauger.php."""

    text = raw.replace("°C", "").lstrip()
    if not text:
        return 0.0
    index = 0
    if text[0] in "+-":
        index = 1
    saw_digit = False
    saw_dot = False
    while index < len(text):
        char = text[index]
        if char.isdigit():
            saw_digit = True
            index += 1
            continue
        if char == "." and not saw_dot:
            saw_dot = True
            index += 1
            continue
        break
    if not saw_digit:
        return 0.0
    number = text[:index]
    if number in {"+", "-", "+.", "-.", "."}:
        return 0.0
    return float(number)


def format_mqtt_number(value: float) -> str:
    """Stringify a float the way PHP casts it for mqtt publish()."""

    if not math.isfinite(value):
        return "0"
    rounded = round(value, 10)
    if rounded.is_integer():
        return str(int(rounded))
    return f"{rounded:.10f}".rstrip("0").rstrip(".")


def interpret_value(raw: str, kind: str) -> float | bool:
    """Convert a schema.jsp value attribute the same way the PHP switch does."""

    if kind == "bool":
        return raw == "ON"
    return php_floatval(raw)


def format_mqtt_value(value: float | bool, kind: str) -> str:
    """MQTT body for one point. Bools are 1/0, floats are plain numbers."""

    if kind == "bool":
        return "1" if value else "0"
    return format_mqtt_number(float(value))


def decode_html(raw: bytes) -> str:
    """Decode a Neura page. Valid UTF-8 is kept, otherwise windows-1252."""

    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("windows-1252", errors="replace")


@dataclass(frozen=True, slots=True)
class ParsedPage:
    """Attribute values keyed by id and by name."""

    by_id: dict[str, str | None]
    by_name: dict[str, str | None]


class _ElementParser(HTMLParser):
    """Collect the first value attribute for each id and name."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.by_id: dict[str, str | None] = {}
        self.by_name: dict[str, str | None] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {key: value for key, value in attrs}
        element_id = attr.get("id")
        if element_id and element_id not in self.by_id:
            self.by_id[element_id] = attr.get("value")
        name = attr.get("name")
        if name and name not in self.by_name:
            self.by_name[name] = attr.get("value")


def _attrs(blob: str) -> dict[str, str | None]:
    found: dict[str, str | None] = {}
    for match in _ATTR_RE.finditer(blob):
        raw = match.group(2)
        if raw is None:
            raw = match.group(3)
        if raw is None:
            raw = match.group(4)
        found[match.group(1).lower()] = html_lib.unescape(raw or "")
    return found


def _fill_from_regex(html: str, by_id: dict[str, str | None], by_name: dict[str, str | None]) -> None:
    """Fill ids the stdlib parser missed. Existing keys are left untouched."""

    for tag in _TAG_RE.findall(html):
        attrs = _attrs(tag)
        element_id = attrs.get("id")
        if element_id and element_id not in by_id:
            by_id[element_id] = attrs.get("value")
        name = attrs.get("name")
        if name and name not in by_name:
            by_name[name] = attrs.get("value")


def parse_page(html: str) -> ParsedPage:
    """Parse id/name value attributes from a Neura JSP page."""

    parser = _ElementParser()
    parser.feed(html.replace("\x00", ""))
    parser.close()
    _fill_from_regex(html, parser.by_id, parser.by_name)
    return ParsedPage(by_id=parser.by_id, by_name=parser.by_name)


def extract_session_id(page: ParsedPage) -> str | None:
    """Return SESSIONID from the main menu page, if the login succeeded."""

    for bucket in (page.by_name, page.by_id):
        value = bucket.get("SESSIONID")
        if value:
            return value
    return None


def page_has_login_form(page: ParsedPage) -> bool:
    """True when the response is the login form instead of a data page."""

    return "PASSWORD" in page.by_name or "PASSWORD" in page.by_id


def read_points(page: ParsedPage, points: tuple[DataPoint, ...] = DATA_POINTS) -> tuple[dict[str, float | bool], list[str]]:
    """Read known points. Missing tags are listed and omitted."""

    values: dict[str, float | bool] = {}
    missing: list[str] = []
    for point in points:
        if point.tag_id not in page.by_id or page.by_id[point.tag_id] is None:
            missing.append(point.tag_id)
            continue
        values[point.key] = interpret_value(page.by_id[point.tag_id] or "", point.kind)
    return values, missing


def build_mqtt_messages(values: dict[str, float | bool], *, login_ok: bool) -> list[tuple[str, str]]:
    """Build the same topic/payload pairs the PHP script publishes.

    A failed login publishes only Neura/loginStatus 0 and then stops.
    """

    messages = [(LOGIN_TOPIC, "1" if login_ok else "0")]
    if not login_ok:
        return messages
    for point in DATA_POINTS:
        if point.key not in values:
            continue
        messages.append((point.mqtt_topic, format_mqtt_value(values[point.key], point.kind)))
    return messages
