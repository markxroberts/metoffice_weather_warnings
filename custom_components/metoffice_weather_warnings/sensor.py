from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import ATTRIBUTION, SEVERITY_RANK
from .coordinator import MetOfficeWarningsCoordinator
from .entity import MetOfficeWarningsEntity
from .models import WeatherWarning


@dataclass(frozen=True, kw_only=True)
class WarningSensorDescription(SensorEntityDescription):
    kind: str


DESCRIPTIONS = (
    WarningSensorDescription(key="active_count", translation_key="active_count", kind="active_count", icon="mdi:counter"),
    WarningSensorDescription(key="upcoming_count", translation_key="upcoming_count", kind="upcoming_count", icon="mdi:counter"),
    WarningSensorDescription(key="highest_level", translation_key="highest_level", kind="highest_level", icon="mdi:alert-decagram"),
    WarningSensorDescription(key="current_warning", translation_key="current_warning", kind="current_warning", icon="mdi:weather-cloudy-alert"),
    WarningSensorDescription(key="next_warning", translation_key="next_warning", kind="next_warning", icon="mdi:weather-cloudy-alert"),
    WarningSensorDescription(key="next_start", translation_key="next_start", kind="next_start", device_class=SensorDeviceClass.TIMESTAMP),
    WarningSensorDescription(key="next_end", translation_key="next_end", kind="next_end", device_class=SensorDeviceClass.TIMESTAMP),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[MetOfficeWarningsCoordinator],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities(MetOfficeWarningsSensor(entry.runtime_data, description) for description in DESCRIPTIONS)


class MetOfficeWarningsSensor(MetOfficeWarningsEntity, SensorEntity):
    _attr_attribution = ATTRIBUTION

    def __init__(self, coordinator: MetOfficeWarningsCoordinator, description: WarningSensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    def _active(self) -> list[WeatherWarning]:
        now = dt_util.utcnow()
        return [warning for warning in self.coordinator.data.warnings if warning.start <= now < warning.end]

    def _upcoming(self) -> list[WeatherWarning]:
        now = dt_util.utcnow()
        return [warning for warning in self.coordinator.data.warnings if warning.start > now]

    def _current(self) -> WeatherWarning | None:
        active = self._active()
        if not active:
            return None
        return max(active, key=lambda item: (SEVERITY_RANK.get(item.severity, 0), -item.start.timestamp()))

    def _next(self) -> WeatherWarning | None:
        upcoming = self._upcoming()
        return min(upcoming, key=lambda item: item.start) if upcoming else None

    @property
    def native_value(self) -> str | int | datetime | None:
        kind = self.entity_description.kind
        active = self._active()
        upcoming = self._upcoming()
        warning = self._current() if kind == "current_warning" else self._next()
        if kind == "active_count":
            return len(active)
        if kind == "upcoming_count":
            return len(upcoming)
        if kind == "highest_level":
            if not active:
                return "none"
            return max(active, key=lambda item: SEVERITY_RANK.get(item.severity, 0)).severity
        if warning is None:
            return None
        if kind in {"current_warning", "next_warning"}:
            return f"{warning.severity.title()} {warning.weather_type}"
        if kind == "next_start":
            return warning.start
        if kind == "next_end":
            return warning.end
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.kind not in {"current_warning", "next_warning"}:
            return None
        warning = self._current() if self.entity_description.kind == "current_warning" else self._next()
        if warning is None:
            return None
        return {
            "warning_id": warning.uid,
            "severity": warning.severity,
            "weather_type": warning.weather_type,
            "summary": warning.summary,
            "further_details": warning.further_details,
            "last_updated": warning.detail_updated.isoformat() if warning.detail_updated else None,
            "update_reason": warning.update_reason,
            "start": warning.start.isoformat(),
            "end": warning.end.isoformat(),
            "matched_areas": list(warning.matched_areas),
            "link": warning.link,
        }
