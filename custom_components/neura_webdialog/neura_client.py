"""HTTP session against the Neura Webdialog JSP interface."""

from __future__ import annotations

import logging

import aiohttp

from .const import DATA_POINTS, PATH_LOGIN, PATH_MENU, PATH_SCHEMA
from .scrape import (
    decode_html,
    extract_session_id,
    normalize_base_url,
    page_has_login_form,
    parse_page,
    read_points,
)

_LOGGER = logging.getLogger(__name__)

_USER_AGENT = "GuzzleHttp/7"


class NeuraError(Exception):
    """Base error for a failed Neura read."""


class NeuraAuthError(NeuraError):
    """Login was rejected or the session is gone."""


class NeuraConnectionError(NeuraError):
    """The web interface could not be reached."""


class NeuraClient:
    """Log in and read schema.jsp the same way datasauger.php does."""

    def __init__(self, host: str, username: str, password: str) -> None:
        self._base_url = normalize_base_url(host)
        self._username = username
        self._password = password

    @property
    def base_url(self) -> str:
        return self._base_url

    def _url(self, path: str) -> str:
        return f"{self._base_url}{path}"

    async def async_read(self) -> dict[str, float | bool]:
        """Return parsed point values. Raises NeuraAuthError or NeuraConnectionError."""

        timeout = aiohttp.ClientTimeout(total=30, connect=10, sock_read=20)
        jar = aiohttp.CookieJar(unsafe=True)
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(
            cookie_jar=jar,
            connector=connector,
            timeout=timeout,
            headers={"User-Agent": _USER_AGENT},
            trust_env=False,
        ) as session:
            await self._request(session, "GET", self._url(PATH_LOGIN))
            menu_html = await self._request(
                session,
                "POST",
                self._url(PATH_MENU),
                {
                    "USER": self._username,
                    "PASSWORD": self._password,
                    "loginButton": "LOGIN",
                },
            )
            session_id = extract_session_id(parse_page(menu_html))
            if not session_id:
                raise NeuraAuthError("Anmeldung fehlgeschlagen, keine SESSIONID erhalten.")
            _LOGGER.debug("Neura SESSIONID erhalten (%s Zeichen)", len(session_id))

            schema_html = await self._request(
                session,
                "POST",
                self._url(PATH_SCHEMA),
                {"SESSIONID": session_id},
            )
            schema = parse_page(schema_html)
            known_present = any(point.tag_id in schema.by_id for point in DATA_POINTS)
            if page_has_login_form(schema) and not known_present:
                raise NeuraAuthError("Die Schema-Seite hat das Login-Formular zurückgegeben.")

            values, missing = read_points(schema)
            if not values:
                raise NeuraError("Die Schema-Seite enthält keine bekannten Messwerte.")
            if missing:
                _LOGGER.debug("Fehlende Neura-Felder: %s", ", ".join(missing))
            _LOGGER.debug("Neura Werte: %s", values)
            return values

    async def _request(
        self,
        session: aiohttp.ClientSession,
        method: str,
        url: str,
        data: dict[str, str] | None = None,
    ) -> str:
        _LOGGER.debug("%s %s", method, url)
        try:
            async with session.request(method, url, data=data, allow_redirects=True) as response:
                if response.status in {401, 403}:
                    raise NeuraAuthError(f"HTTP {response.status} bei {url}")
                if response.status >= 400:
                    raise NeuraConnectionError(f"HTTP {response.status} bei {url}")
                raw = await response.read()
        except NeuraError:
            raise
        except (aiohttp.ClientError, TimeoutError) as err:
            raise NeuraConnectionError(f"Neura-Weboberfläche nicht erreichbar ({url})") from err
        return decode_html(raw)
