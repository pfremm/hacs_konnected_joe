"""Tests for Kamado Joe temperature sensor."""
import pytest
from unittest.mock import MagicMock
from homeassistant.const import UnitOfTemperature

from custom_components.kamado_joe.sensor import KamadoJoeTemperatureSensor
from custom_components.kamado_joe.coordinator import KamadoJoeData
from .conftest import SAMPLE_REPORTED, DEVICE_ID


def _make_coordinator(reported=None):
    coord = MagicMock()
    coord.data = KamadoJoeData(reported or SAMPLE_REPORTED, 0)
    return coord


class TestTemperatureSensor:
    def test_returns_temperature_when_powered_on(self):
        sensor = KamadoJoeTemperatureSensor(_make_coordinator(), DEVICE_ID)
        assert sensor.native_value == 350

    def test_returns_none_when_powered_off(self):
        reported = {**SAMPLE_REPORTED, "pwrOn": False}
        sensor = KamadoJoeTemperatureSensor(_make_coordinator(reported), DEVICE_ID)
        assert sensor.native_value is None

    def test_returns_none_when_no_data(self):
        coord = MagicMock()
        coord.data = None
        sensor = KamadoJoeTemperatureSensor(coord, DEVICE_ID)
        assert sensor.native_value is None

    def test_unit_fahrenheit(self):
        sensor = KamadoJoeTemperatureSensor(_make_coordinator(), DEVICE_ID)
        assert sensor.native_unit_of_measurement == UnitOfTemperature.FAHRENHEIT

    def test_unit_celsius(self):
        reported = {**SAMPLE_REPORTED, "fah": False}
        sensor = KamadoJoeTemperatureSensor(_make_coordinator(reported), DEVICE_ID)
        assert sensor.native_unit_of_measurement == UnitOfTemperature.CELSIUS

    def test_extra_attrs_include_heating_state(self):
        sensor = KamadoJoeTemperatureSensor(_make_coordinator(), DEVICE_ID)
        attrs = sensor.extra_state_attributes
        assert attrs["is_heating"] is True
        assert attrs["target_temperature"] == 400

    def test_extra_attrs_include_network_info(self):
        sensor = KamadoJoeTemperatureSensor(_make_coordinator(), DEVICE_ID)
        attrs = sensor.extra_state_attributes
        assert attrs["ssid"] == "TestNet"
        assert attrs["signal_strength_dbm"] == -55

    def test_extra_attrs_include_errors(self):
        reported = {**SAMPLE_REPORTED, "errors": [0, 0, 3, 0]}
        sensor = KamadoJoeTemperatureSensor(_make_coordinator(reported), DEVICE_ID)
        assert sensor.extra_state_attributes["errors"] == [3]

    def test_unique_id(self):
        sensor = KamadoJoeTemperatureSensor(_make_coordinator(), DEVICE_ID)
        assert sensor.unique_id == f"{DEVICE_ID}_temperature"

    def test_device_info(self):
        sensor = KamadoJoeTemperatureSensor(_make_coordinator(), DEVICE_ID)
        assert (("kamado_joe", DEVICE_ID),) == tuple(sensor.device_info["identifiers"])
        assert sensor.device_info["manufacturer"] == "Kamado Joe"
