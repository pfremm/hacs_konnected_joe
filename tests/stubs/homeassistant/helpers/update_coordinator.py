class _GenericMeta(type):
    def __getitem__(cls, item):
        return cls

class DataUpdateCoordinator(metaclass=_GenericMeta):
    def __init__(self, hass, logger, *, name, update_interval):
        self.hass = hass
        self.logger = logger
        self.name = name
        self.update_interval = update_interval
        self.data = None

class UpdateFailed(Exception):
    pass

class CoordinatorEntity(metaclass=_GenericMeta):
    def __init__(self, coordinator):
        self.coordinator = coordinator
