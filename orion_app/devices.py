from __future__ import annotations

import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional


class DeviceManager:
    """
    Manages registered devices and queued tasks with SQLite persistence
    and in-memory thread-safe caching.
    """

    def __init__(self, db_path: Optional[str | Path] = None) -> None:
        self._lock = threading.RLock()
        configured_path = os.getenv("ORION_DEVICES_DB")
        if db_path is not None:
            self.database_path: Optional[Path] = Path(db_path) if str(db_path) != ":memory:" else None
            self._use_memory = str(db_path) == ":memory:"
        elif configured_path:
            self.database_path = Path(configured_path)
            self._use_memory = False
        else:
            self.database_path = Path(__file__).resolve().parent / "data" / "devices.sqlite3"
            self._use_memory = False

        self.devices: Dict[str, dict] = {}
        self.tasks: List[dict] = []

        if not self._use_memory and self.database_path is not None:
            self.database_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_db()
        self._load_from_db()
        if not self.devices:
            self._bootstrap_defaults()

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
                CREATE TABLE IF NOT EXISTS devices (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    status TEXT NOT NULL,
                    last_seen TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS device_tasks (
                    id TEXT PRIMARY KEY,
                    device_id TEXT NOT NULL,
                    task TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    completed_at TEXT
                )
                """
            )
            conn.commit()

    def _load_from_db(self) -> None:
        if self._use_memory or self.database_path is None or not self.database_path.exists():
            return
        with self._lock, self._connect() as conn:
            cursor = conn.execute("SELECT id, name, kind, status, last_seen, created_at FROM devices")
            for row in cursor.fetchall():
                self.devices[row["id"]] = {
                    "id": row["id"],
                    "name": row["name"],
                    "kind": row["kind"],
                    "status": row["status"],
                    "last_seen": row["last_seen"],
                    "created_at": row["created_at"],
                }

            task_cursor = conn.execute(
                "SELECT id, device_id, task, status, created_at, completed_at FROM device_tasks ORDER BY created_at ASC"
            )
            self.tasks = [
                {
                    "id": row["id"],
                    "device_id": row["device_id"],
                    "task": row["task"],
                    "status": row["status"],
                    "created_at": row["created_at"],
                    "completed_at": row["completed_at"],
                }
                for row in task_cursor.fetchall()
            ]

    def _bootstrap_defaults(self) -> None:
        self.register_device("phone-master", "phone")
        self.register_device("laptop-one", "desktop")
        self.register_device("tablet-hub", "tablet")

    def register_device(self, name: str, kind: str) -> dict:
        device_id = str(uuid.uuid4())[:8]
        now = datetime.now(timezone.utc).isoformat()
        device = {
            "id": device_id,
            "name": name.strip(),
            "kind": kind.strip().lower(),
            "status": "online",
            "last_seen": now,
            "created_at": now,
        }
        with self._lock:
            self.devices[device_id] = device
            if not self._use_memory and self.database_path is not None:
                try:
                    with self._connect() as conn:
                        conn.execute(
                            "INSERT OR REPLACE INTO devices (id, name, kind, status, last_seen, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                            (device["id"], device["name"], device["kind"], device["status"], device["last_seen"], device["created_at"]),
                        )
                        conn.commit()
                except Exception:
                    pass
        return device

    def ping_device(self, device_id: str) -> dict:
        with self._lock:
            device = self.devices.get(device_id)
            if not device:
                raise KeyError(f"Device '{device_id}' not found.")
            now = datetime.now(timezone.utc).isoformat()
            device["status"] = "online"
            device["last_seen"] = now
            if not self._use_memory and self.database_path is not None:
                try:
                    with self._connect() as conn:
                        conn.execute(
                            "UPDATE devices SET status = ?, last_seen = ? WHERE id = ?",
                            (device["status"], device["last_seen"], device_id),
                        )
                        conn.commit()
                except Exception:
                    pass
            return device

    def delete_device(self, device_id: str) -> bool:
        with self._lock:
            if device_id not in self.devices:
                return False
            del self.devices[device_id]
            self.tasks = [t for t in self.tasks if t["device_id"] != device_id]
            if not self._use_memory and self.database_path is not None:
                try:
                    with self._connect() as conn:
                        conn.execute("DELETE FROM devices WHERE id = ?", (device_id,))
                        conn.execute("DELETE FROM device_tasks WHERE device_id = ?", (device_id,))
                        conn.commit()
                except Exception:
                    pass
            return True

    def enqueue_task(self, device_id: str, task: str) -> dict:
        task_id = str(uuid.uuid4())[:8]
        now = datetime.now(timezone.utc).isoformat()
        task_record = {
            "id": task_id,
            "device_id": device_id,
            "task": task.strip(),
            "status": "queued",
            "created_at": now,
            "completed_at": None,
        }
        with self._lock:
            self.tasks.append(task_record)
            if not self._use_memory and self.database_path is not None:
                try:
                    with self._connect() as conn:
                        conn.execute(
                            "INSERT INTO device_tasks (id, device_id, task, status, created_at, completed_at) VALUES (?, ?, ?, ?, ?, ?)",
                            (task_record["id"], task_record["device_id"], task_record["task"], task_record["status"], task_record["created_at"], None),
                        )
                        conn.commit()
                except Exception:
                    pass
        return task_record

    def update_task_status(self, task_id: str, status: str) -> dict:
        valid_statuses = {"queued", "in_progress", "completed", "failed", "cancelled"}
        if status not in valid_statuses:
            raise ValueError(f"Invalid status '{status}'. Must be one of: {', '.join(sorted(valid_statuses))}")

        with self._lock:
            for task in self.tasks:
                if task["id"] == task_id:
                    task["status"] = status
                    if status in {"completed", "failed", "cancelled"}:
                        task["completed_at"] = datetime.now(timezone.utc).isoformat()
                    if not self._use_memory and self.database_path is not None:
                        try:
                            with self._connect() as conn:
                                conn.execute(
                                    "UPDATE device_tasks SET status = ?, completed_at = ? WHERE id = ?",
                                    (task["status"], task["completed_at"], task_id),
                                )
                                conn.commit()
                        except Exception:
                            pass
                    return task
            raise KeyError(f"Task '{task_id}' not found.")

    def delete_task(self, task_id: str) -> bool:
        with self._lock:
            initial_count = len(self.tasks)
            self.tasks = [t for t in self.tasks if t["id"] != task_id]
            found = len(self.tasks) < initial_count
            if found and not self._use_memory and self.database_path is not None:
                try:
                    with self._connect() as conn:
                        conn.execute("DELETE FROM device_tasks WHERE id = ?", (task_id,))
                        conn.commit()
                except Exception:
                    pass
            return found

    def list_devices(self) -> list[dict]:
        with self._lock:
            return list(self.devices.values())

    def list_tasks(self) -> list[dict]:
        with self._lock:
            return list(self.tasks)
