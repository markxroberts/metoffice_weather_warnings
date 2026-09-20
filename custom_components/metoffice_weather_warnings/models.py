from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class WeatherWarning:
    uid: str
    title: str
    severity: str
    weather_type: str
    start: datetime
    end: datetime
    summary: str
    description: str
    link: str | None
    published: datetime | None = None
    updated: datetime | None = None
    matched_areas: tuple[str, ...] = ()
    further_details: str | None = None
    detail_updated: datetime | None = None
    update_reason: str | None = None

    @property
    def fingerprint(self) -> tuple[object, ...]:
        return (
            self.title,
            self.severity,
            self.weather_type,
            self.start,
            self.end,
            self.summary,
            self.description,
            self.link,
            self.further_details,
            self.detail_updated,
            self.update_reason,
        )
