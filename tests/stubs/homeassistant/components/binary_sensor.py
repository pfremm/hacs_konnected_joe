from homeassistant.helpers.entity import Entity

class BinarySensorDeviceClass:
    POWER = "power"
    RUNNING = "running"
    PROBLEM = "problem"
    HEAT = "heat"

class BinarySensorEntity(Entity):
    _attr_device_class = None

    @property
    def is_on(self):
        return None

    @property
    def extra_state_attributes(self):
        return {}
