"""PetTracer API client."""
from __future__ import annotations

import asyncio
import json
import logging
import random
import re
from datetime import datetime, timedelta
from typing import Any, Callable

import aiohttp
import websockets

from .const import (
    API_URL,
    WEBSOCKET_URL,
    ENDPOINT_LOGIN,
    ENDPOINT_CAT_COLLARS,
    ENDPOINT_CC_INFO,
    STOMP_QUEUE_MESSAGES,
    STOMP_QUEUE_PORTAL,
    ENDPOINT_HOME_STATIONS
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
        self._home_stations: dict[str, dict[str, Any]] = {}
        self._callbacks: list[Callable[[dict[str, Any]], None]] = []
        
        # WebSocket/SockJS/STOMP connection
        self._ws: websockets.WebSocketClientProtocol | None = None
        self._ws_task: asyncio.Task | None = None
        self._ws_running = False
        self._stomp_session_id: str | None = None

    async def _ensure_session(self) -> aiohttp.ClientSession:
        """Ensure we have an aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
            self._own_session = True
        return self._session

    async def close(self) -> None:
        """Close the session and WebSocket connection."""
        await self.disconnect_websocket()
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
                    raise PetTracerApiError(f"Failed to get cat collars info: {response.status}")

                self._user_data = await response.json()
                return self._user_data
        except Exception as e:
            _LOGGER.debug(f"Error {e}")
            raise PetTracerApiError(f"Failure to retrieve collars")

    async def get_home_stations_api(self) -> dict[str, Any]:
        """Get home stations info."""
        await self._ensure_authenticated()
        session = await self._ensure_session()

        try:
            async with session.get(
                    f"{API_URL}{ENDPOINT_HOME_STATIONS}",
                    headers=self._get_auth_headers(),
            ) as response:
                if response.status != 200:
                    _LOGGER.debug(f"Error {response}")
                    raise PetTracerApiError(f"Failed to get home station info: {response.status}")

                self._home_station_data = await response.json()
                return self._home_station_data
        except Exception as e:
            _LOGGER.debug(f"Error {e}")
            raise PetTracerApiError(f"Failure to retrieve home stations")

    async def get_home_stations(self) -> list[dict[str, Any]]:
        """Get list of home stations (command centers/trackers)."""
        home_stations = await self.get_home_stations_api()

        _LOGGER.debug(f"Home stations found {home_stations}")

        # Update local device cache
        for home_station in home_stations:
            home_station_id = str(home_station.get("id"))
            self._home_stations[home_station_id] = home_station

        return home_stations

    async def get_home_station_data(self, home_station_id: str, use_cache_only: bool = False) -> dict[str, Any]:
        """Get all data for a device including signal and location.

        Args:
            device_id: The device ID to get data for
            use_cache_only: If True, only use cached data without making API calls.
                           This is used for WebSocket updates where data is already fresh.
        """
        home_station = self._home_stations.get(home_station_id, {})

        result = {
            "device_id": home_station_id,
            "name": f"Home station {home_station_id}",
            "battery": 0,
            "hw": None,
            "sw": None,
            "flags": "none",
            "last_update": None,
            "rssi": 0,
            "status": None,
            "type": None,
            "wifi_ssid": None
        }

        if home_station.get("bat") is not None:
            result["battery"] = home_station.get("bat")

        if home_station.get("flags") is not None:
                result["flags"] = home_station.get("flags")

        if home_station.get("hw") is not None:
            result["hw"] = home_station.get("hw")

        if home_station.get("lastContact") is not None:
            result["last_update"] = home_station.get("lastContact")

        if home_station.get("rssi") is not None:
            result["rssi"] = home_station.get("rssi")

        if home_station.get("status") is not None:
            result["status"] = home_station.get("status")

        if home_station.get("sw") is not None:
            result["sw"] = home_station.get("sw")

        if home_station.get("type") is not None:
            result["type"] = home_station.get("type")

        if home_station.get("wlanSsid") is not None:
            result["wifi_ssid"] = home_station.get("wlanSsid")

        return result

    async def get_all_home_station_data(self) -> dict[str, dict[str, Any]]:
        """Get all data for all home stations."""
        home_station = await self.get_home_stations()
        all_data = {}

        for home_statio in home_station:

            home_station_id = str(home_statio.get("id"))
            try:
                home_station_data = await self.get_home_station_data(home_station_id)
                all_data[home_station_id] = home_station_data
            except Exception as err:
                _LOGGER.exception("Failed to get data for home station %s: %s", home_station_id, err)

        return all_data

    async def get_devices(self) -> list[dict[str, Any]]:
        """Get list of devices (command centers/trackers)."""
        collars = await self.get_cat_collars()

        _LOGGER.debug(f"Collars found {collars}")
        
        # Update local device cache
        for collar in collars:
            collar_id = str(collar.get("id"))
            self._devices[collar_id] = collar
        
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


    
    async def get_device_data(self, device_id: str, use_cache_only: bool = False) -> dict[str, Any]:
        """Get all data for a device including signal and location.

        Args:
            device_id: The device ID to get data for
            use_cache_only: If True, only use cached data without making API calls.
                           This is used for WebSocket updates where data is already fresh.
        """
        device = self._devices.get(device_id, {})

        device_name = device.get("details", {}).get("name", f"Tracker {device_id}")


        """
            set leds: setCatCollarLEDUrl
            set buz: setCatCollarBuzUrl
            set collar mode: setCatCollarModeUrl
                    JSON.stringify({
                        devType: 0,
                        devId: e,
                        cmdNr: t
                    }
            position quality: fixP and fixS
             
            turn off the collar : https://portal.pettracer.com/api/map/setccmode
                {"devType":0,"devId":23712,"cmdNr":12}

        
        
        """
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
            "hw": None,
            "sw": None,
            "buzzer": False,
            "mode": None,
            "mode_set": None,
            "search_mode_duration": None,
            "led_status": False,
            "battery_charging": False,
            "search": False,
            "status": None,
            "home": None,
            "home_since": None,
            "satellites": 0,
            "last_position_flags": None,
            "collar_colour": None


        }

        # Get battery from device data
        if device.get("bat") is not None:
            # batt is a battery level indicator
            result["battery_level"] = device.get("bat")

        # Get location from lastPos
        last_pos = device.get("lastPos")
        if last_pos:
            result["latitude"] = last_pos.get("lat")
            result["longitude"] = last_pos.get("lng")
            result["last_update"] = last_pos.get("timeDb")

        # Get signal from cached lastRssi (updated via WebSocket)
        last_rssi = device.get("lastRssi", 0)
        if last_rssi:
            dbm = format_rssi(last_rssi)
            percent = rssi_to_percent(dbm)
            result["rssi_raw"] = last_rssi
            result["rssi_dbm"] = dbm
            result["signal_percent"] = percent
            result["signal_level"] = get_signal_level(percent)

        if device.get("mode") is not None:
            result["mode"] = device.get("mode")

        if device.get("modeSet") is not None:
            result["mode_set"] = device.get("modeSet")

        if device.get("buz") is not None:
            result["buzzer"] = device.get("buz")

        if device.get("chg") is not None:
            result["battery_charging"] = device.get("chg")

        if device.get("led") is not None:
            result["led_status"] = device.get("led")

        if device.get("search") is not None:
            result["search"] = device.get("search")

        if device.get("status") is not None:
            result["status"] = device.get("status")

        if device.get("home") is not None:
            result["home"] = device.get("home")

        if device.get("homeSince") is not None:
            result["home_since"] = device.get("homeSince")

        if device.get("searchModeDuration") is not None:
            result["search_mode_duration"] = device.get("searchModeDuration")

        if device.get("sw") is not None:
            result["sw"] = device.get("sw")

        if device.get("hw") is not None:
            result["hw"] = device.get("hw")

        if details := device.get("details"):
            result["collar_colour"] = details.get("color", 0)
            result["cat_image"] = details.get("image", None)
            result["cat_birthdate"] = details.get("birth", None)

        # If using cache only (WebSocket update), skip API call
        if use_cache_only:
            _LOGGER.debug("Using cached data only for device %s", device_id)
            return result

        # Get latest FIFO data for most recent signal (only on initial load)
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

                        # Update satellites
                        if telegram.get("sat"):
                            result["satellites"] = telegram["sat"]

                        # Update last position flag
                        if telegram.get("flags"):
                            result["last_position_flags"] = telegram["flags"]






        except Exception as err:
            _LOGGER.warning("Failed to get FIFO data for %s: %s", device_id, err)

            # Already using lastRssi fallback above

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
                _LOGGER.exception("Failed to get data for device %s: %s", device_id, err)
        
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

    async def connect_websocket(self) -> None:
        """Connect to PetTracer SockJS/STOMP WebSocket for real-time updates."""
        if self._ws_running:
            _LOGGER.debug("WebSocket already running")
            return
        
        await self._ensure_authenticated()
        
        self._ws_running = True
        self._ws_task = asyncio.create_task(self._websocket_loop())
        _LOGGER.info("WebSocket connection task started")

    async def disconnect_websocket(self) -> None:
        """Disconnect from WebSocket."""
        self._ws_running = False
        
        if self._ws:
            try:
                await self._ws.close()
            except Exception as err:
                _LOGGER.debug("Error closing WebSocket: %s", err)
            self._ws = None
        
        if self._ws_task:
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass
            self._ws_task = None
        
        _LOGGER.info("WebSocket disconnected")

    async def _websocket_loop(self) -> None:
        """Main WebSocket connection loop with auto-reconnect."""
        reconnect_delay = 5
        max_reconnect_delay = 300  # 5 minutes
        
        while self._ws_running:
            try:
                await self._websocket_handler()
            except asyncio.CancelledError:
                _LOGGER.debug("WebSocket task cancelled")
                break
            except Exception as err:
                _LOGGER.warning(
                    "WebSocket disconnected: %s. Reconnecting in %s seconds...",
                    err,
                    reconnect_delay,
                )
                
                if self._ws_running:
                    await asyncio.sleep(reconnect_delay)
                    reconnect_delay = min(reconnect_delay * 2, max_reconnect_delay)
                else:
                    break
            else:
                reconnect_delay = 5

    async def _websocket_handler(self) -> None:
        """Handle SockJS/STOMP WebSocket connection and messages."""
        # Generate random server ID (3 digits)
        server_id = random.randint(100, 999)
        # Generate random session ID (8 characters)
        session_id = "".join(random.choices("abcdefghijklmnopqrstuvwxyz0123456789", k=8))
        
        # SockJS WebSocket URL: wss://host/sc/{server}/{session}/websocket?access_token=...
        ws_url = f"{WEBSOCKET_URL}/sc/{server_id}/{session_id}/websocket?access_token={self._token}"
        
        _LOGGER.debug("Connecting to SockJS WebSocket: %s", ws_url.replace(self._token, "***"))
        
        async with websockets.connect(ws_url) as websocket:
            self._ws = websocket
            _LOGGER.info("SockJS WebSocket connected")
            
            # SockJS sends open frame: o
            open_frame = await websocket.recv()
            _LOGGER.debug("Received SockJS open frame: %s", open_frame)
            
            if open_frame != "o":
                _LOGGER.warning("Unexpected SockJS open frame: %s", open_frame)
                return
            
            # Send STOMP CONNECT frame
            await self._send_stomp_connect(websocket)
            
            # Listen for messages
            async for message in websocket:
                try:
                    await self._parse_sockjs_message(message)
                except Exception as err:
                    _LOGGER.error("Error parsing message: %s", err)

    async def _send_stomp_connect(self, websocket) -> None:
        """Send STOMP CONNECT frame over SockJS."""
        # STOMP CONNECT frame
        stomp_frame = (
            f"CONNECT\n"
            f"accept-version:1.1,1.0\n"
            f"heart-beat:10000,10000\n"
            f"access_token:{self._token}\n"
            f"\n"
            f"\x00"
        )
        
        _LOGGER.debug(f"SOCKET: connecting {stomp_frame}")
        # Wrap in SockJS send frame: ["..."]
        sockjs_frame = json.dumps([stomp_frame])
        
        _LOGGER.debug("Sending STOMP CONNECT")
        await websocket.send(sockjs_frame)

    async def _send_stomp_subscribe(self, websocket, destination: str, sub_id: str) -> None:
        """Send STOMP SUBSCRIBE frame."""
        stomp_frame = (
            f"SUBSCRIBE\n"
            f"id:{sub_id}\n"
            f"destination:{destination}\n"
            f"ack:auto\n"
            f"\n"
            f"\x00"
        )
        
        _LOGGER.debug(f"SOCKET: sending {stomp_frame}")
        sockjs_frame = json.dumps([stomp_frame])
        
        _LOGGER.debug("Subscribing to %s", destination)
        await websocket.send(sockjs_frame)

    async def _send_app_subscribe(self, websocket) -> None:
        """Send STOMP SEND frame to /app/subscribe with device IDs."""
        # Get device IDs from cached devices
        device_ids = [int(device_id) for device_id in self._devices.keys()]
        
        if not device_ids:
            _LOGGER.warning("No devices to subscribe to")
            return


        
        # Create JSON body
        body = json.dumps({"deviceIds": device_ids})
        
        # STOMP SEND frame with content-length
        stomp_frame = (
            f"SEND\n"
            f"destination:/app/subscribe\n"
            f"content-type:application/json\n"
            f"content-length:{len(body)}\n"
            f"\n"
            f"{body}\x00"
        )

        _LOGGER.debug(f"SOCKET: sending2 {stomp_frame}")
        
        sockjs_frame = json.dumps([stomp_frame])
        
        _LOGGER.info("Sending /app/subscribe with device IDs: %s", device_ids)
        await websocket.send(sockjs_frame)

    async def _parse_sockjs_message(self, raw_message: str) -> None:
        """Parse SockJS frame and extract STOMP messages."""
        _LOGGER.debug("Raw SockJS message: %s", raw_message[:200])
        
        if not raw_message:
            return
        
        frame_type = raw_message[0]
        
        if frame_type == "h":
            # Heartbeat
            _LOGGER.debug("Received heartbeat")
            return
        
        if frame_type == "c":
            # Close frame
            _LOGGER.warning("Received close frame: %s", raw_message)
            return
        
        if frame_type == "a":
            # Array of messages: a["message1","message2"]
            try:
                messages_json = raw_message[1:]  # Remove 'a' prefix
                messages = json.loads(messages_json)
                
                for msg in messages:
                    await self._parse_stomp_frame(msg)
                    
            except json.JSONDecodeError as err:
                _LOGGER.error("Failed to parse SockJS array: %s", err)

    async def _parse_stomp_frame(self, frame_str: str) -> None:
        """Parse STOMP frame and extract message body."""
        _LOGGER.debug("Parsing STOMP frame (first 500 chars): %s", frame_str[:500])
        
        # STOMP frame format:
        # COMMAND\n
        # header1:value1\n
        # header2:value2\n
        # \n
        # body\x00
        
        if not frame_str:
            return
        
        # Check frame type
        if frame_str.startswith("CONNECTED"):
            _LOGGER.info("STOMP CONNECTED")
            # Subscribe to topics after connection
            if self._ws:
                await self._send_stomp_subscribe(self._ws, STOMP_QUEUE_MESSAGES, "sub-0")
                await self._send_stomp_subscribe(self._ws, STOMP_QUEUE_PORTAL, "sub-1")
                
                # Send subscription request to /app/subscribe with device IDs
                await self._send_app_subscribe(self._ws)
            return
        
        if frame_str.startswith("MESSAGE"):
            # Extract JSON body from STOMP MESSAGE frame
            # Find the blank line that separates headers from body
            try:
                # Split into lines
                lines = frame_str.split("\n")
                
                # Find empty line (separates headers from body)
                body_start_idx = None
                for i, line in enumerate(lines):
                    if not line.strip():
                        body_start_idx = i + 1
                        break
                
                if body_start_idx is not None:
                    # Join remaining lines as body
                    body = "\n".join(lines[body_start_idx:])
                    # Remove null terminator
                    body = body.rstrip("\x00")
                    
                    # Parse JSON
                    data = json.loads(body)
                    await self._handle_device_update(data)
                else:
                    _LOGGER.warning("No body found in STOMP MESSAGE")
                    
            except json.JSONDecodeError as err:
                _LOGGER.error("Failed to parse MESSAGE body as JSON: %s", err)
            except Exception as err:
                _LOGGER.error("Error parsing STOMP MESSAGE: %s", err)
        
        elif frame_str.startswith("ERROR"):
            _LOGGER.error("STOMP ERROR: %s", frame_str)

    async def _handle_device_update(self, data: dict[str, Any]) -> None:
        """Handle device update from STOMP message."""
        _LOGGER.debug("Device update received: %s", json.dumps(data, indent=2))
        
        # Extract device ID
        device_id = str(data.get("id", ""))
        
        if not device_id:
            _LOGGER.debug("No device ID in update")
            return
        
        # Update device cache
        if device_id in self._devices:
            device = self._devices[device_id]
            
            # Update location from lastPos
            if "lastPos" in data:
                last_pos = data["lastPos"]
                device["lastPos"] = {
                    "lat": last_pos.get("posLat"),
                    "lng": last_pos.get("posLong"),
                    "timeDb": last_pos.get("timeDb")
                }
                _LOGGER.info("Updated location for device %s", device_id)
            
            # Update signal from lastRssi
            if "lastRssi" in data:
                device["lastRssi"] = data["lastRssi"]
                _LOGGER.info("Updated signal for device %s: %s dBm", device_id, data["lastRssi"])
            
            # Update battery from bat
            if "bat" in data:
                device["bat"] = data["bat"]
                _LOGGER.info("Updated battery for device %s: %s", device_id, data["bat"])
            
            # Update entire FIFO data if present
            if "fiFo" in data:
                device["fifo"] = data["fiFo"]
        
        # Notify callbacks
        self._notify_callbacks({
            "device_id": device_id,
            "update_type": "websocket",
            "data": data,
        })
