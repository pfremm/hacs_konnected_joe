"""Tests for Kamado Joe binary sensors."""
import pytest
from unittest.mock import MagicMock

from custom_components.kamado_joe.binary_sensor import (
    KamadoJoePowerSensor,
    KamadoJoeHeatingSensor,
    KamadoJoePowerOutageSensor,
)
from custom_components.kamado_joe.coordinator import KamadoJoeData
from .conftest import SAMPLE_REPORTED, DEVICE_ID


def _make_coordinator(reported=None, outage=False):
    coord = MagicMock()
    coord.data = KamadoJoeData(reported or SAMPLE_REPORTED, 0)
    coord.power_outage_detected = outage
    coord._last_target = coord.data.target_temperature
    return coord


class TestPowerSensor:
    def test_on_when_powered(self):
        sensor = KamadoJoePowerSensor(_make_coordinator(), DEVICE_ID)
        assert sensor.is_on is True

    def test_off_when_not_powered(self):
        reported = {**SAMPLE_REPORTED, "pwrOn": False}
        sensor = KamadoJoePowerSensor(_make_coordinator(reported), DEVICE_ID)
        assert sensor.is_on is False

    def test_none_when_no_data(self):
        coord = MagicMock()
        coord.data = None
        sensor = KamadoJoePowerSensor(coord, DEVICE_ID)
        assert sensor.is_on is None

    def test_unique_id(self):
        sensor = KamadoJoePowerSensor(_make_coordinator(), DEVICE_ID)
        assert sensor.unique_id == f"{DEVICE_ID}_power"

    def test_device_info_uses_device_id(self):
        sensor = KamadoJoePowerSensor(_make_coordinator(), DEVICE_ID)
        assert (("kamado_joe", DEVICE_ID),) == tuple(sensor.device_info["identifiers"])


class TestHeatingSensor:
    def test_on_when_heating(self):
        sensor = KamadoJoeHeatingSensor(_make_coordinator(), DEVICE_ID)
        assert sensor.is_on is True

    def test_off_when_not_heating(self):
        reported = {**SAMPLE_REPORTED, "heat": {
            "t1": {"heating": False}, "t2": {"heating": False},
        }}
        sensor = KamadoJoeHeatingSensor(_make_coordinator(reported), DEVICE_ID)
        assert sensor.is_on is False

    def test_none_when_no_data(self):
        coord = MagicMock()
        coord.data = None
        sensor = KamadoJoeHeatingSensor(coord, DEVICE_ID)
        assert sensor.is_on is None

    def test_extra_attrs_include_target(self):
        sensor = KamadoJoeHeatingSensor(_make_coordinator(), DEVICE_ID)
        attrs = sensor.extra_state_attributes
        assert attrs["target_temperature"] == "400.0°F"
        assert "t2" in attrs["active_elements"]

    def test_extra_attrs_current_temp(self):
        sensor = KamadoJoeHeatingSensor(_make_coordinator(), DEVICE_ID)
        assert sensor.extra_state_attributes["current_temperature"] == "350.0°F"

    def test_unique_id(self):
        sensor = KamadoJoeHeatingSensor(_make_coordinator(), DEVICE_ID)
        assert sensor.unique_id == f"{DEVICE_ID}_heating"


class TestPowerOutageSensor:
    def test_off_normally(self):
        sensor = KamadoJoePowerOutageSensor(_make_coordinator(outage=False), DEVICE_ID)
        assert sensor.is_on is False

    def test_on_when_outage_detected(self):
        sensor = KamadoJoePowerOutageSensor(_make_coordinator(outage=True), DEVICE_ID)
        assert sensor.is_on is True

    def test_extra_attrs_include_last_temp(self):
        sensor = KamadoJoePowerOutageSensor(_make_coordinator(outage=True), DEVICE_ID)
        attrs = sensor.extra_state_attributes
        assert attrs["last_temperature"] == "350.0°F"
        assert attrs["last_target"] == "400.0°F"

    def test_extra_attrs_grill_powered_on(self):
        sensor = KamadoJoePowerOutageSensor(_make_coordinator(outage=False), DEVICE_ID)
        assert sensor.extra_state_attributes["grill_powered_on"] is True

    def test_unique_id(self):
        sensor = KamadoJoePowerOutageSensor(_make_coordinator(), DEVICE_ID)
        assert sensor.unique_id == f"{DEVICE_ID}_power_outage"
