"""PetTracer API client."""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Callable

import aiohttp

from .const import (
    API_URL,
    WEBSOCKET_URL,
    ENDPOINT_LOGIN,
    ENDPOINT_CAT_COLLARS,
    ENDPOINT_CC_INFO,
)

_LOGGER = logging.getLogger(__name__)


def format_rssi(raw_value: int) -> float:
    """Convert raw RSSI value to dBm."""
    return (255 & raw_value) / 2 - 130


def rssi_to_percent(dbm: float) -> int:
    """Convert dBm to signal percentage."""
    if dbm >= -1.5:
        return 100
    # Formula from PetTracer JS: 100 * 1.35 * (1 - dbm / -130)
    percent = 100 * max(0, min(1, 1.35 * (1 - dbm / -130)))
    return round(percent)


def get_signal_level(percent: int) -> str:
    """Get signal level string from percentage."""
    if percent > 70:
        return "excellent"
    if percent > 50:
        return "good"
    if percent > 30:
        return "fair"
    if percent > 5:
        return "poor"
    return "none"


class PetTracerApiError(Exception):
    """Exception for API errors."""


class PetTracerAuthError(PetTracerApiError):
    """Exception for authentication errors."""


class PetTracerApi:
    """PetTracer API client."""

    def __init__(
        self,
        email: str,
        password: str,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        """Initialize the API client."""
        self._email = email
        self._password = password
        self._session = session
        self._own_session = session is None
        self._token: str | None = None
        self._token_expires: datetime | None = None
        self._user_data: dict[str, Any] = {}
        self._devices: dict[str, dict[str, Any]] = {}
        self._callbacks: list[Callable[[dict[str, Any]], None]] = []

    async def _ensure_session(self) -> aiohttp.ClientSession:
        """Ensure we have an aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
            self._own_session = True
        return self._session

    async def close(self) -> None:
        """Close the session."""
        if self._own_session and self._session:
            await self._session.close()

    def _is_token_valid(self) -> bool:
        """Check if current token is still valid."""
        if not self._token or not self._token_expires:
            return False
        # Add 5 minute buffer
        return datetime.now() < self._token_expires - timedelta(minutes=5)

    async def authenticate(self) -> bool:
        """Authenticate with PetTracer API."""
        session = await self._ensure_session()
        
        try:
            async with session.post(
                f"{API_URL}{ENDPOINT_LOGIN}",
                json={"login": self._email, "password": self._password},
                headers={"Content-Type": "application/json"},
            ) as response:
                if response.status == 401:
                    raise PetTracerAuthError("Invalid credentials")
                if response.status != 200:
                    raise PetTracerApiError(f"Login failed with status {response.status}")
                

                data = await response.json()
                self._token = data.get("access_token")
                expires_str = data.get("expires")
                
                if expires_str:
                    self._token_expires = datetime.fromisoformat(
                        expires_str.replace("Z", "+00:00")
                    )
                
                _LOGGER.debug("Successfully authenticated with PetTracer")
                return True
                
        except aiohttp.ClientError as err:
            _LOGGER.debug(f"Error {err}")
            raise PetTracerApiError(f"Connection error: {err}") from err

    async def _ensure_authenticated(self) -> None:
        """Ensure we have a valid token."""
        if not self._is_token_valid():
            await self.authenticate()

    def _get_auth_headers(self) -> dict[str, str]:
        """Get authorization headers."""
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
            "Referer": "https://portal.pettracer.com/en/dashboard",
            "Host": "portal.pettracer.com"
        }

    async def get_cat_collars(self) -> dict[str, Any]:
        """Get cat collars info."""
        await self._ensure_authenticated()
        session = await self._ensure_session()
        
        try:
            async with session.get(
                f"{API_URL}{ENDPOINT_CAT_COLLARS}",
                headers=self._get_auth_headers(),
            ) as response:
                if response.status != 200:
                    _LOGGER.debug(f"Error {response}")
                    raise PetTracerApiError(f"Failed to get user info: {response.status}")
                
                self._user_data = await response.json()
                return self._user_data
        except Exception as e:
            _LOGGER.debug(f"Error {e}")
            raise PetTracerApiError(f"Failure to retrive collars")
            

    async def get_devices(self) -> list[dict[str, Any]]:
        """Get list of devices (command centers/trackers)."""
        collars = await self.get_cat_collars()
        
        # Update local device cache
        for collar in collars:
            collar_id = str(collar.get("id"))
            self._devices[collar_id] = collar_id
        
        return collars

    async def get_device_fifo(self, device_id: str) -> dict[str, Any]:
        """Get FIFO data for a device (latest positions and signal)."""
        await self._ensure_authenticated()
        session = await self._ensure_session()
       
        
        async with session.post(
            f"{API_URL}{ENDPOINT_CC_INFO}",
            json={"devId": device_id},
            headers=self._get_auth_headers(),
        ) as response:
            if response.status != 200:
                raise PetTracerApiError(f"Failed to get FIFO: {response.status}")
            
            return await response.json()

    async def get_device_data(self, device_id: str) -> dict[str, Any]:
        """Get all data for a device including signal and location."""
        device = self._devices.get(device_id, {})
        device_name = device.get("details", {}).get("name", f"Tracker {device_id}")
        
        result = {
            "device_id": device_id,
            "name": device_name,
            "rssi_raw": 0,
            "rssi_dbm": -130,
            "signal_percent": 0,
            "signal_level": "none",
            "latitude": None,
            "longitude": None,
            "battery_level": None,
            "last_update": None,
        }
        
        # Get battery from device data
        if device.get("accuWarn") is not None:
            # accuWarn is a battery level indicator
            result["battery_level"] = device.get("accuWarn")
        
        # Get location from lastPos
        last_pos = device.get("lastPos")
        if last_pos:
            result["latitude"] = last_pos.get("lat")
            result["longitude"] = last_pos.get("lng")
            result["last_update"] = last_pos.get("timeDb")
        
        # Get latest FIFO data for most recent signal
        try:
            device_info = await self.get_device_fifo(device_id)

            if device_info and "fifo" in device_info:

                fifo_data = device_info["fifo"]            
                # Extract signal and position from FIFO data
                if isinstance(fifo_data, list) and len(fifo_data) > 0:
                    latest = fifo_data[0]
                    
                    # Signal from receivedBy
                    received_by = latest.get("receivedBy", [])
                    if received_by:
                        raw_rssi = received_by[0].get("rssi", 0)
                        dbm = format_rssi(raw_rssi)
                        percent = rssi_to_percent(dbm)
                        
                        result["rssi_raw"] = raw_rssi
                        result["rssi_dbm"] = dbm
                        result["signal_percent"] = percent
                        result["signal_level"] = get_signal_level(percent)
                    
                    # Position from last position
                    telegram = latest.get("telegram", {})
                    if telegram:
                        result["latitude"] = telegram.get("latitude")
                        result["longitude"] = telegram.get("longitude")
                    
                        # Update timestamp
                        if telegram.get("timeDb"):
                            result["last_update"] = telegram["timeDb"]
                    
        except Exception as err:
            _LOGGER.warning("Failed to get FIFO data for %s: %s", device_id, err)
            
            # Fallback to device's lastRssi if available
            last_rssi = device.get("lastRssi", 0)
            if last_rssi:
                dbm = format_rssi(last_rssi)
                percent = rssi_to_percent(dbm)
                result["rssi_raw"] = last_rssi
                result["rssi_dbm"] = dbm
                result["signal_percent"] = percent
                result["signal_level"] = get_signal_level(percent)
        
        return result

    async def get_all_device_data(self) -> dict[str, dict[str, Any]]:
        """Get all data for all devices."""
        devices = await self.get_devices()
        all_data = {}
        
        for device in devices:
            device_id = str(device.get("id"))
            try:
                device_data = await self.get_device_data(device_id)
                all_data[device_id] = device_data
            except Exception as err:
                _LOGGER.error("Failed to get data for device %s: %s", device_id, err)
        
        return all_data

    def register_callback(self, callback: Callable[[dict[str, Any]], None]) -> None:
        """Register a callback for real-time updates."""
        self._callbacks.append(callback)

    def unregister_callback(self, callback: Callable[[dict[str, Any]], None]) -> None:
        """Unregister a callback."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def _notify_callbacks(self, data: dict[str, Any]) -> None:
        """Notify all registered callbacks."""
        for callback in self._callbacks:
            try:
                callback(data)
            except Exception as err:
                _LOGGER.error("Callback error: %s", err)
