"""Sensor platform for PetTracer integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfElectricPotential, PERCENTAGE, SIGNAL_STRENGTH_DECIBELS_MILLIWATT, ATTR_BATTERY_CHARGING, ATTR_SW_VERSION, ATTR_HW_VERSION
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
    """Set up PetTracer sensors."""
    coordinator: PetTracerCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    
    # Wait for first data fetch
    await coordinator.async_config_entry_first_refresh()
    
    entities: list[SensorEntity] = []
    
    for device_id, device_data in coordinator.data.items():
        # Signal strength percentage sensor
        entities.append(
            PetTracerSignalPercentSensor(coordinator, device_id, device_data)
        )
        # Signal strength dBm sensor
        entities.append(
            PetTracerSignalDbmSensor(coordinator, device_id, device_data)
        )
        # Signal level sensor (text: excellent/good/fair/poor/none)
        entities.append(
            PetTracerSignalLevelSensor(coordinator, device_id, device_data)
        )

        # Battery level sensor
        entities.append(
            PetTracerBatterySensor(coordinator, device_id, device_data)
        )
        # Battery voltage sensor
        entities.append(
            PetTracerBatteryVoltageSensor(coordinator, device_id, device_data)
        )

        # Software Version sensor
        entities.append(
            PetTracerSoftwareVersionSensor(coordinator, device_id, device_data)
        )
        # Hardware Version sensor
        entities.append(
            PetTracerHardwareVersionSensor(coordinator, device_id, device_data)
        )

        # Operation mode sensor
        entities.append(
            PetTracerOperationModeSensor(coordinator, device_id, device_data)
        )

        # Collar Colour sensor
        entities.append(
            PetTracerCollarColourSensor(coordinator, device_id, device_data)
        )

    async_add_entities(entities)


class PetTracerBaseSensor(CoordinatorEntity[PetTracerCoordinator], SensorEntity):
    """Base class for PetTracer sensors."""

    def __init__(
        self,
        coordinator: PetTracerCoordinator,
        device_id: str,
        device_data: dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._device_name = device_data.get("name", f"Tracker {device_id}")
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

    def _get_device_data(self) -> dict[str, Any] | None:
        """Get current device data from coordinator."""
        if self.coordinator.data:
            return self.coordinator.data.get(self._device_id)
        return None

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


class PetTracerSignalPercentSensor(PetTracerBaseSensor):
    """Sensor for signal strength percentage."""

    def __init__(
        self,
        coordinator: PetTracerCoordinator,
        device_id: str,
        device_data: dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, device_id, device_data)
        self._attr_unique_id = f"{device_id}_signal_percent"
        self._attr_name = "Signal Strength"
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:signal"

    @property
    def native_value(self) -> int | None:
        """Return the signal percentage."""
        data = self._get_device_data()
        if data:
            return data.get("signal_percent")
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        data = self._get_device_data()
        if data:
            return {
                "rssi_dbm": data.get("rssi_dbm"),
                "signal_level": data.get("signal_level"),
                "last_update": data.get("last_update"),
            }
        return {}


class PetTracerSignalDbmSensor(PetTracerBaseSensor):
    """Sensor for signal strength in dBm."""

    def __init__(
        self,
        coordinator: PetTracerCoordinator,
        device_id: str,
        device_data: dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, device_id, device_data)
        self._attr_unique_id = f"{device_id}_signal_dbm"
        self._attr_name = "Signal dBm"
        self._attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT
        self._attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:signal-variant"

    @property
    def native_value(self) -> float | None:
        """Return the signal strength in dBm."""
        data = self._get_device_data()
        if data:
            return data.get("rssi_dbm")
        return None


class PetTracerBatteryVoltageSensor(PetTracerBaseSensor):
    """Sensor for battery voltage."""

    def __init__(
        self,
        coordinator: PetTracerCoordinator,
        device_id: str,
        device_data: dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, device_id, device_data)
        self._attr_unique_id = f"{device_id}_battery_voltage"
        self._attr_name = "Battery Voltage"
        self._attr_device_class = SensorDeviceClass.VOLTAGE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfElectricPotential.MILLIVOLT
        self._attr_icon = "mdi:battery"

    @property
    def native_value(self) -> int | None:
        """Return the battery voltage."""
        data = self._get_device_data()
        if data:
            return data.get("battery_level")
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        data = self._get_device_data()
        if data:
            return {
                ATTR_BATTERY_CHARGING: data.get("charging"),
            }
        return {}


class PetTracerBatterySensor(PetTracerBaseSensor):
    """Sensor for battery level."""

    def __init__(
        self,
        coordinator: PetTracerCoordinator,
        device_id: str,
        device_data: dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, device_id, device_data)
        self._attr_unique_id = f"{device_id}_battery"
        self._attr_name = "Battery"
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_device_class = SensorDeviceClass.BATTERY
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:battery"

    def calculate_battery_percentage(self, voltage_mv: int) -> float:
        """
        Converts battery millivolts to a percentage (0-100).
        Input range: 3000mV (0%) to 4150mV (100%).
        """
        # Clamp the voltage between 3000 and 4150
        voltage = max(3000, min(voltage_mv, 4150))
        _LOGGER.debug(f"Voltage in: {voltage_mv} and clamped {voltage}")
        
        if voltage >= 4000:
            # Range: 4000 - 4150
            percentage = (voltage - 4150) / 150 * 17 + 83
        elif voltage >= 3900:
            # Range: 3900 - 3999
            percentage = (voltage - 3900) / 100 * 26 + 67
        elif voltage >= 3840:
            # Range: 3840 - 3899
            percentage = (voltage - 3840) / 60 * 17 + 50
        elif voltage >= 3760:
            # Range: 3760 - 3839
            percentage = (voltage - 3760) / 80 * 16 + 34
        elif voltage >= 3600:
            # Range: 3600 - 3759
            percentage = (voltage - 3600) / 160 * 17 + 17
        else:
            # Below 3600
            percentage = 0

        _LOGGER.debug(f"Raw percentage: {percentage} and round {round(percentage)}")
            
        return round(percentage)

    @property
    def native_value(self) -> int | None:
        """Return the battery level."""
        data = self._get_device_data()
        if data:
            return self.calculate_battery_percentage(data.get("battery_level"))
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        data = self._get_device_data()
        if data:
            return {
                ATTR_BATTERY_CHARGING: data.get("charging"),
            }
        return {}


class PetTracerSignalLevelSensor(PetTracerBaseSensor):
    """Sensor for signal level (text)."""

    def __init__(
        self,
        coordinator: PetTracerCoordinator,
        device_id: str,
        device_data: dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, device_id, device_data)
        self._attr_unique_id = f"{device_id}_signal_level"
        self._attr_name = "Signal Level"
        self._attr_icon = "mdi:signal-cellular-3"

    @property
    def native_value(self) -> str | None:
        """Return the signal level."""
        data = self._get_device_data()
        if data:
            return data.get("signal_level")
        return None

    @property
    def icon(self) -> str:
        """Return icon based on signal level."""
        data = self._get_device_data()
        if data:
            level = data.get("signal_level", "none")
            icons = {
                "excellent": "mdi:signal-cellular-3",
                "good": "mdi:signal-cellular-2",
                "fair": "mdi:signal-cellular-1",
                "poor": "mdi:signal-cellular-outline",
                "none": "mdi:signal-off",
            }
            return icons.get(level, "mdi:signal")
        return "mdi:signal"

class PetTracerSoftwareVersionSensor(PetTracerBaseSensor):
    """Sensor for software version."""

    def __init__(
        self,
        coordinator: PetTracerCoordinator,
        device_id: str,
        device_data: dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, device_id, device_data)
        self._attr_unique_id = f"{device_id}_software_version"
        self._attr_name = "Software Version"
        self._attr_icon = "mdi:package-up"

    @property
    def native_value(self) -> int | None:
        """Return the software version."""
        data = self._get_device_data()
        if data:
            return data.get("sw")
        return None

class PetTracerOperationModeSensor(PetTracerBaseSensor):
    """Sensor for operation mode."""

    def __init__(
            self,
            coordinator: PetTracerCoordinator,
            device_id: str,
            device_data: dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, device_id, device_data)
        self._attr_unique_id = f"{device_id}_operation_mode"
        self._attr_name = "Operation Mode"
        self._attr_device_class = None
        self._attr_icon = "mdi:cog-outline"

    def _get_text_name(self, mode: int | None) -> str:
        modes = {
            1: "Fast", #"TM_FAST_1",
            2: "Medium", #"TM_MEDIUM",
            3: "Slow", #"TM_SLOW",
            4: "Ultra Slow", #"TM_ULTRASLOW",
            5: "Test", #"TM_TEST",
            6: "Slow 3", #"TM_SLOW_3",
            7: "Slow 4", #"TM_SLOW_4",
            8: "Fast 2", #"TM_FAST_2",
            10: "Battery Low", #"TM_BATLOW",
            11: "Search mode", #"TM_SEARCH",
            12: "Turned off (need activating)", #"TM_OFF",
            14: "Normal 2", #"TM_NORMAL_2",
            18: "Peil 3", #"TM_PEIL_3",
            19: "Peil 4", #"TM_PEIL_4"
        }
        return modes.get(mode, "Unknown")

    @property
    def native_value(self) -> str | None:
        """Return the software version."""
        data = self._get_device_data()
        if data:
            return self._get_text_name(data.get("mode"))
        return None

class PetTracerCollarColourSensor(PetTracerBaseSensor):
    """Sensor for colour collar."""

    def __init__(
            self,
            coordinator: PetTracerCoordinator,
            device_id: str,
            device_data: dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, device_id, device_data)
        self._attr_unique_id = f"{device_id}_collar_colour"
        self._attr_name = "Collar colour"
        self._attr_device_class =  None
        self._attr_icon = "mdi:cat"
        self._hex_code = ""

    def _get_hex_colour(self, colour: int) -> str:
        # Extract RGB components using bitwise shifts
        r = (colour >> 16) & 255
        g = (colour >> 8) & 255
        b = colour & 255

        # Format as hex string:
        # :02x means hex format, lowercase, padded to 2 characters with 0s
        return f"#{r:02x}{g:02x}{b:02x}"

    def _get_name(self, colour: str) -> str:
        colour_names = {
            "#0000FF": "blue",
            "#00FF00": "green",
            "#FF0000": "red",
            "#FF00FF": "pink"
        }
        return colour_names.get(colour, "Unknown")

    @property
    def native_value(self) -> str | None:
        """Return the software version."""
        data = self._get_device_data()
        if data:
            self._hex_code = self._get_hex_colour(data.get("colour"))
            return self._get_name(self._hex_code)
        return None

    @property
    def entity_picture(self):
        # Returns a 1x1 pixel square of the colour
        colour = self._hex_code
        return f"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1 1'><rect width='1' height='1' fill='{colour}'/></svg>"

class PetTracerHardwareVersionSensor(PetTracerBaseSensor):
    """Sensor for Hardware version."""

    def __init__(
            self,
            coordinator: PetTracerCoordinator,
            device_id: str,
            device_data: dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, device_id, device_data)
        self._attr_unique_id = f"{device_id}_hardware_version"
        self._attr_name = "Hardware Version"
        self._attr_icon = "mdi:chip"

    @property
    def native_value(self) -> int | None:
        """Return the software version."""
        data = self._get_device_data()
        if data:
            return data.get("hw")
        return None