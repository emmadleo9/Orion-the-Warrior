from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List
import uuid


class DeviceManager:
    def __init__(self) -> None:
        self.devices: Dict[str, dict] = {}
        self.tasks: List[dict] = []
        self._bootstrap_defaults()

    def _bootstrap_defaults(self) -> None:
        self.register_device("phone-master", "phone")
        self.register_device("laptop-one", "desktop")
        self.register_device("tablet-hub", "tablet")

    def register_device(self, name: str, kind: str) -> dict:
        device_id = str(uuid.uuid4())[:8]
        device = {
            "id": device_id,
            "name": name,
            "kind": kind,
            "status": "online",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self.devices[device_id] = device
        return device

    def enqueue_task(self, device_id: str, task: str) -> dict:
        task_record = {
            "id": str(uuid.uuid4())[:8],
            "device_id": device_id,
            "task": task,
            "status": "queued",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self.tasks.append(task_record)
        return task_record

    def list_devices(self) -> list[dict]:
        return list(self.devices.values())

    def list_tasks(self) -> list[dict]:
        return list(self.tasks)
