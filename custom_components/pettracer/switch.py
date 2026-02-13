"""Switch platform for PetTracer integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.const import ATTR_SW_VERSION, ATTR_HW_VERSION

from homeassistant.config_entries import ConfigEntry
from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN
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

    entities: list[SwitchEntity] = []
    for device_id, device_data in coordinator.data["collars"].items():
        # LED switch
        entities.append(
            PetTracerLEDSwitch(coordinator, device_id, device_data)
        )
        # Buzzer switch
        entities.append(
            PetTracerBuzzerSwitch(coordinator, device_id, device_data)
        )

    async_add_entities(entities)


class PetTracerBaseSwitch(CoordinatorEntity[PetTracerCoordinator], SwitchEntity):
    """Base class for PetTracer sensors."""

    def __init__(
        self,
        coordinator: PetTracerCoordinator,
        device_id: str,
        device_data: dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.api = coordinator.get_api()
        self._device_id = device_id
        self._device_name = device_data.get("name", f"Tracker {device_id}")
        self._attr_has_entity_name = True
        self._attr_is_on = False

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=self._device_name,
            manufacturer="PetTracer",
            model="GPS Tracker",
        )

    def _get_device_data(self) -> dict[str, Any] | None:
        """Get current device data from coordinator."""
        if self.coordinator.data["collars"]:
            return self.coordinator.data["collars"].get(self._device_id)
        return None

    @property
    def is_on(self) -> bool:
        """Return True if the switch is currently on."""
        return self._attr_is_on

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        data = self._get_device_data()
        if data:
            return {
                ATTR_SW_VERSION: data.get("rssi_dbm"),
                ATTR_HW_VERSION: data.get("signal_level"),
                "last_update": data.get("last_update"),
            }
        return {}

class PetTracerLEDSwitch(PetTracerBaseSwitch):
    """Sensor for led switch."""

    def __init__(
        self,
        coordinator: PetTracerCoordinator,
        device_id: str,
        device_data: dict[str, Any],
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, device_id, device_data)
        self._attr_unique_id = f"{device_id}_set_led"
        self._attr_name = "LED Switch"
        self._attr_icon = "mdi:lightbulb-outline"
        self._attr_is_on = True if device_data.get("led_status") else False

    async def async_turn_on(self, **kwargs) -> None:
        """Send the 'Turn On' command to the API."""
        success = await self.api.set_led_mode(1, self._device_id)
        if success:
            self._attr_is_on = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Send the 'Turn Off' command to the API."""
        success = await self.api.set_led_mode(0, self._device_id)
        if success:
            self._attr_is_on = False
            self.async_write_ha_state()

class PetTracerBuzzerSwitch(PetTracerBaseSwitch):
    """Sensor for buzzer switch."""

    def __init__(
        self,
        coordinator: PetTracerCoordinator,
        device_id: str,
        device_data: dict[str, Any],
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, device_id, device_data)
        self._attr_unique_id = f"{device_id}_set_buzzer"
        self._attr_name = "Buzzer Switch"
        self._attr_icon = "mdi:bugle"
        self._attr_is_on = True if device_data.get("buzzer") else False

    async def async_turn_on(self, **kwargs) -> None:
        """Send the 'Turn On' command to the API."""
        success = await self.api.set_buzzer_mode(1, self._device_id)
        if success:
            self._attr_is_on = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Send the 'Turn Off' command to the API."""
        success = await self.api.set_buzzer_mode(1, self._device_id)
        if success:
            self._attr_is_on = False
            self.async_write_ha_state()
