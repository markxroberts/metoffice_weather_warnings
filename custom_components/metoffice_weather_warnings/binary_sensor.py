from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import ATTRIBUTION
from .coordinator import MetOfficeWarningsCoordinator
from .entity import MetOfficeWarningsEntity

DESCRIPTIONS = (
    BinarySensorEntityDescription(key="active", translation_key="active", icon="mdi:alert"),
    BinarySensorEntityDescription(key="upcoming", translation_key="upcoming", icon="mdi:alert-outline"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[MetOfficeWarningsCoordinator],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities(MetOfficeWarningsBinarySensor(entry.runtime_data, description) for description in DESCRIPTIONS)


class MetOfficeWarningsBinarySensor(MetOfficeWarningsEntity, BinarySensorEntity):
    _attr_attribution = ATTRIBUTION

    def __init__(
        self,
        coordinator: MetOfficeWarningsCoordinator,
        description: BinarySensorEntityDescription,
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        now = dt_util.utcnow()
        if self.entity_description.key == "active":
            return any(warning.start <= now < warning.end for warning in self.coordinator.data.warnings)
        return any(warning.start > now for warning in self.coordinator.data.warnings)
