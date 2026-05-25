"""
Integration tests — hit the real Kamado Joe API.

Reads credentials from the .env file in the repo root. Skipped automatically
if any required variable is missing so they never break CI without credentials.

Run from hacs_kamadojoe/:
    python3 -m pytest tests/test_integration.py -v
"""
import os
import sys
from pathlib import Path

import pytest

# Load .env from the repo root (two levels up from this file)
_env_path = Path(__file__).parent.parent.parent / ".env"
if _env_path.exists():
    for line in _env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key.strip(), value)

_REQUIRED = ("KAMADO_USERNAME", "KAMADO_PASSWORD", "KAMADO_DEVICE_ID", "KAMADO_THING_NAME")
_missing = [k for k in _REQUIRED if not os.environ.get(k)]

pytestmark = pytest.mark.skipif(
    bool(_missing),
    reason=f"Integration tests require env vars: {', '.join(_missing)}",
)

USERNAME = os.environ.get("KAMADO_USERNAME", "")
PASSWORD = os.environ.get("KAMADO_PASSWORD", "")
DEVICE_ID = os.environ.get("KAMADO_DEVICE_ID", "")
THING_NAME = os.environ.get("KAMADO_THING_NAME", "")
API_BASE = os.environ.get("KAMADO_API_BASE_URL", "https://cas.kamadojoe.com")

import aiohttp
import base64

CLIENT_ID = "0oag310cbuWhqCUx30h7"
CLIENT_SECRET = "sL7Wxyya8C4RDjLyAPvFxUQtvDWKpIjm5-mv31Vr"


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class TestAuthEndpoint:
    @pytest.mark.asyncio
    async def test_login_returns_token(self):
        """POST /api/v1/auth/login should return a JWT token."""
        b64 = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{API_BASE}/api/v1/auth/login",
                json={"username": USERNAME, "password": PASSWORD},
                headers={
                    "Authorization": f"Basic {b64}",
                    "Content-Type": "application/json",
                    "Accept": "*/*",
                    "User-Agent": "KamadoJoe-HA/1.0",
                },
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                assert resp.status == 200, f"Expected 200, got {resp.status}"
                body = await resp.json(content_type=None)
                assert "token" in body, f"Response missing 'token': {body}"
                token = body["token"]
                assert isinstance(token, str) and len(token) > 0
                # Basic JWT structure check (header.payload.signature)
                parts = token.split(".")
                assert len(parts) == 3, f"Token does not look like a JWT: {token[:40]}..."

    @pytest.mark.asyncio
    async def test_login_rejects_bad_password(self):
        """Wrong password should return a 4xx error (API returns 403)."""
        b64 = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{API_BASE}/api/v1/auth/login",
                json={"username": USERNAME, "password": "wrong-password"},
                headers={
                    "Authorization": f"Basic {b64}",
                    "Content-Type": "application/json",
                    "Accept": "*/*",
                    "User-Agent": "KamadoJoe-HA/1.0",
                },
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                assert 400 <= resp.status < 500, f"Expected 4xx, got {resp.status}"


# ---------------------------------------------------------------------------
# Device shadow
# ---------------------------------------------------------------------------

async def _get_token() -> str:
    b64 = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{API_BASE}/api/v1/auth/login",
            json={"username": USERNAME, "password": PASSWORD},
            headers={
                "Authorization": f"Basic {b64}",
                "Content-Type": "application/json",
                "Accept": "*/*",
                "User-Agent": "KamadoJoe-HA/1.0",
            },
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            resp.raise_for_status()
            return (await resp.json(content_type=None))["token"]


class TestDeviceShadowEndpoint:
    @pytest.mark.asyncio
    async def test_shadow_returns_200(self):
        """GET /api/v1/paired-device/{id}/shadows/current should return 200."""
        token = await _get_token()
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{API_BASE}/api/v1/paired-device/{DEVICE_ID}/shadows/current",
                params={"thing_name": THING_NAME},
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "*/*",
                    "User-Agent": "KamadoJoe-HA/1.0",
                },
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                assert resp.status == 200, f"Expected 200, got {resp.status}"

    @pytest.mark.asyncio
    async def test_shadow_has_state_reported(self):
        """Response must contain state.reported."""
        token = await _get_token()
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{API_BASE}/api/v1/paired-device/{DEVICE_ID}/shadows/current",
                params={"thing_name": THING_NAME},
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "*/*",
                    "User-Agent": "KamadoJoe-HA/1.0",
                },
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                body = await resp.json(content_type=None)
                assert "state" in body, f"Missing 'state' key: {list(body.keys())}"
                assert "reported" in body["state"], "Missing 'state.reported'"

    @pytest.mark.asyncio
    async def test_shadow_reported_has_expected_fields(self):
        """state.reported must include the core fields the integration depends on."""
        token = await _get_token()
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{API_BASE}/api/v1/paired-device/{DEVICE_ID}/shadows/current",
                params={"thing_name": THING_NAME},
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "*/*",
                    "User-Agent": "KamadoJoe-HA/1.0",
                },
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                reported = (await resp.json(content_type=None))["state"]["reported"]

                required = ["mac", "pwrOn", "mainTemp", "heat", "fah", "errors"]
                missing = [f for f in required if f not in reported]
                assert not missing, f"Missing fields in state.reported: {missing}"

    @pytest.mark.asyncio
    async def test_shadow_parses_into_kamadojoedata(self):
        """The live response should parse without error into KamadoJoeData."""
        token = await _get_token()
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{API_BASE}/api/v1/paired-device/{DEVICE_ID}/shadows/current",
                params={"thing_name": THING_NAME},
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "*/*",
                    "User-Agent": "KamadoJoe-HA/1.0",
                },
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                body = await resp.json(content_type=None)

        from custom_components.kamado_joe.coordinator import KamadoJoeData
        reported = body["state"]["reported"]
        data = KamadoJoeData(reported, body.get("timestamp", 0))

        assert isinstance(data.power_on, bool)
        assert isinstance(data.is_heating, bool)
        assert isinstance(data.errors, list)
        assert all(e != 0 for e in data.errors), "Zero error codes should be filtered"
        if data.power_on:
            assert data.main_temperature is not None, "mainTemp should be present when powered on"

    @pytest.mark.asyncio
    async def test_shadow_rejects_bad_token(self):
        """A bogus token should return 401."""
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{API_BASE}/api/v1/paired-device/{DEVICE_ID}/shadows/current",
                params={"thing_name": THING_NAME},
                headers={
                    "Authorization": "Bearer not-a-real-token",
                    "Accept": "*/*",
                    "User-Agent": "KamadoJoe-HA/1.0",
                },
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                assert resp.status == 401, f"Expected 401, got {resp.status}"
