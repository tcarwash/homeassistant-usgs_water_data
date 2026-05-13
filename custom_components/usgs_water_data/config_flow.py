"""Config flow for USGS Water Data."""

from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries

from .const import (
    CONF_HISTORY_DAYS,
    CONF_MONITORING_LOCATION_ID,
    CONF_RECORD_LIMIT,
    CONF_SCAN_INTERVAL_MINUTES,
    DEFAULT_HISTORY_DAYS,
    DEFAULT_RECORD_LIMIT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)


class USGSWaterDataConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for USGS Water Data."""

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None):
        """Handle the initial step."""
        if user_input is not None:
            monitoring_location_id = (
                user_input[CONF_MONITORING_LOCATION_ID].strip().upper()
            )
            await self.async_set_unique_id(monitoring_location_id)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=f"USGS {monitoring_location_id}",
                data={CONF_MONITORING_LOCATION_ID: monitoring_location_id},
                options={
                    CONF_HISTORY_DAYS: user_input[CONF_HISTORY_DAYS],
                    CONF_RECORD_LIMIT: user_input[CONF_RECORD_LIMIT],
                    CONF_SCAN_INTERVAL_MINUTES: user_input[CONF_SCAN_INTERVAL_MINUTES],
                },
            )

        return self.async_show_form(step_id="user", data_schema=self._user_schema())

    @staticmethod
    def _user_schema() -> vol.Schema:
        """Return config schema for setup form."""
        return vol.Schema(
            {
                vol.Required(CONF_MONITORING_LOCATION_ID): str,
                vol.Optional(
                    CONF_HISTORY_DAYS,
                    default=DEFAULT_HISTORY_DAYS,
                ): vol.All(vol.Coerce(int), vol.Range(min=0, max=365)),
                vol.Optional(
                    CONF_RECORD_LIMIT,
                    default=DEFAULT_RECORD_LIMIT,
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=1000)),
                vol.Optional(
                    CONF_SCAN_INTERVAL_MINUTES,
                    default=int(DEFAULT_SCAN_INTERVAL.total_seconds() / 60),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=1440)),
            }
        )

    @staticmethod
    @config_entries.callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """Create the options flow."""
        return USGSWaterDataOptionsFlow(config_entry)


class USGSWaterDataOptionsFlow(config_entries.OptionsFlow):
    """Handle options for the integration."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict | None = None):
        """Manage options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = self.config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_HISTORY_DAYS,
                        default=options.get(CONF_HISTORY_DAYS, DEFAULT_HISTORY_DAYS),
                    ): vol.All(vol.Coerce(int), vol.Range(min=0, max=365)),
                    vol.Optional(
                        CONF_RECORD_LIMIT,
                        default=options.get(CONF_RECORD_LIMIT, DEFAULT_RECORD_LIMIT),
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=1000)),
                    vol.Optional(
                        CONF_SCAN_INTERVAL_MINUTES,
                        default=options.get(
                            CONF_SCAN_INTERVAL_MINUTES,
                            int(DEFAULT_SCAN_INTERVAL.total_seconds() / 60),
                        ),
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=1440)),
                }
            ),
        )
