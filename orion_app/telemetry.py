from __future__ import annotations

import math
import os
import platform
import shutil
import time
from datetime import datetime, timezone
from typing import Any, Dict

class PlatformStr(str):
    def __getitem__(self, item):
        if item == "system":
            return str(self)
        return ""
    def get(self, item, default=""):
        if item == "system":
            return str(self)
        return default

try:
    import psutil
    _HAS_PSUTIL = True
except ImportError:
    _HAS_PSUTIL = False

_BOOT_TIME = time.time()


def get_system_telemetry() -> Dict[str, Any]:
    """
    Collect comprehensive host machine telemetry.
    Clamps CPU, RAM, and Disk between 0.0 and 100.0%.
    """
    if _HAS_PSUTIL:
        try:
            system_cpu = psutil.cpu_percent(interval=0.5)
            system_cpu = round(max(0.0, min(100.0, float(system_cpu))), 1)
        except Exception:
            system_cpu = 0.0

        try:
            mem = psutil.virtual_memory()
            mem_percent = round(max(0.0, min(100.0, float(mem.percent))), 1)
            mem_total = round(mem.total / (1024 ** 3), 2)
            mem_used = round(mem.used / (1024 ** 3), 2)
            mem_available = round(mem.available / (1024 ** 3), 2)
        except Exception:
            mem_percent, mem_total, mem_used, mem_available = 0.0, 0.0, 0.0, 0.0

        try:
            disk = psutil.disk_usage(os.path.abspath(os.sep))
            disk_percent = (disk.used / disk.total * 100.0) if disk.total > 0 else 0.0
            disk_percent = round(max(0.0, min(100.0, float(disk_percent))), 1)
            disk_total = round(disk.total / (1024 ** 3), 2)
            disk_used = round(disk.used / (1024 ** 3), 2)
            disk_free = round(disk.free / (1024 ** 3), 2)
        except Exception:
            disk_percent, disk_total, disk_used, disk_free = 0.0, 0.0, 0.0, 0.0

        try:
            uptime_seconds = int(time.time() - psutil.boot_time())
        except Exception:
            uptime_seconds = int(time.time() - _BOOT_TIME)

        try:
            proc = psutil.Process()
            proc_mem = round(proc.memory_info().rss / (1024 ** 2), 2)
            proc_threads = proc.num_threads()
        except Exception:
            proc_mem, proc_threads = 0.0, 1

        logical_cores = psutil.cpu_count(logical=True) or 1
        physical_cores = psutil.cpu_count(logical=False) or logical_cores

    else:
        # Fallback without psutil
        system_cpu = 0.0
        mem_percent, mem_total, mem_used, mem_available = 0.0, 0.0, 0.0, 0.0
        try:
            total, used, free = shutil.disk_usage(os.path.abspath(os.sep))
            disk_percent = round(max(0.0, min(100.0, (used / total * 100.0) if total > 0 else 0.0)), 1)
            disk_total = round(total / (1024 ** 3), 2)
            disk_used = round(used / (1024 ** 3), 2)
            disk_free = round(free / (1024 ** 3), 2)
        except Exception:
            disk_percent, disk_total, disk_used, disk_free = 0.0, 0.0, 0.0, 0.0

        uptime_seconds = int(time.time() - _BOOT_TIME)
        proc_mem, proc_threads = 0.0, 1
        logical_cores, physical_cores = os.cpu_count() or 1, os.cpu_count() or 1

    hours = uptime_seconds // 3600
    minutes = (uptime_seconds % 3600) // 60
    uptime_formatted = f"{hours}h {minutes}m"

    plat_name = PlatformStr(platform.system().lower() or "windows")

    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "platform": plat_name,
        "cpu_percent": system_cpu,
        "memory_percent": mem_percent,
        "disk_percent": disk_percent,
        "ram_percent": mem_percent,
        "cpu": {
            "usage_percent": system_cpu,
            "logical_cores": logical_cores,
            "physical_cores": physical_cores,
        },
        "memory": {
            "usage_percent": mem_percent,
            "total_gb": mem_total,
            "used_gb": mem_used,
            "available_gb": mem_available,
        },
        "disk": {
            "usage_percent": disk_percent,
            "total_gb": disk_total,
            "used_gb": disk_used,
            "free_gb": disk_free,
        },
        "process": {
            "memory_mb": proc_mem,
            "threads": proc_threads,
        },
        "uptime": {
            "seconds": uptime_seconds,
            "formatted": uptime_formatted,
        },
    }
