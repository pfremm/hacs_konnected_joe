"""DataUpdateCoordinator for Kamado Joe grill polling."""
from __future__ import annotations

import base64
import logging
from datetime import timedelta
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    API_BASE_URL,
    API_DEVICE_SHADOW_PATH,
    API_LOGIN_PATH,
    CLIENT_ID,
    CLIENT_SECRET,
    CONF_DEVICE_ID,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_THING_NAME,
    CONF_USERNAME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class KamadoJoeData:
    """Parsed snapshot of grill state from the device shadow API."""

    def __init__(self, reported: dict, timestamp: int) -> None:
        self.power_on: bool = bool(reported.get("pwrOn", False))
        self.engaged: bool = bool(reported.get("engaged", False))
        self.door_open: bool = bool(reported.get("doorOpn", False))
        self.lid_open: bool = bool(reported.get("lidOpn", False))
        self.main_temperature: float | None = self._parse_float(reported.get("mainTemp"))
        self.is_fahrenheit: bool = bool(reported.get("fah", True))
        self.ssid: str | None = reported.get("ssid")
        self.rssi: int | None = reported.get("RSSI")
        self.errors: list[int] = [e for e in (reported.get("errors") or []) if e != 0]
        self.timestamp: int = timestamp

        # Parse heating elements from the `heat` dict (keys: t1, t2, t3, t4)
        self.heating_elements: dict[str, dict[str, Any]] = {}
        self.is_heating: bool = False
        self.target_temperature: float | None = None

        for elem_id, elem_data in (reported.get("heat") or {}).items():
            if not isinstance(elem_data, dict):
                continue
            heating = bool(elem_data.get("heating", False))
            target = self._parse_float(elem_data.get("trgt"))
            self.heating_elements[elem_id] = {
                "heating": heating,
                "intensity": int(elem_data.get("intensity") or 0),
                "target": target,
                "max": self._parse_float(elem_data.get("max")),
                "min": self._parse_float(elem_data.get("min")),
            }
            if heating:
                self.is_heating = True
                if target and target > 0:
                    self.target_temperature = target

    @staticmethod
    def _parse_float(val: Any) -> float | None:
        if val is None:
            return None
        try:
            result = float(val)
            return None if result != result else result  # filter NaN
        except (ValueError, TypeError):
            return None


class KamadoJoeCoordinator(DataUpdateCoordinator[KamadoJoeData]):
    """Coordinator that polls the Kamado Joe cloud API and tracks outage state."""

    def __init__(self, hass: HomeAssistant, config: dict) -> None:
        self._username: str = config[CONF_USERNAME]
        self._password: str = config[CONF_PASSWORD]
        self._device_id: str = config[CONF_DEVICE_ID]
        self._thing_name: str = config[CONF_THING_NAME]
        self._token: str | None = None
        self._session: aiohttp.ClientSession | None = None

        # Power outage state machine
        self._tracking_cook: bool = False      # grill is/was heating toward a target
        self._last_target: float | None = None  # target temp at start of tracked cook
        self._outage_detected: bool = False    # True until grill powers back on

        scan_interval = int(config.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def _login(self) -> str:
        """Authenticate with the Kamado Joe API and return a JWT token."""
        session = await self._get_session()
        b64 = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()

        async with session.post(
            f"{API_BASE_URL}{API_LOGIN_PATH}",
            json={"username": self._username, "password": self._password},
            headers={
                "Authorization": f"Basic {b64}",
                "Content-Type": "application/json",
                "Accept": "*/*",
                "User-Agent": "KamadoJoe-HA/1.0",
            },
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            if resp.status == 401:
                raise ConfigEntryAuthFailed("Invalid Kamado Joe credentials")
            resp.raise_for_status()
            body = await resp.json(content_type=None)
            token = body.get("token") or body.get("access_token")
            if not token:
                raise UpdateFailed("Login response is missing a token field")
            return token

    async def _fetch_shadow(self) -> dict:
        """Fetch the device shadow from the API using the stored token."""
        session = await self._get_session()
        url = f"{API_BASE_URL}{API_DEVICE_SHADOW_PATH.format(device_id=self._device_id)}"

        async with session.get(
            url,
            params={"thing_name": self._thing_name},
            headers={
                "Authorization": f"Bearer {self._token}",
                "Accept": "*/*",
                "User-Agent": "KamadoJoe-HA/1.0",
            },
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            if resp.status == 401:
                self._token = None
                raise UpdateFailed("Token expired or invalid")
            resp.raise_for_status()
            return await resp.json(content_type=None)

    # ------------------------------------------------------------------
    # Power outage state machine
    # ------------------------------------------------------------------

    def _update_outage_state(self, data: KamadoJoeData) -> None:
        """
        Advance the power outage state machine on every poll.

        States:
        - Not tracking: grill is off or heating without a target temp.
        - Tracking:  grill is on, heating, and has a positive target temp.
        - Outage:    tracking was active when power went off and temp had
                     not yet reached the target.  Stays set until power
                     returns.
        """
        # Start or refresh tracking whenever the grill is actively heating
        # toward a specific target temperature.
        if data.power_on and data.is_heating and data.target_temperature:
            self._tracking_cook = True
            self._last_target = data.target_temperature

        # If grill is on and temp has reached or exceeded the target naturally,
        # the cook is done — stop tracking so a subsequent power-off isn't
        # flagged as an outage.
        if (
            self._tracking_cook
            and data.power_on
            and data.main_temperature is not None
            and self._last_target is not None
            and data.main_temperature >= self._last_target
        ):
            self._tracking_cook = False

        # Power went off while we were tracking a cook that hadn't finished.
        if self._tracking_cook and not data.power_on:
            if (
                data.main_temperature is not None
                and self._last_target is not None
                and data.main_temperature < self._last_target
            ):
                self._outage_detected = True
            self._tracking_cook = False

        # Clear the outage latch once the grill powers back on.
        if data.power_on:
            self._outage_detected = False

    @property
    def power_outage_detected(self) -> bool:
        """True when the grill lost power before hitting its target temp."""
        return self._outage_detected

    # ------------------------------------------------------------------
    # DataUpdateCoordinator interface
    # ------------------------------------------------------------------

    async def _async_update_data(self) -> KamadoJoeData:
        """Fetch latest grill data, refreshing the token once if needed."""
        for attempt in range(2):
            try:
                if not self._token:
                    self._token = await self._login()
                raw = await self._fetch_shadow()
                break
            except ConfigEntryAuthFailed:
                raise
            except UpdateFailed:
                if attempt == 0:
                    # Token likely expired — clear it and retry with a fresh login.
                    self._token = None
                    continue
                raise
            except aiohttp.ClientError as err:
                raise UpdateFailed(f"Network error communicating with Kamado Joe API: {err}") from err

        reported = (raw.get("state") or {}).get("reported") or {}
        if not reported:
            raise UpdateFailed("API response is missing state.reported")

        data = KamadoJoeData(reported, raw.get("timestamp", 0))
        self._update_outage_state(data)
        return data

    async def async_close(self) -> None:
        """Release the aiohttp session when the integration is unloaded."""
        if self._session and not self._session.closed:
            await self._session.close()
