from __future__ import annotations

from datetime import datetime

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import ATTRIBUTION, DOMAIN, REGIONS
from .coordinator import MetOfficeWarningsCoordinator
from .entity import MetOfficeWarningsEntity
from .models import WeatherWarning


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[MetOfficeWarningsCoordinator],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([MetOfficeWarningsCalendar(entry.runtime_data)])


class MetOfficeWarningsCalendar(MetOfficeWarningsEntity, CalendarEntity):
    _attr_translation_key = "warnings"
    _attr_icon = "mdi:weather-lightning-rainy"
    _attr_attribution = ATTRIBUTION
    _attr_initial_color = "#f5a623"

    def __init__(self, coordinator: MetOfficeWarningsCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_calendar"

    @property
    def event(self) -> CalendarEvent | None:
        now = dt_util.utcnow()
        candidates = [warning for warning in self.coordinator.data.warnings if warning.end > now]
        if not candidates:
            return None
        active = [warning for warning in candidates if warning.start <= now < warning.end]
        warning = min(active or candidates, key=lambda item: (item.start, item.end))
        return self._to_event(warning)

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        return [
            self._to_event(warning)
            for warning in self.coordinator.data.warnings
            if warning.start < end_date and warning.end > start_date
        ]

    def _to_event(self, warning: WeatherWarning) -> CalendarEvent:
        description_parts = [
            warning.summary,
            "",
            f"Severity: {warning.severity.title()}",
            f"Weather type: {warning.weather_type.title()}",
            f"Region: {REGIONS.get(self.coordinator.region, self.coordinator.region)}",
        ]
        if warning.matched_areas:
            description_parts.append(f"Matched area: {', '.join(warning.matched_areas)}")
        if warning.link:
            description_parts.extend(["", f"Met Office: {warning.link}"])
        return CalendarEvent(
            start=warning.start,
            end=warning.end,
            summary=f"{warning.severity.title()} warning of {warning.weather_type}",
            location=REGIONS.get(self.coordinator.region, self.coordinator.region),
            description="\n".join(description_parts),
            uid=warning.uid,
        )
