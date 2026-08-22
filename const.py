from __future__ import annotations

from datetime import timedelta

DOMAIN = "metoffice_weather_warnings"
NAME = "Met Office Weather Warnings"
VERSION = "0.1.2"

PLATFORMS = ["binary_sensor", "calendar", "sensor"]

CONF_REGION = "region"
CONF_AREA_FILTERS = "area_filters"
CONF_SEVERITIES = "severities"
CONF_WEATHER_TYPES = "weather_types"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_REGION = "em"
DEFAULT_SCAN_INTERVAL = 10
MIN_SCAN_INTERVAL = 5
MAX_SCAN_INTERVAL = 60

DEFAULT_SEVERITIES = ["yellow", "amber", "red"]
DEFAULT_WEATHER_TYPES = [
    "rain",
    "thunderstorm",
    "wind",
    "snow",
    "lightning",
    "ice",
    "fog",
    "extreme heat",
]

SEVERITY_RANK = {"none": 0, "yellow": 1, "amber": 2, "red": 3}

REGIONS = {
    "os": "Orkney & Shetland",
    "he": "Highlands & Eilean Siar",
    "gr": "Grampian",
    "st": "Strathclyde",
    "ta": "Central, Tayside & Fife",
    "dg": "SW Scotland, Lothian Borders",
    "ni": "Northern Ireland",
    "wl": "Wales",
    "nw": "North West England",
    "ne": "North East England",
    "yh": "Yorkshire & Humber",
    "wm": "West Midlands",
    "em": "East Midlands",
    "ee": "East of England",
    "sw": "South West England",
    "se": "London & South East England",
}

RSS_URL = "https://www.metoffice.gov.uk/public/data/PWSCache/WarningsRSS/Region/{region}"
ATTRIBUTION = "Data supplied by the Met Office"
MET_OFFICE_WARNINGS_URL = "https://weather.metoffice.gov.uk/warnings-and-advice/uk-warnings"

DEFAULT_UPDATE_INTERVAL = timedelta(minutes=DEFAULT_SCAN_INTERVAL)
