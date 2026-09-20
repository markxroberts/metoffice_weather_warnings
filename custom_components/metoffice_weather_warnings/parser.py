from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from hashlib import sha256
from html import unescape
from html.parser import HTMLParser
import re
from typing import Iterable
from zoneinfo import ZoneInfo
from xml.etree import ElementTree as ET

from .const import DEFAULT_SEVERITIES, DEFAULT_WEATHER_TYPES
from .models import WeatherWarning


@dataclass(slots=True)
class ParseDiagnostics:
    """Diagnostics from one feed parse without exposing feed internals as entities."""

    total_items: int = 0
    warning_like_items: int = 0
    filtered_items: int = 0
    parse_failures: int = 0


_WARNING_LIKE_RE = re.compile(r"\b(yellow|amber|red)\s+warning\s+of\b", re.I)
_SEVERITY_RE = re.compile(r"\b(yellow|amber|red)\b", re.I)
_TYPE_RE = re.compile(
    r"\b(extreme\s+heat|thunderstorms?|lightning|rain|wind|snow|ice|fog)\b", re.I
)
_BETWEEN_RE = re.compile(
    r"Between\s+(?P<start>.+?)\s+and\s+(?P<end>.+?)(?:[\r\n<]|$)", re.I | re.S
)
_VALID_RE = re.compile(
    r"Valid\s+(?:from|between)\s+(?P<start>.+?)\s+(?:until|and)\s+(?P<end>.+?)(?:[\r\n<]|$)",
    re.I | re.S,
)
_ISO_RANGE_RE = re.compile(
    r"(?P<start>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:?\d{2}))"
    r".*?"
    r"(?P<end>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:?\d{2}))",
    re.S,
)

# Current Met Office regional RSS titles use this canonical form, e.g.
# "Amber warning of extreme heat affecting East Midlands: Derby, ... Nottinghamshire
# valid from 0900 Thu 13 Aug to 2259 Thu 13 Aug".  Parse it explicitly before
# falling back to the more generic extractors below.
_RSS_TITLE_RE = re.compile(
    r"^(?P<severity>yellow|amber|red)\s+warning\s+of\s+"
    r"(?P<weather_type>extreme\s+heat|thunderstorms?|lightning|rain|wind|snow|ice|fog)\s+"
    r"affecting\s+(?P<region>[^:]+):\s*(?P<areas>.+?)\s+"
    r"valid\s+from\s+(?P<start_time>\d{4}|\d{1,2}:\d{2})\s+"
    r"(?:(?P<start_weekday>[A-Za-z]{3,9})\s+)?(?P<start_date>\d{1,2})\s+(?P<start_month>[A-Za-z]{3,9})"
    r"(?:\s+(?P<start_year>\d{4}))?\s+to\s+"
    r"(?P<end_time>\d{4}|\d{1,2}:\d{2})\s+"
    r"(?:(?P<end_weekday>[A-Za-z]{3,9})\s+)?(?P<end_date>\d{1,2})\s+(?P<end_month>[A-Za-z]{3,9})"
    r"(?:\s+(?P<end_year>\d{4}))?\s*$",
    re.I | re.S,
)

_RSS_VALID_RE = re.compile(
    r"\bvalid\s+from\s+"
    r"(?P<start_time>\d{4}|\d{1,2}:\d{2})\s+"
    r"(?P<start_day>[A-Za-z]{3,9})?\s*"
    r"(?P<start_date>\d{1,2})\s+"
    r"(?P<start_month>[A-Za-z]{3,9})"
    r"(?:\s+(?P<start_year>\d{4}))?\s+"
    r"(?:to|until)\s+"
    r"(?P<end_time>\d{4}|\d{1,2}:\d{2})\s+"
    r"(?P<end_day>[A-Za-z]{3,9})?\s*"
    r"(?P<end_date>\d{1,2})\s+"
    r"(?P<end_month>[A-Za-z]{3,9})"
    r"(?:\s+(?P<end_year>\d{4}))?\b",
    re.I,
)


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.parts.append(data.strip())


def _strip_html(value: str) -> str:
    parser = _TextExtractor()
    try:
        parser.feed(unescape(value or ""))
        text = "\n".join(parser.parts)
    except Exception:
        text = unescape(value or "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _children(element: ET.Element, names: Iterable[str]) -> list[ET.Element]:
    wanted = {name.lower() for name in names}
    return [child for child in list(element) if _local_name(child.tag) in wanted]


def _first_text(element: ET.Element, *names: str) -> str:
    for child in element.iter():
        if child is element:
            continue
        if _local_name(child.tag) in {name.lower() for name in names}:
            if child.text and child.text.strip():
                return child.text.strip()
    return ""


def _first_link(element: ET.Element) -> str | None:
    for child in element.iter():
        if _local_name(child.tag) != "link":
            continue
        href = child.attrib.get("href")
        if href:
            rel = child.attrib.get("rel", "alternate")
            if rel in {"alternate", "related"}:
                return href
        if child.text and child.text.strip().startswith("http"):
            return child.text.strip()
    return None


def _parse_feed_datetime(value: str) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    try:
        result = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return result if result.tzinfo else result.replace(tzinfo=timezone.utc)
    except ValueError:
        pass
    try:
        result = parsedate_to_datetime(text)
        return result if result.tzinfo else result.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None


def _normalise_human_datetime(value: str) -> datetime | None:
    text = _strip_html(value)
    text = re.sub(r"\s+", " ", text).strip(" .;,-")
    text = re.sub(r"\((UTC(?:[+-]\d{1,2})?|GMT|BST)\)", r"\1", text, flags=re.I)
    text = re.sub(r"\b(on)\b", "", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip()

    # Met Office warning clocks labelled GMT/BST are UK civil times.  Attach
    # Europe/London rather than a fixed offset so the result remains correct
    # around daylight-saving transitions as well as during normal winter/summer.
    uk_label = re.search(r"\b(GMT|BST)\b", text, re.I)
    if uk_label:
        stripped = re.sub(r"\b(?:GMT|BST)\b", "", text, flags=re.I)
        stripped = re.sub(r"\s+", " ", stripped).strip()
        for pattern in (
            "%H:%M %a %d %b %Y", "%H:%M %a %d %B %Y",
            "%H:%M %d %b %Y", "%H:%M %d %B %Y",
        ):
            try:
                return datetime.strptime(stripped, pattern).replace(tzinfo=ZoneInfo("Europe/London"))
            except ValueError:
                continue

    iso = _parse_feed_datetime(text)
    if iso:
        return iso

    patterns = [
        "%H:%M UTC on %a %d %b %Y",
        "%H:%M UTC on %a %d %B %Y",
        "%H:%M UTC%z %a %d %b %Y",
        "%H:%M UTC%z %a %d %B %Y",
        "%H:%M %a %d %b %Y",
        "%H:%M %a %d %B %Y",
        "%H:%M on %a %d %b %Y",
        "%H:%M on %a %d %B %Y",
        "%H:%M %Z %a %d %b %Y",
        "%H:%M %Z %a %d %B %Y",
    ]

    offset_match = re.search(r"\bUTC([+-])(\d{1,2})(?::?(\d{2}))?\b", text, re.I)
    if offset_match:
        sign = 1 if offset_match.group(1) == "+" else -1
        hours = int(offset_match.group(2))
        minutes = int(offset_match.group(3) or 0)
        tz = timezone(sign * timedelta(hours=hours, minutes=minutes))
        stripped = re.sub(r"\bUTC[+-]\d{1,2}(?::?\d{2})?\b", "", text, flags=re.I)
        stripped = re.sub(r"\s+", " ", stripped).strip()
        for pattern in ("%H:%M %a %d %b %Y", "%H:%M %a %d %B %Y"):
            try:
                return datetime.strptime(stripped, pattern).replace(tzinfo=tz)
            except ValueError:
                continue

    for pattern in patterns:
        try:
            dt = datetime.strptime(text, pattern)
            if dt.tzinfo is None:
                # Unqualified human-readable Met Office warning times are UK local
                # civil time, not necessarily UTC.
                dt = dt.replace(tzinfo=ZoneInfo("Europe/London"))
            return dt
        except ValueError:
            continue
    return None


def _parse_rss_compact_datetime(
    time_text: str,
    day: str,
    month: str,
    year: int,
) -> datetime | None:
    clean_time = time_text.replace(":", "")
    if len(clean_time) != 4 or not clean_time.isdigit():
        return None
    value = f"{clean_time} {day} {month} {year}"
    for pattern in ("%H%M %d %b %Y", "%H%M %d %B %Y"):
        try:
            # Met Office regional RSS validity clock times are UTC. Home Assistant
            # will convert these timezone-aware values to the configured local timezone
            # (Europe/London for a UK installation), giving BST during summer.
            return datetime.strptime(value, pattern).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None



def _parse_canonical_rss_title(
    title: str,
    *,
    reference: datetime | None,
) -> tuple[str, str, tuple[str, ...], datetime | None, datetime | None] | None:
    compact = re.sub(r"\s+", " ", title).strip()
    match = _RSS_TITLE_RE.match(compact)
    if not match:
        return None

    ref = reference or datetime.now(timezone.utc)
    start_year = int(match.group("start_year") or ref.year)
    end_year = int(match.group("end_year") or start_year)
    start = _parse_rss_compact_datetime(
        match.group("start_time"), match.group("start_date"), match.group("start_month"), start_year
    )
    end = _parse_rss_compact_datetime(
        match.group("end_time"), match.group("end_date"), match.group("end_month"), end_year
    )
    if start and end and end <= start and not match.group("end_year"):
        end = end.replace(year=end.year + 1)

    weather_type = match.group("weather_type").lower()
    if weather_type == "thunderstorms":
        weather_type = "thunderstorm"
    areas = tuple(
        part.strip()
        for part in re.split(r"\s*,\s*", match.group("areas"))
        if part.strip()
    )
    return match.group("severity").lower(), weather_type, areas, start, end

def _extract_validity(
    text: str,
    *,
    reference: datetime | None = None,
) -> tuple[datetime | None, datetime | None]:
    iso = _ISO_RANGE_RE.search(text)
    if iso:
        return _parse_feed_datetime(iso.group("start")), _parse_feed_datetime(iso.group("end"))

    rss_match = _RSS_VALID_RE.search(re.sub(r"\s+", " ", text))
    if rss_match:
        ref = reference or datetime.now(timezone.utc)
        start_year = int(rss_match.group("start_year") or ref.year)
        end_year = int(rss_match.group("end_year") or start_year)
        start = _parse_rss_compact_datetime(
            rss_match.group("start_time"),
            rss_match.group("start_date"),
            rss_match.group("start_month"),
            start_year,
        )
        end = _parse_rss_compact_datetime(
            rss_match.group("end_time"),
            rss_match.group("end_date"),
            rss_match.group("end_month"),
            end_year,
        )
        # Handle a warning spanning New Year when the RSS title omits years.
        if start and end and end <= start and not rss_match.group("end_year"):
            end = end.replace(year=end.year + 1)
        if start and end:
            return start, end

    for pattern in (_BETWEEN_RE, _VALID_RE):
        match = pattern.search(text)
        if match:
            start = _normalise_human_datetime(match.group("start"))
            end = _normalise_human_datetime(match.group("end"))
            if start and end:
                return start, end

    # Some feed HTML flattens the period onto a single line with labels nearby.
    compact = re.sub(r"\s+", " ", text)
    match = re.search(
        r"Between\s+(\d{1,2}:\d{2}.*?\d{4})\s+and\s+(\d{1,2}:\d{2}.*?\d{4})",
        compact,
        re.I,
    )
    if match:
        return _normalise_human_datetime(match.group(1)), _normalise_human_datetime(match.group(2))
    return None, None


def _extract_summary(text: str, fallback: str) -> str:
    patterns = [
        re.compile(r"Headline\s*[:\-]?\s*(.+?)(?:\n\s*(?:What to expect|Further Details|Issued|Updated)\b|$)", re.I | re.S),
        re.compile(r"Summary\s*[:\-]?\s*(.+?)(?:\n\s*[A-Z][A-Za-z ]+\s*[:\-]|$)", re.I | re.S),
    ]
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            return re.sub(r"\s+", " ", match.group(1)).strip()
    return re.sub(r"\s+", " ", fallback).strip()


def _stable_uid(raw_uid: str, link: str | None, title: str, start: datetime, end: datetime) -> str:
    source = raw_uid.strip() or (link or "")
    if not source:
        source = f"{title}|{start.isoformat()}|{end.isoformat()}"
    return sha256(source.encode("utf-8")).hexdigest()[:24]


def parse_warnings(
    xml_text: str,
    *,
    area_filters: list[str] | tuple[str, ...] = (),
    severities: list[str] | tuple[str, ...] = tuple(DEFAULT_SEVERITIES),
    weather_types: list[str] | tuple[str, ...] = tuple(DEFAULT_WEATHER_TYPES),
    diagnostics: ParseDiagnostics | None = None,
) -> list[WeatherWarning]:
    root = ET.fromstring(xml_text)
    items = [el for el in root.iter() if _local_name(el.tag) in {"item", "entry"}]
    if diagnostics is not None:
        diagnostics.total_items = len(items)

    severity_filter = {v.lower() for v in severities}
    weather_filter = {v.lower() for v in weather_types}
    area_filter = [v.strip() for v in area_filters if v.strip()]

    warnings: list[WeatherWarning] = []
    for item in items:
        title = _strip_html(_first_text(item, "title"))
        raw_summary = _first_text(item, "summary", "description")
        raw_content = _first_text(item, "content", "encoded")
        summary_text = _strip_html(raw_summary)
        content_text = _strip_html(raw_content)
        combined = "\n".join(part for part in (title, summary_text, content_text) if part)
        if not combined:
            continue

        warning_like = bool(_WARNING_LIKE_RE.search(title or combined))
        if warning_like and diagnostics is not None:
            diagnostics.warning_like_items += 1

        published = _parse_feed_datetime(_first_text(item, "published", "pubdate"))
        updated = _parse_feed_datetime(_first_text(item, "updated", "lastbuilddate"))

        canonical = _parse_canonical_rss_title(title, reference=updated or published)
        feed_areas: tuple[str, ...] = ()
        if canonical:
            severity, weather_type, feed_areas, start, end = canonical
        else:
            sev_match = _SEVERITY_RE.search(combined)
            type_match = _TYPE_RE.search(combined)
            severity = sev_match.group(1).lower() if sev_match else "unknown"
            weather_type = type_match.group(1).lower() if type_match else "unknown"
            if weather_type == "thunderstorms":
                weather_type = "thunderstorm"
            start, end = _extract_validity(combined, reference=updated or published)

        if severity not in severity_filter or weather_type not in weather_filter:
            if diagnostics is not None:
                diagnostics.filtered_items += 1
            continue
        if start is None or end is None or end <= start:
            # Without a valid interval it cannot safely become a CalendarEvent.
            # Only count this as a parser failure when the item clearly looks like
            # a Met Office colour warning; unrelated RSS items are normal.
            if warning_like and diagnostics is not None:
                diagnostics.parse_failures += 1
            continue

        matched_areas: tuple[str, ...] = ()
        if area_filter:
            # Prefer the authority list encoded in the canonical RSS title.
            # Fall back to text matching for older feed formats.
            haystacks = feed_areas if feed_areas else (combined,)
            matched = []
            for area in area_filter:
                if any(re.search(rf"\b{re.escape(area)}\b", value, re.I) for value in haystacks):
                    matched.append(area)
            if not matched:
                if diagnostics is not None:
                    diagnostics.filtered_items += 1
                continue
            matched_areas = tuple(matched)

        link = _first_link(item)
        raw_uid = _first_text(item, "id", "guid")
        description = content_text or summary_text
        human_summary = _extract_summary(description, summary_text or title)
        uid = _stable_uid(raw_uid, link, title, start, end)

        warnings.append(
            WeatherWarning(
                uid=uid,
                title=title or f"{severity.title()} warning of {weather_type}",
                severity=severity,
                weather_type=weather_type,
                start=start,
                end=end,
                summary=human_summary,
                description=description,
                link=link,
                published=published,
                updated=updated,
                matched_areas=matched_areas,
            )
        )

    warnings.sort(key=lambda warning: (warning.start, warning.end, warning.uid))
    return warnings
