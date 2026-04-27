"""Config flow for YoDeck integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import YoDeckApiClient, YoDeckApiError, YoDeckAuthError
from .const import CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN, MIN_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_TOKEN): str,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
            vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL)
        ),
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    session = async_get_clientsession(hass)
    client = YoDeckApiClient(session, data[CONF_API_TOKEN])

    if not await client.verify_token():
        raise YoDeckAuthError("Invalid API token")

    # Get schedules to use for title
    schedules_response = await client.get_schedules()
    schedules = schedules_response.get("results", [])

    return {
        "title": f"YoDeck ({len(schedules)} schedule{'s' if len(schedules) != 1 else ''})",
        "schedules": schedules,
    }


class YoDeckConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for YoDeck."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except YoDeckAuthError:
                errors["base"] = "invalid_auth"
            except YoDeckApiError:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                # Create unique ID based on API token hash to prevent duplicates
                await self.async_set_unique_id(user_input[CONF_API_TOKEN][:16])
                self._abort_if_unique_id_configured()

                # Separate scan_interval into options
                scan_interval = user_input.pop(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

                return self.async_create_entry(
                    title=info["title"],
                    data=user_input,
                    options={CONF_SCAN_INTERVAL: scan_interval},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> YoDeckOptionsFlowHandler:
        """Get the options flow for this handler."""
        return YoDeckOptionsFlowHandler(config_entry)


class YoDeckOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle YoDeck options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate scan interval
            scan_interval = user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            if scan_interval < MIN_SCAN_INTERVAL:
                errors[CONF_SCAN_INTERVAL] = "scan_interval_too_low"
            else:
                return self.async_create_entry(title="", data=user_input)

        # Get current values from the config entry (available as self.config_entry)
        current_scan_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=current_scan_interval,
                    ): vol.All(vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL)),
                }
            ),
            errors=errors,
            description_placeholders={
                "min_interval": str(MIN_SCAN_INTERVAL // 60),
                "default_interval": str(DEFAULT_SCAN_INTERVAL // 60),
            },
        )
