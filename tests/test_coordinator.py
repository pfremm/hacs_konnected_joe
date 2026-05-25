"""Tests for KamadoJoeCoordinator and KamadoJoeData."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.kamado_joe.coordinator import KamadoJoeCoordinator, KamadoJoeData
from .conftest import VALID_CONFIG, SAMPLE_REPORTED, SAMPLE_SHADOW, DEVICE_ID


# ---------------------------------------------------------------------------
# KamadoJoeData parsing
# ---------------------------------------------------------------------------

class TestKamadoJoeData:
    def test_parses_basic_fields(self):
        data = KamadoJoeData(SAMPLE_REPORTED, 1700000000)
        assert data.power_on is True
        assert data.engaged is True
        assert data.door_open is False
        assert data.lid_open is False
        assert data.main_temperature == 350
        assert data.is_fahrenheit is True
        assert data.ssid == "TestNet"
        assert data.rssi == -55
        assert data.timestamp == 1700000000

    def test_filters_zero_errors(self):
        reported = {**SAMPLE_REPORTED, "errors": [0, 0, 1, 0]}
        data = KamadoJoeData(reported, 0)
        assert data.errors == [1]

    def test_no_errors_when_all_zero(self):
        data = KamadoJoeData(SAMPLE_REPORTED, 0)
        assert data.errors == []

    def test_detects_heating(self):
        data = KamadoJoeData(SAMPLE_REPORTED, 0)
        assert data.is_heating is True
        assert data.target_temperature == 400

    def test_not_heating_when_all_elements_off(self):
        reported = {**SAMPLE_REPORTED, "heat": {
            "t1": {"heating": False},
            "t2": {"heating": False},
        }}
        data = KamadoJoeData(reported, 0)
        assert data.is_heating is False
        assert data.target_temperature is None

    def test_target_temperature_ignored_when_zero(self):
        reported = {**SAMPLE_REPORTED, "heat": {
            "t2": {"heating": True, "intensity": 50, "trgt": 0},
        }}
        data = KamadoJoeData(reported, 0)
        assert data.is_heating is True
        assert data.target_temperature is None

    def test_handles_missing_heat(self):
        reported = {**SAMPLE_REPORTED, "heat": None}
        data = KamadoJoeData(reported, 0)
        assert data.is_heating is False
        assert data.heating_elements == {}

    def test_power_off(self):
        reported = {**SAMPLE_REPORTED, "pwrOn": False}
        data = KamadoJoeData(reported, 0)
        assert data.power_on is False

    def test_celsius(self):
        reported = {**SAMPLE_REPORTED, "fah": False, "mainTemp": 180}
        data = KamadoJoeData(reported, 0)
        assert data.is_fahrenheit is False
        assert data.main_temperature == 180


# ---------------------------------------------------------------------------
# Power outage state machine
# ---------------------------------------------------------------------------

class TestPowerOutageStateMachine:
    def _make_coordinator(self, hass=None):
        hass = hass or MagicMock()
        coord = KamadoJoeCoordinator(hass, VALID_CONFIG)
        return coord

    def _data(self, power_on, is_heating, temp, target):
        reported = {
            **SAMPLE_REPORTED,
            "pwrOn": power_on,
            "mainTemp": temp,
            "heat": {
                "t2": {"heating": is_heating, "intensity": 50 if is_heating else 0, "trgt": target or 0},
            },
        }
        return KamadoJoeData(reported, 0)

    def test_no_outage_on_normal_operation(self):
        coord = self._make_coordinator()
        coord._update_outage_state(self._data(True, True, 350, 400))
        assert coord.power_outage_detected is False

    def test_outage_detected_when_power_drops_before_target(self):
        coord = self._make_coordinator()
        # Start heating toward 400°F at 350°F
        coord._update_outage_state(self._data(True, True, 350, 400))
        # Power goes off at 350°F — never reached 400°F
        coord._update_outage_state(self._data(False, False, 350, None))
        assert coord.power_outage_detected is True

    def test_no_outage_when_target_reached_before_power_off(self):
        coord = self._make_coordinator()
        coord._update_outage_state(self._data(True, True, 350, 400))
        # Temperature reaches target while still on
        coord._update_outage_state(self._data(True, True, 400, 400))
        # Now power goes off
        coord._update_outage_state(self._data(False, False, 400, None))
        assert coord.power_outage_detected is False

    def test_outage_clears_when_power_restored(self):
        coord = self._make_coordinator()
        coord._update_outage_state(self._data(True, True, 350, 400))
        coord._update_outage_state(self._data(False, False, 350, None))
        assert coord.power_outage_detected is True
        # Power comes back on
        coord._update_outage_state(self._data(True, False, 200, None))
        assert coord.power_outage_detected is False

    def test_no_outage_without_target_temperature(self):
        """If no target is set, there is nothing to compare against — no outage."""
        coord = self._make_coordinator()
        # Heating but trgt=0 so target_temperature is None
        coord._update_outage_state(self._data(True, True, 350, 0))
        coord._update_outage_state(self._data(False, False, 350, None))
        assert coord.power_outage_detected is False

    def test_outage_stays_latched_across_multiple_polls(self):
        coord = self._make_coordinator()
        coord._update_outage_state(self._data(True, True, 350, 400))
        coord._update_outage_state(self._data(False, False, 350, None))
        # Multiple polls while still off
        coord._update_outage_state(self._data(False, False, 300, None))
        coord._update_outage_state(self._data(False, False, 250, None))
        assert coord.power_outage_detected is True


# ---------------------------------------------------------------------------
# Coordinator HTTP layer
# ---------------------------------------------------------------------------

class TestCoordinatorHTTP:
    def _make_coordinator(self):
        hass = MagicMock()
        coord = KamadoJoeCoordinator(hass, VALID_CONFIG)
        return coord

    @pytest.mark.asyncio
    async def test_successful_update(self):
        coord = self._make_coordinator()
        coord._login = AsyncMock(return_value="fake-token")
        coord._fetch_shadow = AsyncMock(return_value=SAMPLE_SHADOW)

        data = await coord._async_update_data()

        assert data.power_on is True
        assert data.main_temperature == 350
        assert data.is_heating is True

    @pytest.mark.asyncio
    async def test_retries_after_token_expiry(self):
        coord = self._make_coordinator()
        coord._token = "old-token"
        coord._login = AsyncMock(return_value="new-token")

        # First fetch raises UpdateFailed (401), second succeeds
        coord._fetch_shadow = AsyncMock(
            side_effect=[UpdateFailed("Token expired"), SAMPLE_SHADOW]
        )

        data = await coord._async_update_data()

        assert coord._login.call_count == 1
        assert coord._fetch_shadow.call_count == 2
        assert data.power_on is True

    @pytest.mark.asyncio
    async def test_raises_config_entry_auth_failed_on_bad_credentials(self):
        coord = self._make_coordinator()
        coord._login = AsyncMock(side_effect=ConfigEntryAuthFailed("Bad credentials"))

        with pytest.raises(ConfigEntryAuthFailed):
            await coord._async_update_data()

    @pytest.mark.asyncio
    async def test_raises_update_failed_on_network_error(self):
        import aiohttp
        coord = self._make_coordinator()
        coord._login = AsyncMock(return_value="token")
        coord._fetch_shadow = AsyncMock(side_effect=aiohttp.ClientError())

        with pytest.raises(UpdateFailed):
            await coord._async_update_data()

    @pytest.mark.asyncio
    async def test_raises_update_failed_on_missing_reported(self):
        coord = self._make_coordinator()
        coord._login = AsyncMock(return_value="token")
        coord._fetch_shadow = AsyncMock(return_value={"state": {}})

        with pytest.raises(UpdateFailed, match="missing state.reported"):
            await coord._async_update_data()
