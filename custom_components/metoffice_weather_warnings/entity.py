from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MET_OFFICE_WARNINGS_URL, REGIONS
from .coordinator import MetOfficeWarningsCoordinator


class MetOfficeWarningsEntity(CoordinatorEntity[MetOfficeWarningsCoordinator]):
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MetOfficeWarningsCoordinator,
        entity_key: str,
    ) -> None:
        super().__init__(coordinator)
        # Config-entry ID is stable for the lifetime of this configured service and
        # is an accepted unique-ID source when the upstream service has no device ID.
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{entity_key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry.entry_id)},
            name=f"Met Office Weather Warnings — {REGIONS.get(coordinator.region, coordinator.region)}",
            manufacturer="Met Office",
            model="Severe Weather Warnings RSS",
            configuration_url=MET_OFFICE_WARNINGS_URL,
        )
