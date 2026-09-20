# Met Office Weather Warnings

Home Assistant custom integration for regional Met Office severe weather warnings. Current version: **0.1.9**.

## Installation and upgrades

1. Download this repository and copy `custom_components/metoffice_weather_warnings` into your Home Assistant configuration directory's `custom_components` folder.
2. For an upgrade, replace the existing integration folder with this version while retaining your Home Assistant configuration.
3. Restart Home Assistant.
4. For a new installation, open **Settings → Devices & services → Add integration** and select **Met Office Weather Warnings**.

The installed manifest must be at `config/custom_components/metoffice_weather_warnings/manifest.json`. Existing configured entries do not need to be removed and recreated.

Earlier repository versions placed the integration files at the repository root. This version preserves the original distribution's `custom_components/metoffice_weather_warnings` layout; copy that inner folder when upgrading.

## Configuration

Choose a UK warning region, optional comma-separated area filters, warning severities, weather types, and a refresh interval. The default interval is 10 minutes, configurable from 5 to 60 minutes. Filters and the refresh interval can be changed through the integration options. No API key is required.

## Entities

| Entity | Purpose |
| --- | --- |
| Current warning | Highest-severity warning currently in force |
| Next warning | Earliest warning that has not started yet |
| Next warning start / end | Timestamps for that upcoming warning |
| Active / upcoming counts | Number of matching warnings in each group |
| Highest level | Highest active severity, or `none` |
| Active / upcoming binary sensors | Whether matching warnings exist in each group |
| Calendar | Matching warning events, with available detail in their descriptions |

Current warning and Next warning have independent attributes: `warning_id`, `severity`, `weather_type`, `summary`, `further_details`, `last_updated`, `update_reason`, `start`, `end`, `matched_areas`, and `link`. Entity IDs depend on Home Assistant's entity registry and any custom names.

Detail pages are fetched for new or changed warnings and useful results are cached. Empty results are retried. A detail-page failure does not make the underlying RSS warning unavailable. Further details end before the Met Office feedback section.

RSS validity times are interpreted as UTC. Home Assistant displays timestamps in its configured timezone; use `Europe/London` for GMT/BST display.

## Warning events

The existing event type is `metoffice_weather_warnings_warning`. Actions include `issued`, `updated`, `became_active`, `expired`, and `cancelled`. Initial refresh does not emit change events.

The original v0.1.9 code already labels a warning that disappears from the filtered results before its scheduled end as `cancelled`, otherwise `expired`. This is an inference from disappearance, not confirmation of an official cancellation. This release preserves that behavior without adding cancellation logic.

## Version and validation

See [CHANGELOG.md](CHANGELOG.md). The integration source and branding come from the original `metoffice_weather_warnings_v0.1.9.zip`; generated Python bytecode is excluded. The stale internal version constant is aligned with the manifest's `0.1.9`.

Python syntax and JSON validity were checked before publication. A full Home Assistant runtime test has not been performed as part of this publication.

Data supplied by the [Met Office](https://weather.metoffice.gov.uk/warnings-and-advice/uk-warnings).
