"""Select platform for PetTracer integration."""
from __future__ import annotations

import logging
from typing import Any


from homeassistant.config_entries import ConfigEntry
from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, COLLAR_MODES
from .coordinator import PetTracerCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
        hass: HomeAssistant,
        entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up PetTracer sensors."""
    coordinator: PetTracerCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    # Wait for first data fetch
    await coordinator.async_config_entry_first_refresh()

    entities: list[SelectEntity] = []
    for device_id, device_data in coordinator.data["collars"].items():
        # Signal strength percentage sensor
        entities.append(
            PetTracerModeSelector(coordinator, device_id, device_data)
        )

    async_add_entities(entities)


class PetTracerModeSelector(CoordinatorEntity[PetTracerCoordinator], SelectEntity):
    def __init__(self,
            coordinator: PetTracerCoordinator,
            device_id: str,
            device_data: dict[str, Any]):
        self.coordinator = coordinator
        self.api = coordinator.get_api()
        self._device_id = device_id
        self._attr_name = "Operation mode"
        self._attr_options = COLLAR_MODES.values()
        current_mode = device_data.get("mode")
        self._attr_current_option = COLLAR_MODES.get(current_mode, "Unknown")
        self._attr_icon = "mdi:cog-outline"
        self._MODE_TO_INT  = {v: k for k, v in COLLAR_MODES.items()}

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=self._device_name,
            manufacturer="PetTracer",
            model="GPS Tracker",
        )

    async def async_select_option(self, option: str) -> None:
        """Update the current selected option and call the API."""
        # 1. Call your API endpoint

        success = await self.api.set_collar_mode(self._MODE_TO_INT.get(option), int(self._device_id))

        if success:
            # 2. Update the internal state if the API call worked
            self._attr_current_option = option
            self.async_write_ha_state()