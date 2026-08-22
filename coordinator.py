from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging

from aiohttp import ClientError
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CONF_AREA_FILTERS,
    CONF_REGION,
    CONF_SCAN_INTERVAL,
    CONF_SEVERITIES,
    CONF_WEATHER_TYPES,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SEVERITIES,
    DEFAULT_WEATHER_TYPES,
    DOMAIN,
    RSS_URL,
)
from .models import WeatherWarning
from .parser import ParseDiagnostics, parse_warnings

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class WarningData:
    warnings: list[WeatherWarning]


class MetOfficeWarningsCoordinator(DataUpdateCoordinator[WarningData]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry = entry
        self._first_refresh = True
        self._previous: dict[str, WeatherWarning] = {}
        minutes = int(entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=timedelta(minutes=minutes),
        )

    @property
    def region(self) -> str:
        return str(self.entry.data[CONF_REGION])

    async def _async_update_data(self) -> WarningData:
        session = async_get_clientsession(self.hass)
        url = RSS_URL.format(region=self.region)
        try:
            async with session.get(
                url,
                headers={
                    "Accept": "application/atom+xml, application/rss+xml, application/xml, text/xml;q=0.9, */*;q=0.1",
                    "User-Agent": "Home Assistant Met Office Weather Warnings custom integration",
                },
                timeout=20,
            ) as response:
                response.raise_for_status()
                text = await response.text()
        except (ClientError, TimeoutError) as err:
            raise UpdateFailed(f"Unable to retrieve Met Office warning feed: {err}") from err

        area_filters = [
            value.strip()
            for value in str(self.entry.options.get(CONF_AREA_FILTERS, self.entry.data.get(CONF_AREA_FILTERS, ""))).split(",")
            if value.strip()
        ]
        severities = list(self.entry.options.get(CONF_SEVERITIES, DEFAULT_SEVERITIES))
        weather_types = list(self.entry.options.get(CONF_WEATHER_TYPES, DEFAULT_WEATHER_TYPES))

        diagnostics = ParseDiagnostics()
        try:
            warnings = parse_warnings(
                text,
                area_filters=area_filters,
                severities=severities,
                weather_types=weather_types,
                diagnostics=diagnostics,
            )
        except Exception as err:
            raise UpdateFailed(f"Unable to parse Met Office warning feed: {err}") from err

        _LOGGER.debug(
            "Met Office %s feed refresh: %d bytes received, %d item(s), "
            "%d warning-like item(s), %d filtered, %d parse failure(s), "
            "%d warning(s) accepted; area_filters=%s severities=%s weather_types=%s",
            self.region,
            len(text),
            diagnostics.total_items,
            diagnostics.warning_like_items,
            diagnostics.filtered_items,
            diagnostics.parse_failures,
            len(warnings),
            area_filters,
            severities,
            weather_types,
        )
        if diagnostics.parse_failures:
            _LOGGER.warning(
                "Met Office %s feed contains %d recognised warning item(s) that could not "
                "be parsed into a valid warning period. This may indicate a Met Office "
                "feed format change; enable debug logging for %s for refresh diagnostics.",
                self.region,
                diagnostics.parse_failures,
                DOMAIN,
            )

        current = {warning.uid: warning for warning in warnings}
        if not self._first_refresh:
            self._fire_change_events(self._previous, current)
        self._previous = current
        self._first_refresh = False
        return WarningData(warnings=warnings)

    def _fire_change_events(
        self,
        previous: dict[str, WeatherWarning],
        current: dict[str, WeatherWarning],
    ) -> None:
        now = dt_util.utcnow()

        for uid, warning in current.items():
            old = previous.get(uid)
            if old is None:
                self._fire_event("issued", warning)
                continue
            if old.fingerprint != warning.fingerprint:
                self._fire_event("updated", warning)
            if old.start > now >= warning.start and warning.end > now:
                self._fire_event("became_active", warning)

        for uid, warning in previous.items():
            if uid in current:
                continue
            action = "expired" if warning.end <= now else "cancelled"
            self._fire_event(action, warning)

    def _fire_event(self, action: str, warning: WeatherWarning) -> None:
        self.hass.bus.async_fire(
            f"{DOMAIN}_warning",
            {
                "action": action,
                "warning_id": warning.uid,
                "severity": warning.severity,
                "weather_type": warning.weather_type,
                "start": warning.start.isoformat(),
                "end": warning.end.isoformat(),
                "summary": warning.summary,
                "link": warning.link,
            },
        )
