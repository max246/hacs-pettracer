"""Config flow for PetTracer integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import PetTracerApi, PetTracerAuthError, PetTracerApiError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class PetTracerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for PetTracer."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            email = user_input[CONF_EMAIL]
            password = user_input[CONF_PASSWORD]

            # Check if already configured
            await self.async_set_unique_id(email.lower())
            self._abort_if_unique_id_configured()

            # Test credentials
            session = async_get_clientsession(self.hass)
            api = PetTracerApi(email, password, session)

            try:
                await api.authenticate()
                
                # Get user info to verify we can access data
                await api.get_devices()
                
                return self.async_create_entry(
                    title=f"PetTracer ({email})",
                    data=user_input,
                )
                
            except PetTracerAuthError:
                errors["base"] = "invalid_auth"
            except PetTracerApiError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during setup")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
