"""Config flow for the Kamado Joe integration."""
from __future__ import annotations

import base64
import logging

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import (
    API_BASE_URL,
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

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_DEVICE_ID): str,
        vol.Required(CONF_THING_NAME): str,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
            int, vol.Range(min=10, max=3600)
        ),
    }
)


async def _validate_credentials(username: str, password: str) -> None:
    """Attempt login to verify credentials; raises on failure."""
    b64 = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                f"{API_BASE_URL}{API_LOGIN_PATH}",
                json={"username": username, "password": password},
                headers={
                    "Authorization": f"Basic {b64}",
                    "Content-Type": "application/json",
                    "Accept": "*/*",
                    "User-Agent": "KamadoJoe-HA/1.0",
                },
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 401:
                    raise InvalidAuth
                if resp.status >= 500:
                    raise CannotConnect
                resp.raise_for_status()
                body = await resp.json(content_type=None)
                if not (body.get("token") or body.get("access_token")):
                    raise CannotConnect
        except aiohttp.ClientError as err:
            raise CannotConnect from err


class KamadoJoeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the initial configuration UI flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await _validate_credentials(
                    user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected error during Kamado Joe config validation")
                errors["base"] = "unknown"
            else:
                device_id = user_input[CONF_DEVICE_ID]
                await self.async_set_unique_id(device_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Kamado Joe ({device_id})",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Raised when we cannot reach the Kamado Joe API."""


class InvalidAuth(HomeAssistantError):
    """Raised when credentials are rejected by the API."""
