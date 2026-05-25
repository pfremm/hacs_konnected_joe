"""Binary sensors for Kamado Joe: power, heating, and power outage."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_DEVICE_ID, DOMAIN
from .coordinator import KamadoJoeCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: KamadoJoeCoordinator = hass.data[DOMAIN][entry.entry_id]
    device_id = entry.data[CONF_DEVICE_ID]
    async_add_entities(
        [
            KamadoJoePowerSensor(coordinator, device_id),
            KamadoJoeHeatingSensor(coordinator, device_id),
            KamadoJoePowerOutageSensor(coordinator, device_id),
        ]
    )


class _KamadoJoeBaseSensor(CoordinatorEntity[KamadoJoeCoordinator], BinarySensorEntity):
    """Shared base for all Kamado Joe binary sensors."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: KamadoJoeCoordinator, device_id: str) -> None:
        super().__init__(coordinator)
        self._device_id = device_id

    @property
    def device_info(self) -> dict:
        return {
            "identifiers": {(DOMAIN, self._device_id)},
            "name": f"Kamado Joe ({self._device_id})",
            "manufacturer": "Kamado Joe",
        }


class KamadoJoePowerSensor(_KamadoJoeBaseSensor):
    """True when the grill is powered on."""

    _attr_device_class = BinarySensorDeviceClass.POWER
    _attr_name = "Power"

    def __init__(self, coordinator: KamadoJoeCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_power"

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.data.power_on if self.coordinator.data else None


class KamadoJoeHeatingSensor(_KamadoJoeBaseSensor):
    """True when one or more heating elements are actively heating."""

    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_name = "Heating"

    def __init__(self, coordinator: KamadoJoeCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_heating"

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.data.is_heating if self.coordinator.data else None

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data
        if not data:
            return {}
        unit = "°F" if data.is_fahrenheit else "°C"
        return {
            "current_temperature": (
                f"{data.main_temperature}{unit}" if data.main_temperature is not None else None
            ),
            "target_temperature": (
                f"{data.target_temperature}{unit}" if data.target_temperature is not None else None
            ),
            "active_elements": [
                k for k, v in data.heating_elements.items() if v["heating"]
            ],
        }


class KamadoJoePowerOutageSensor(_KamadoJoeBaseSensor):
    """
    True when the grill lost power before reaching its target temperature.

    Latches on until the grill is powered back on, so a brief outage that
    the user might miss is still surfaced in the UI.  Build an HA automation
    against this sensor to send a push notification.
    """

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_name = "Power Outage"

    def __init__(self, coordinator: KamadoJoeCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_power_outage"

    @property
    def is_on(self) -> bool:
        return self.coordinator.power_outage_detected

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data
        if not data:
            return {}
        unit = "°F" if data.is_fahrenheit else "°C"
        return {
            "last_temperature": (
                f"{data.main_temperature}{unit}" if data.main_temperature is not None else None
            ),
            "last_target": (
                f"{self.coordinator._last_target}{unit}"
                if self.coordinator._last_target is not None
                else None
            ),
            "grill_powered_on": data.power_on,
        }
