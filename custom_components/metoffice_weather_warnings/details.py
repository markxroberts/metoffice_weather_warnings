from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from html import unescape
from html.parser import HTMLParser
import re


@dataclass(frozen=True, slots=True)
class WarningDetails:
    further_details: str | None = None
    last_updated: datetime | None = None
    update_reason: str | None = None


class _PageTextExtractor(HTMLParser):
    """Extract readable text while preserving useful block boundaries."""

    _BLOCK_TAGS = {
        "br",
        "p",
        "div",
        "section",
        "article",
        "h1",
        "h2",
        "h3",
        "h4",
        "li",
        "ul",
        "ol",
    }

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in self._BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self._BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        text = unescape(data)
        if text.strip():
            self.parts.append(text.strip())

    def text(self) -> str:
        value = " ".join(self.parts)
        value = re.sub(r"[ \t]+", " ", value)
        value = re.sub(r" *\n *", "\n", value)
        value = re.sub(r"\n{3,}", "\n\n", value)
        return value.strip()


def _normalise_paragraph(text: str) -> str | None:
    value = re.sub(r"\s+", " ", text).strip(" \n\t:-")
    return value or None


def _parse_last_updated(value: str) -> datetime | None:
    """Parse Met Office text such as '09:58 (UTC+1) on Thu 13 Aug 2026'."""

    text = re.sub(r"\s+", " ", value).strip()

    # Current/legacy Met Office pages may use explicit GMT or BST instead of a
    # numeric UTC offset.  Interpret both through Europe/London so DST rules are
    # applied from the date, including either side of the clock changes.
    named = re.search(
        r"(?P<time>\d{1,2}:\d{2})\s*(?:\((?P<zone1>GMT|BST)\)|(?P<zone2>GMT|BST))\s*"
        r"(?:on\s+)?(?:[A-Za-z]{3,9}\s+)?"
        r"(?P<day>\d{1,2})\s+(?P<month>[A-Za-z]{3,9})\s+(?P<year>\d{4})",
        text,
        re.I,
    )
    if named:
        raw = (
            f"{named.group('time')} {named.group('day')} "
            f"{named.group('month')} {named.group('year')}"
        )
        for fmt in ("%H:%M %d %b %Y", "%H:%M %d %B %Y"):
            try:
                return datetime.strptime(raw, fmt).replace(tzinfo=ZoneInfo("Europe/London"))
            except ValueError:
                continue

    match = re.search(
        r"(?P<time>\d{1,2}:\d{2})\s*"
        r"\(UTC(?P<sign>[+-])(?P<hours>\d{1,2})(?::?(?P<minutes>\d{2}))?\)\s*"
        r"(?:on\s+)?(?:[A-Za-z]{3,9}\s+)?"
        r"(?P<day>\d{1,2})\s+(?P<month>[A-Za-z]{3,9})\s+(?P<year>\d{4})",
        text,
        re.I,
    )
    if match:
        sign = 1 if match.group("sign") == "+" else -1
        offset = timedelta(
            hours=int(match.group("hours")),
            minutes=int(match.group("minutes") or 0),
        )
        tz = timezone(sign * offset)
        raw = (
            f"{match.group('time')} {match.group('day')} "
            f"{match.group('month')} {match.group('year')}"
        )
        for fmt in ("%H:%M %d %b %Y", "%H:%M %d %B %Y"):
            try:
                return datetime.strptime(raw, fmt).replace(tzinfo=tz)
            except ValueError:
                continue

    # Defensive fallback for a bare UTC clock or an unqualified UK-local clock.
    match = re.search(
        r"(?P<time>\d{1,2}:\d{2})\s*(?P<utc>UTC)?\s*(?:on\s+)?"
        r"(?:[A-Za-z]{3,9}\s+)?(?P<day>\d{1,2})\s+"
        r"(?P<month>[A-Za-z]{3,9})\s+(?P<year>\d{4})",
        text,
        re.I,
    )
    if match:
        raw = (
            f"{match.group('time')} {match.group('day')} "
            f"{match.group('month')} {match.group('year')}"
        )
        for fmt in ("%H:%M %d %b %Y", "%H:%M %d %B %Y"):
            try:
                parsed = datetime.strptime(raw, fmt)
                tz = timezone.utc if match.group("utc") else ZoneInfo("Europe/London")
                return parsed.replace(tzinfo=tz)
            except ValueError:
                continue
    return None


def parse_warning_details(html: str) -> WarningDetails:
    """Extract public warning-page detail fields from Met Office HTML.

    The parser deliberately works from visible heading text rather than CSS class
    names, which makes it less coupled to presentation changes on the website.
    """

    parser = _PageTextExtractor()
    parser.feed(html)
    text = parser.text()
    compact = re.sub(r"\s+", " ", text)

    further_details: str | None = None
    match = re.search(
        r"\bFurther details?\b\s*(?P<details>.+?)\s*"
        r"(?=\bGive us feedback about this warning\b|"
        r"\bMore detail on this warning\b|\bView all affected areas\b|"
        r"\bUK weather warnings\b|\bLast updated\b|$)",
        compact,
        re.I | re.S,
    )
    if match:
        further_details = _normalise_paragraph(match.group("details"))

    last_updated: datetime | None = None
    match = re.search(
        r"\bLast updated\b\s*(?P<updated>.+?)"
        r"(?=\bReason\s*:|\bRegions and local authorities affected\b|"
        r"\bView all affected areas\b|\bUK weather warnings\b|$)",
        compact,
        re.I | re.S,
    )
    if match:
        last_updated = _parse_last_updated(match.group("updated"))

    update_reason: str | None = None
    match = re.search(
        r"\bReason\s*:\s*(?P<reason>.+?)"
        r"(?=\bRegions and local authorities affected\b|\bView all affected areas\b|"
        r"\bUK weather warnings\b|$)",
        compact,
        re.I | re.S,
    )
    if match:
        update_reason = _normalise_paragraph(match.group("reason"))

    return WarningDetails(
        further_details=further_details,
        last_updated=last_updated,
        update_reason=update_reason,
    )
