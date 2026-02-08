"""Device tracker platform for PetTracer integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PetTracerCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up PetTracer device trackers."""
    coordinator: PetTracerCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    
    entities: list[TrackerEntity] = []

    _LOGGER.debug(f"coordinato {coordinator}")
    _LOGGER.debug(f"coordinato {coordinator.data}")
    
    for device_id, device_data in coordinator.data.items():
        entities.append(PetTracerDeviceTracker(coordinator, device_id, device_data))
    
    async_add_entities(entities)


class PetTracerDeviceTracker(CoordinatorEntity[PetTracerCoordinator], TrackerEntity):
    """Representation of a PetTracer device tracker."""

    def __init__(
        self,
        coordinator: PetTracerCoordinator,
        device_id: str,
        device_data: dict[str, Any],
    ) -> None:
        """Initialize the device tracker."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._device_name = device_data.get("name", f"Tracker {device_id}")
        self._attr_unique_id = f"{device_id}_location"
        self._attr_name = None  # Use device name
        self._attr_has_entity_name = True

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=self._device_name,
            manufacturer="PetTracer",
            model="GPS Tracker",
        )

    @property
    def source_type(self) -> SourceType:
        """Return the source type."""
        return SourceType.GPS

    @property
    def latitude(self) -> float | None:
        """Return latitude value of the device."""
        data = self._get_device_data()
        if data:
            return data.get("latitude")
        return None

    @property
    def longitude(self) -> float | None:
        """Return longitude value of the device."""
        data = self._get_device_data()
        if data:
            return data.get("longitude")
        return None

    @property
    def battery_level(self) -> int | None:
        """Return battery level."""
        data = self._get_device_data()
        if data:
            return data.get("battery_level")
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        data = self._get_device_data()
        if data:
            return {
                "signal_percent": data.get("signal_percent"),
                "signal_level": data.get("signal_level"),
                "last_update": data.get("last_update"),
            }
        return {}

    def _get_device_data(self) -> dict[str, Any] | None:
        """Get current device data from coordinator."""
        if self.coordinator.data:
            return self.coordinator.data.get(self._device_id)
        return None
