"""Data update coordinator for PetTracer."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import PetTracerApi, PetTracerApiError
from .const import DOMAIN

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
        # No update_interval - data fetched once at startup, then updated via WebSocket
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=None,
        )
        self.api = api
        self.entry = entry
        self.devices: dict[str, dict[str, Any]] = {}
        self.home_stations: dict[str, dict[str, Any]] = {}

        # Register callback for WebSocket updates
        self.api.register_callback(self._handle_websocket_update)

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from PetTracer API.

        This is only called once at startup via async_config_entry_first_refresh().
        After that, all updates come via WebSocket callbacks.
        """
        _LOGGER.debug("Fetching initial data for coordinator")
        try:
            # Get all device data (signal + location)
            collars = await self.api.get_all_device_data()
            home_stations = await self.api.get_all_home_station_data()

            all_data = {
                "collars" : collars,
                "home_stations" : home_stations
            }
            _LOGGER.debug(f"Fetched initial data: {all_data}")

            # Update local device cache
            self.devices = all_data

            return all_data

        except PetTracerApiError as err:
            _LOGGER.debug(f"Error api: {err}")
            raise UpdateFailed(f"Error fetching PetTracer data: {err}") from err
        except Exception as err:
            _LOGGER.debug(f"Error exception: {err}")
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

    async def _update_device_from_websocket(self, device_id: str) -> None:
        """Update device data from API cache after WebSocket update."""
        try:
            # Get updated device data from API cache (no API calls, uses cached data only)
            device_data = await self.api.get_device_data(device_id, use_cache_only=True)
            _LOGGER.debug(f"Data coming from cached: {device_data}")
            # Update coordinator data
            if self.data:
                self.data["collars"][device_id] = device_data
            else:
                self.data["collars"] = {device_id: device_data}


            _LOGGER.debug(f"Data in the coordiantor:  {self.data}")

            self.devices["collars"][device_id] = device_data

            # Notify all listeners (sensors, device trackers) of the update
            self.async_set_updated_data(self.data)

            _LOGGER.debug("Updated device %s from WebSocket", device_id)

        except Exception as err:
            _LOGGER.error("Failed to update device %s from WebSocket: %s", device_id, err)

    def _handle_websocket_update(self, update: dict[str, Any]) -> None:
        """Handle WebSocket update by directly updating device data.

        No API polling - the API has already updated its internal cache,
        we just need to extract the data and notify listeners.
        """
        _LOGGER.debug("WebSocket update received: %s", update)

        device_id = update.get("device_id")

        if device_id:
            if device_id in self.devices["collars"] or device_id in self.api._devices:
                # Update device data from API cache (no new API call)
                self.hass.async_create_task(self._update_device_from_websocket(device_id))
            else:
                _LOGGER.debug("Received update for unknown device: %s", device_id)
        else:
            _LOGGER.debug("WebSocket update missing device_id")
