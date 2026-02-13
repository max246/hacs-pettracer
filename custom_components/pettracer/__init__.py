"""PetTracer integration for Home Assistant."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import PetTracerApi
from .const import DOMAIN
from .coordinator import PetTracerCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.DEVICE_TRACKER,
    Platform.SELECT,
    Platform.SWITCH,
    Platform.BUTTON
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up PetTracer from a config entry."""
    session = async_get_clientsession(hass)
    
    api = PetTracerApi(
        email=entry.data[CONF_EMAIL],
        password=entry.data[CONF_PASSWORD],
        session=session,
    )
    
    # Authenticate
    await api.authenticate()
    
    # Create coordinator
    coordinator = PetTracerCoordinator(hass, api, entry)
    
    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()
    
    # Start WebSocket for real-time updates
    await coordinator.start_websocket()
    
    # Store for platforms
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "coordinator": coordinator,
    }
    
    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    _LOGGER.info("PetTracer integration setup complete with WebSocket support")
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: PetTracerCoordinator = data["coordinator"]
    
    # Stop WebSocket connection
    await coordinator.stop_websocket()
    
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id)
        api: PetTracerApi = data["api"]
        await api.close()
    
    return unload_ok
