"""Temperature sensor for Kamado Joe."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
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
    async_add_entities([KamadoJoeTemperatureSensor(coordinator, entry.data[CONF_DEVICE_ID])])


class KamadoJoeTemperatureSensor(CoordinatorEntity[KamadoJoeCoordinator], SensorEntity):
    """
    Grill temperature.

    Reports the current grill temperature whenever the grill is powered on.
    Returns None (unavailable) when the grill is off.
    """

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_has_entity_name = True
    _attr_name = "Temperature"

    def __init__(self, coordinator: KamadoJoeCoordinator, device_id: str) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_unique_id = f"{device_id}_temperature"

    @property
    def native_unit_of_measurement(self) -> str:
        if self.coordinator.data and not self.coordinator.data.is_fahrenheit:
            return UnitOfTemperature.CELSIUS
        return UnitOfTemperature.FAHRENHEIT

    @property
    def native_value(self) -> float | None:
        data = self.coordinator.data
        if data is None or not data.power_on:
            return None
        return data.main_temperature

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data
        if not data:
            return {}
        return {
            "is_heating": data.is_heating,
            "target_temperature": data.target_temperature,
            "heating_elements": {
                k: {"heating": v["heating"], "intensity": v["intensity"], "target": v["target"]}
                for k, v in data.heating_elements.items()
            },
            "ssid": data.ssid,
            "signal_strength_dbm": data.rssi,
            "errors": data.errors,
        }

    @property
    def device_info(self) -> dict:
        return {
            "identifiers": {(DOMAIN, self._device_id)},
            "name": f"Kamado Joe ({self._device_id})",
            "manufacturer": "Kamado Joe",
        }
