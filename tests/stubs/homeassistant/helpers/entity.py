class Entity:
    _attr_unique_id = None
    _attr_name = None
    _attr_has_entity_name = False

    @property
    def unique_id(self):
        return self._attr_unique_id
