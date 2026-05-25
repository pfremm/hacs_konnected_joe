from homeassistant.helpers.entity import Entity

class SensorDeviceClass:
    TEMPERATURE = "temperature"

class SensorStateClass:
    MEASUREMENT = "measurement"

class SensorEntity(Entity):
    _attr_device_class = None
    _attr_state_class = None
    _attr_native_unit_of_measurement = None

    @property
    def native_value(self):
        return None

    @property
    def native_unit_of_measurement(self):
        return self._attr_native_unit_of_measurement

    @property
    def extra_state_attributes(self):
        return {}
