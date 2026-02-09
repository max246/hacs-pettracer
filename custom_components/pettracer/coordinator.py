"""Data update coordinator for PetTracer."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import PetTracerApi, PetTracerApiError
from .const import DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


class PetTracerCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to manage fetching PetTracer data."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: PetTracerApi,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )
        self.api = api
        self.entry = entry
        self.devices: dict[str, dict[str, Any]] = {}
        
        # Register callback for WebSocket updates
        self.api.register_callback(self._handle_websocket_update)

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from PetTracer API."""
        _LOGGER.debug("Fetching data for coordinator")
        try:
            # Get all device data (signal + location)
            all_data = await self.api.get_all_device_data()
            _LOGGER.debug(f"Fetched {all_data}")
            
            # Update local device cache
            self.devices = all_data
            
            return all_data
            
        except PetTracerApiError as err:
            _LOGGER.debug(f"Error api  {err}")
            raise UpdateFailed(f"Error fetching PetTracer data: {err}") from err
        except Exception as err:
            _LOGGER.debug(f"Error exce  {err}")
            raise UpdateFailed(f"Unexpected error: {err}") from err

    def get_device_data(self, device_id: str) -> dict[str, Any] | None:
        """Get data for a specific device."""
        return self.data.get(device_id) if self.data else None

    async def start_websocket(self) -> None:
        """Start WebSocket connection for real-time updates."""
        try:
            await self.api.connect_websocket()
            _LOGGER.info("WebSocket connection started")
        except Exception as err:
            _LOGGER.error("Failed to start WebSocket: %s", err)

    async def stop_websocket(self) -> None:
        """Stop WebSocket connection."""
        await self.api.disconnect_websocket()
        _LOGGER.info("WebSocket connection stopped")

    def _handle_websocket_update(self, update: dict[str, Any]) -> None:
        """Handle WebSocket update and trigger coordinator refresh."""
        _LOGGER.debug("WebSocket update received: %s", update)
        
        device_id = update.get("device_id")
        
        if device_id and device_id in self.devices:
            # Trigger an async refresh to update all entities
            # This will call _async_update_data and notify all listeners
            self.hass.async_create_task(self.async_request_refresh())
        else:
            _LOGGER.debug("Received update for unknown device: %s", device_id)
