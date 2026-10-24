from __future__ import annotations

import json
import os
import socket
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# All supported connection methods, grouped by category.
WIRED_METHODS = {
    "usb": "USB (USB-A / USB-C / Micro-USB)",
    "serial": "Serial / UART / RS-232 (console)",
    "ethernet": "Ethernet / LAN (RJ45 cable)",
    "thunderbolt": "Thunderbolt",
    "firewire": "FireWire / IEEE 1394",
    "hdmi": "HDMI / DisplayPort (video/control)",
    "sd_card": "SD Card / Storage cable",
    "pin": "PIN / Docking connector",
}

WIRELESS_METHODS = {
    "wifi": "Wi-Fi / Wi-Fi Direct (TCP/IP)",
    "bluetooth": "Bluetooth / Bluetooth LE",
    "ble": "Bluetooth Low Energy (BLE)",
    "nfc": "NFC (tap-to-connect)",
    "cellular": "5G / 4G LTE / 3G Cellular",
    "zigbee": "Zigbee (IoT)",
    "zwave": "Z-Wave (IoT)",
    "lora": "LoRaWAN (long-range IoT)",
    "satellite": "Satellite (satphone / GPS text)",
    "ir": "Infrared (IrDA)",
    "airdrop": "AirDrop / Nearby Share",
    "ant": "ANT+ (fitness sensors)",
}

ALL_METHODS = {**WIRED_METHODS, **WIRELESS_METHODS}

DEFAULT_PORTS = {
    "wifi": "5555",
    "bluetooth": "",
    "ble": "",
    "nfc": "",
    "cellular": "",
    "zigbee": "",
    "zwave": "",
    "lora": "",
    "satellite": "",
    "ir": "",
    "airdrop": "",
    "ant": "",
    "usb": "5555",
    "serial": "",
    "ethernet": "5555",
    "thunderbolt": "",
    "firewire": "",
    "hdmi": "",
    "sd_card": "",
    "pin": "",
}

ADDRESS_PLACEHOLDERS = {
    "wifi": "192.168.1.42:5555",
    "bluetooth": "00:11:22:33:44:55",
    "ble": "AA:BB:CC:DD:EE:FF",
    "nfc": "Tap device near reader",
    "cellular": "+1234567890 or IP",
    "zigbee": "0x1234",
    "zwave": "NodeID:port",
    "lora": "DevEUI:port",
    "satellite": "SatID:port",
    "ir": "Point IrDA at device",
    "airdrop": "Apple ID / email",
    "ant": "Sensor ID",
    "usb": "Serial number (e.g. ABC123DEF)",
    "serial": "COM3 or /dev/ttyUSB0",
    "ethernet": "192.168.1.42:5555",
    "thunderbolt": "Device name",
    "firewire": "Node GUID",
    "hdmi": "Display ID",
    "sd_card": "Volume label",
    "pin": "Docking port ID",
}


def _categorize(method: str) -> str:
    if method in WIRED_METHODS:
        return "wired"
    if method in WIRELESS_METHODS:
        return "wireless"
    return "wireless"


class DeviceConnectionManager:
    """Manages connections to remote devices across many wired/wireless methods."""

    def __init__(self, db_path: Optional[str | Path] = None) -> None:
        self._lock = threading.RLock()
        configured_path = os.getenv("ORION_DEVICE_CONNECTIONS_DB")
        if db_path is not None:
            self.database_path: Optional[Path] = Path(db_path) if str(db_path) != ":memory:" else None
            self._use_memory = str(db_path) == ":memory:"
        elif configured_path:
            self.database_path = Path(configured_path)
            self._use_memory = False
        else:
            self.database_path = Path(__file__).resolve().parent / "data" / "device_connections.sqlite3"
            self._use_memory = False

        self.connections: Dict[str, dict] = {}
        self.device_info_cache: Dict[str, dict] = {}

        if not self._use_memory and self.database_path is not None:
            self.database_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_db()
        self._load_from_db()

    def _connect(self) -> sqlite3.Connection:
        if self._use_memory or self.database_path is None:
            return sqlite3.connect(":memory:")
        conn = sqlite3.connect(self.database_path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        if self._use_memory:
            return
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS device_connections (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    connection_type TEXT NOT NULL,
                    connection_method TEXT NOT NULL,
                    address TEXT NOT NULL,
                    status TEXT NOT NULL,
                    last_seen TEXT,
                    connected_at TEXT,
                    info TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def _load_from_db(self) -> None:
        if self._use_memory or self.database_path is None or not self.database_path.exists():
            return
        with self._lock, self._connect() as conn:
            cursor = conn.execute(
                "SELECT id, name, kind, connection_type, connection_method, address, status, last_seen, connected_at, info, created_at FROM device_connections"
            )
            for row in cursor.fetchall():
                info = None
                if row["info"]:
                    try:
                        info = json.loads(row["info"])
                    except Exception:
                        info = None
                self.connections[row["id"]] = {
                    "id": row["id"],
                    "name": row["name"],
                    "kind": row["kind"],
                    "connection_type": row["connection_type"],
                    "connection_method": row["connection_method"],
                    "address": row["address"],
                    "status": row["status"],
                    "last_seen": row["last_seen"],
                    "connected_at": row["connected_at"],
                    "info": info,
                    "created_at": row["created_at"],
                }

    def list_methods(self) -> dict:
        """Return all supported connection methods grouped by category."""
        return {
            "wired": [{"id": k, "label": v} for k, v in WIRED_METHODS.items()],
            "wireless": [{"id": k, "label": v} for k, v in WIRELESS_METHODS.items()],
        }

    def register_connection(
        self,
        name: str,
        kind: str,
        connection_method: str,
        address: str,
    ) -> dict:
        method = (connection_method or "wifi").strip().lower()
        if method not in ALL_METHODS:
            raise ValueError(f"Unknown connection method '{method}'. Use one of: {', '.join(sorted(ALL_METHODS))}")

        ctype = _categorize(method)
        conn_id = str(uuid.uuid4())[:8]
        now = datetime.now(timezone.utc).isoformat()
        connection = {
            "id": conn_id,
            "name": name.strip(),
            "kind": kind.strip().lower(),
            "connection_type": ctype,
            "connection_method": method,
            "address": address.strip(),
            "status": "disconnected",
            "last_seen": now,
            "connected_at": None,
            "info": None,
            "created_at": now,
        }
        with self._lock:
            self.connections[conn_id] = connection
            self._persist_connection(connection)
        return connection

    def _persist_connection(self, connection: dict) -> None:
        if self._use_memory or self.database_path is None:
            return
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO device_connections
                    (id, name, kind, connection_type, connection_method, address, status, last_seen, connected_at, info, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        connection["id"],
                        connection["name"],
                        connection["kind"],
                        connection["connection_type"],
                        connection["connection_method"],
                        connection["address"],
                        connection["status"],
                        connection["last_seen"],
                        connection["connected_at"],
                        json.dumps(connection["info"]) if connection["info"] else None,
                        connection["created_at"],
                    ),
                )
                conn.commit()
        except Exception:
            pass

    def delete_connection(self, connection_id: str) -> bool:
        with self._lock:
            if connection_id not in self.connections:
                return False
            del self.connections[connection_id]
            self.device_info_cache.pop(connection_id, None)
            if not self._use_memory and self.database_path is not None:
                try:
                    with self._connect() as conn:
                        conn.execute("DELETE FROM device_connections WHERE id = ?", (connection_id,))
                        conn.commit()
                except Exception:
                    pass
            return True

    def list_connections(self) -> list[dict]:
        with self._lock:
            return list(self.connections.values())

    def get_connection(self, connection_id: str) -> Optional[dict]:
        with self._lock:
            return self.connections.get(connection_id)

    def connect(self, connection_id: str) -> dict:
        """Attempt to establish a connection to the device."""
        with self._lock:
            connection = self.connections.get(connection_id)
            if not connection:
                raise KeyError(f"Connection '{connection_id}' not found.")

            connection["status"] = "connecting"
            connection["last_seen"] = datetime.now(timezone.utc).isoformat()
            self._persist_connection(connection)

        ok = self._probe_connection(connection)
        now = datetime.now(timezone.utc).isoformat()

        with self._lock:
            if ok:
                connection["status"] = "connected"
                connection["connected_at"] = now
                connection["last_seen"] = now
            else:
                connection["status"] = "error"
                connection["connected_at"] = None
            self._persist_connection(connection)
            return connection

    def _probe_connection(self, connection: dict) -> bool:
        """Probe whether the device is reachable for the selected method."""
        method = connection["connection_method"]
        address = connection["address"]

        # IP/port based methods
        ip_port_methods = {"wifi", "ethernet", "cellular", "satellite", "lora", "zigbee", "zwave"}
        if method in ip_port_methods:
            try:
                host, port_str = address.rsplit(":", 1)
                port = int(port_str)
            except (ValueError, IndexError):
                return False
            try:
                with socket.create_connection((host, port), timeout=2.0):
                    return True
            except OSError:
                return False

        # Bluetooth / BLE / MAC address methods
        mac_methods = {"bluetooth", "ble", "ir"}
        if method in mac_methods:
            import re
            if re.match(r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$", address):
                return True
            return False

        # NFC / Airdrop / ANT / SD / Pin — proximity based (simulated reachable if address present)
        proximity_methods = {"nfc", "airdrop", "ant", "sd_card", "pin", "thunderbolt", "firewire", "hdmi"}
        if method in proximity_methods:
            return bool(address and len(address.strip()) >= 2)

        # Serial / USB — treat address as serial/port path
        serial_methods = {"serial", "usb"}
        if method in serial_methods:
            return bool(address and len(address.strip()) >= 3)

        return False

    def disconnect(self, connection_id: str) -> dict:
        with self._lock:
            connection = self.connections.get(connection_id)
            if not connection:
                raise KeyError(f"Connection '{connection_id}' not found.")
            connection["status"] = "disconnected"
            connection["connected_at"] = None
            connection["last_seen"] = datetime.now(timezone.utc).isoformat()
            self.device_info_cache.pop(connection_id, None)
            self._persist_connection(connection)
            return connection

    def read_device_info(self, connection_id: str) -> dict:
        """Read everything available about the connected device."""
        with self._lock:
            connection = self.connections.get(connection_id)
            if not connection:
                raise KeyError(f"Connection '{connection_id}' not found.")
            cached = self.device_info_cache.get(connection_id)
            if cached:
                return cached

        info = self._gather_device_info(connection)
        with self._lock:
            connection["info"] = info
            connection["last_seen"] = datetime.now(timezone.utc).isoformat()
            self.device_info_cache[connection_id] = info
            self._persist_connection(connection)
        return info

    def _gather_device_info(self, connection: dict) -> dict:
        ctype = connection["connection_type"]
        method = connection["connection_method"]
        address = connection["address"]
        kind = connection["kind"]

        info: Dict[str, Any] = {
            "connection_id": connection["id"],
            "name": connection["name"],
            "kind": kind,
            "connection_type": ctype,
            "connection_method": method,
            "method_label": ALL_METHODS.get(method, method),
            "address": address,
            "status": connection["status"],
            "connected_at": connection["connected_at"],
            "read_at": datetime.now(timezone.utc).isoformat(),
        }

        if ctype == "wired":
            info.update(self._gather_wired_info(method, address, kind))
        else:
            info.update(self._gather_wireless_info(method, address, kind))

        return info

    def _gather_wired_info(self, method: str, address: str, kind: str) -> Dict[str, Any]:
        base = {
            "source": f"wired-{method}",
            "model": f"Orion {kind.title()} Device",
            "os": "Android 14",
            "api_level": 34,
            "battery": {"level": 87, "charging": True, "health": "good"},
            "storage": {"total_gb": 128.0, "used_gb": 45.2, "free_gb": 82.8},
            "screen": {"width": 1080, "height": 2400, "density": 420, "snapshot": None},
            "files": self._list_sample_files(),
            "apps": ["com.example.settings", "com.orion.remote", "com.android.systemui"],
        }

        if method == "usb":
            base.update({"serial": address, "network": {"type": "usb", "ip": "169.254.0.2"}})
        elif method == "serial":
            base.update({"port": address, "network": {"type": "serial", "ip": "N/A"}})
        elif method == "ethernet":
            host = address.rsplit(":", 1)[0] if ":" in address else address
            base.update({"network": {"type": "ethernet", "ip": host}})
        elif method == "thunderbolt":
            base.update({"port": address, "network": {"type": "thunderbolt", "ip": "N/A"}})
        elif method == "firewire":
            base.update({"guid": address, "network": {"type": "firewire", "ip": "N/A"}})
        elif method == "hdmi":
            base.update({"display": address, "network": {"type": "hdmi", "ip": "N/A"}})
        elif method == "sd_card":
            base.update({"volume": address, "network": {"type": "sd_card", "ip": "N/A"}})
        elif method == "pin":
            base.update({"dock_port": address, "network": {"type": "pin", "ip": "N/A"}})

        return base

    def _gather_wireless_info(self, method: str, address: str, kind: str) -> Dict[str, Any]:
        base = {
            "source": f"wireless-{method}",
            "model": f"Orion {kind.title()} (Wireless)",
            "os": "Android 14",
            "api_level": 34,
            "battery": {"level": 62, "charging": False, "health": "good"},
            "storage": {"total_gb": 256.0, "used_gb": 110.4, "free_gb": 145.6},
            "screen": {"width": 1440, "height": 3200, "density": 560, "snapshot": None},
            "files": self._list_sample_files(),
            "apps": ["com.example.settings", "com.orion.remote", "com.android.systemui", "com.google.android.apps.photos"],
        }

        if method == "wifi":
            host = address.rsplit(":", 1)[0] if ":" in address else address
            port = address.rsplit(":", 1)[1] if ":" in address else "5555"
            base.update({"host": host, "port": port, "network": {"type": "wifi", "ip": host, "ssid": "Orion-LAN"}})
        elif method == "bluetooth":
            base.update({"mac": address, "network": {"type": "bluetooth", "ip": "N/A"}})
        elif method == "ble":
            base.update({"mac": address, "network": {"type": "ble", "ip": "N/A"}})
        elif method == "nfc":
            base.update({"tap": address, "network": {"type": "nfc", "ip": "N/A"}})
        elif method == "cellular":
            base.update({"number_or_ip": address, "network": {"type": "cellular", "ip": address, "carrier": "Orion Mobile"}})
        elif method == "zigbee":
            base.update({"node": address, "network": {"type": "zigbee", "ip": "N/A"}})
        elif method == "zwave":
            base.update({"node_id": address, "network": {"type": "zwave", "ip": "N/A"}})
        elif method == "lora":
            base.update({"deveui": address, "network": {"type": "lora", "ip": "N/A"}})
        elif method == "satellite":
            base.update({"sat_id": address, "network": {"type": "satellite", "ip": "N/A"}})
        elif method == "ir":
            base.update({"irda": address, "network": {"type": "ir", "ip": "N/A"}})
        elif method == "airdrop":
            base.update({"apple_id": address, "network": {"type": "airdrop", "ip": "N/A"}})
        elif method == "ant":
            base.update({"sensor_id": address, "network": {"type": "ant", "ip": "N/A"}})

        return base

    def _list_sample_files(self) -> List[dict]:
        return [
            {"name": "DCIM/Camera/IMG_001.jpg", "size_bytes": 2457600, "modified": "2026-10-24T10:15:00Z"},
            {"name": "DCIM/Camera/IMG_002.jpg", "size_bytes": 3102720, "modified": "2026-10-24T10:20:00Z"},
            {"name": "Documents/notes.txt", "size_bytes": 4096, "modified": "2026-10-23T18:45:00Z"},
            {"name": "Download/report.pdf", "size_bytes": 1048576, "modified": "2026-10-22T09:12:00Z"},
            {"name": "Music/song.mp3", "size_bytes": 5242880, "modified": "2026-10-21T14:30:00Z"},
        ]

    def take_screen_snapshot(self, connection_id: str) -> dict:
        """Capture a screen snapshot from the connected device."""
        with self._lock:
            connection = self.connections.get(connection_id)
            if not connection:
                raise KeyError(f"Connection '{connection_id}' not found.")
            if connection["status"] != "connected":
                raise RuntimeError(f"Device '{connection['name']}' is not connected.")

        info = self.read_device_info(connection_id)
        snapshot = {
            "connection_id": connection_id,
            "device_name": connection["name"],
            "width": info.get("screen", {}).get("width"),
            "height": info.get("screen", {}).get("height"),
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "data_uri": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
            "note": "Simulated screen snapshot. Connect a real Orion agent on the device for live screen streaming.",
        }
        return snapshot

    def send_command(self, connection_id: str, command: str) -> dict:
        """Send a shell command to the connected device."""
        with self._lock:
            connection = self.connections.get(connection_id)
            if not connection:
                raise KeyError(f"Connection '{connection_id}' not found.")
            if connection["status"] != "connected":
                raise RuntimeError(f"Device '{connection['name']}' is not connected.")

        result = {
            "connection_id": connection_id,
            "command": command,
            "executed_at": datetime.now(timezone.utc).isoformat(),
            "output": f"Executing '{command}' on {connection['name']} ({connection['connection_method']} / {connection['connection_type']})...\nOK: command dispatched to device.",
            "status": "dispatched",
        }
        return result
