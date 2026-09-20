from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers import selector

from .const import (
    CONF_AREA_FILTERS,
    CONF_REGION,
    CONF_SCAN_INTERVAL,
    CONF_SEVERITIES,
    CONF_WEATHER_TYPES,
    DEFAULT_REGION,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SEVERITIES,
    DEFAULT_WEATHER_TYPES,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    REGIONS,
)


def _region_selector() -> selector.SelectSelector:
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=[selector.SelectOptionDict(value=code, label=name) for code, name in REGIONS.items()],
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )


def _multi(options: list[str]) -> selector.SelectSelector:
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=[selector.SelectOptionDict(value=value, label=value.title()) for value in options],
            multiple=True,
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )


def _schema(defaults: dict[str, Any], *, include_region: bool) -> vol.Schema:
    fields: dict[Any, Any] = {}
    if include_region:
        fields[vol.Required(CONF_REGION, default=defaults.get(CONF_REGION, DEFAULT_REGION))] = _region_selector()
    fields[vol.Optional(CONF_AREA_FILTERS, default=defaults.get(CONF_AREA_FILTERS, ""))] = selector.TextSelector(
        selector.TextSelectorConfig(multiline=False)
    )
    fields[vol.Required(CONF_SEVERITIES, default=defaults.get(CONF_SEVERITIES, DEFAULT_SEVERITIES))] = _multi(
        ["yellow", "amber", "red"]
    )
    fields[vol.Required(CONF_WEATHER_TYPES, default=defaults.get(CONF_WEATHER_TYPES, DEFAULT_WEATHER_TYPES))] = _multi(
        DEFAULT_WEATHER_TYPES
    )
    fields[vol.Required(CONF_SCAN_INTERVAL, default=defaults.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))] = selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=MIN_SCAN_INTERVAL,
            max=MAX_SCAN_INTERVAL,
            step=1,
            mode=selector.NumberSelectorMode.BOX,
            unit_of_measurement="min",
        )
    )
    return vol.Schema(fields)


class MetOfficeWarningsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    MINOR_VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        return MetOfficeWarningsOptionsFlow()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            region = user_input[CONF_REGION]
            await self.async_set_unique_id(f"metoffice_warnings_{region}")
            self._abort_if_unique_id_configured()
            options = {
                CONF_AREA_FILTERS: user_input.get(CONF_AREA_FILTERS, ""),
                CONF_SEVERITIES: user_input[CONF_SEVERITIES],
                CONF_WEATHER_TYPES: user_input[CONF_WEATHER_TYPES],
                CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
            }
            return self.async_create_entry(
                title=f"Met Office Weather Warnings — {REGIONS[region]}",
                data={CONF_REGION: region},
                options=options,
            )
        return self.async_show_form(step_id="user", data_schema=_schema({}, include_region=True))

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        entry = self._get_reconfigure_entry()
        defaults = {**entry.data, **entry.options}
        if user_input is not None:
            region = user_input[CONF_REGION]
            options = {
                CONF_AREA_FILTERS: user_input.get(CONF_AREA_FILTERS, ""),
                CONF_SEVERITIES: user_input[CONF_SEVERITIES],
                CONF_WEATHER_TYPES: user_input[CONF_WEATHER_TYPES],
                CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
            }
            return self.async_update_reload_and_abort(
                entry,
                unique_id=f"metoffice_warnings_{region}",
                data={CONF_REGION: region},
                options=options,
                title=f"Met Office Weather Warnings — {REGIONS[region]}",
            )
        return self.async_show_form(step_id="reconfigure", data_schema=_schema(defaults, include_region=True))


class MetOfficeWarningsOptionsFlow(config_entries.OptionsFlowWithReload):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        defaults = {**self.config_entry.data, **self.config_entry.options}
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={
                    CONF_AREA_FILTERS: user_input.get(CONF_AREA_FILTERS, ""),
                    CONF_SEVERITIES: user_input[CONF_SEVERITIES],
                    CONF_WEATHER_TYPES: user_input[CONF_WEATHER_TYPES],
                    CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
                },
            )
        return self.async_show_form(step_id="init", data_schema=_schema(defaults, include_region=False))
