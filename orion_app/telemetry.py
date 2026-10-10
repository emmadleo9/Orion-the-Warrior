from __future__ import annotations

import os
import platform
import shutil
import time
from datetime import datetime, timezone
from typing import Any, Dict

try:
    import psutil
    _HAS_PSUTIL = True
except ImportError:
    _HAS_PSUTIL = False

_BOOT_TIME = time.time()


def get_system_telemetry() -> Dict[str, Any]:
    """
    Collect comprehensive host machine telemetry.
    Uses psutil if installed, with resilient standard library fallbacks.
    """
    now = datetime.now(timezone.utc).isoformat()
    telemetry: Dict[str, Any] = {
        "timestamp": now,
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "python_version": platform.python_version(),
            "hostname": platform.node(),
        },
    }

    if _HAS_PSUTIL:
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_count_logical = psutil.cpu_count(logical=True) or 1
            cpu_count_physical = psutil.cpu_count(logical=False) or cpu_count_logical
            telemetry["cpu"] = {
                "usage_percent": round(cpu_percent, 1),
                "logical_cores": cpu_count_logical,
                "physical_cores": cpu_count_physical,
            }
        except Exception:
            telemetry["cpu"] = {"usage_percent": 0.0, "logical_cores": os.cpu_count() or 1, "physical_cores": 1}

        try:
            mem = psutil.virtual_memory()
            telemetry["memory"] = {
                "total_gb": round(mem.total / (1024 ** 3), 2),
                "used_gb": round(mem.used / (1024 ** 3), 2),
                "available_gb": round(mem.available / (1024 ** 3), 2),
                "usage_percent": round(mem.percent, 1),
            }
        except Exception:
            telemetry["memory"] = {"total_gb": 0.0, "used_gb": 0.0, "available_gb": 0.0, "usage_percent": 0.0}

        try:
            disk = psutil.disk_usage(os.path.abspath(os.sep))
            telemetry["disk"] = {
                "total_gb": round(disk.total / (1024 ** 3), 2),
                "used_gb": round(disk.used / (1024 ** 3), 2),
                "free_gb": round(disk.free / (1024 ** 3), 2),
                "usage_percent": round(disk.percent, 1),
            }
        except Exception:
            telemetry["disk"] = {"total_gb": 0.0, "used_gb": 0.0, "free_gb": 0.0, "usage_percent": 0.0}

        try:
            boot_timestamp = psutil.boot_time()
            uptime_seconds = int(time.time() - boot_timestamp)
            hours, remainder = divmod(uptime_seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            telemetry["uptime"] = {
                "seconds": uptime_seconds,
                "formatted": f"{hours}h {minutes}m",
            }
        except Exception:
            uptime_seconds = int(time.time() - _BOOT_TIME)
            hours, remainder = divmod(uptime_seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            telemetry["uptime"] = {
                "seconds": uptime_seconds,
                "formatted": f"{hours}h {minutes}m",
            }

        try:
            proc = psutil.Process()
            proc_mem = proc.memory_info().rss / (1024 ** 2)
            telemetry["process"] = {
                "memory_mb": round(proc_mem, 1),
                "threads": proc.num_threads(),
            }
        except Exception:
            telemetry["process"] = {"memory_mb": 0.0, "threads": 1}
    else:
        # Standard library fallbacks
        cores = os.cpu_count() or 1
        telemetry["cpu"] = {
            "usage_percent": 0.0,
            "logical_cores": cores,
            "physical_cores": cores,
        }
        telemetry["memory"] = {
            "total_gb": 0.0,
            "used_gb": 0.0,
            "available_gb": 0.0,
            "usage_percent": 0.0,
        }
        try:
            total, used, free = shutil.disk_usage(os.path.abspath(os.sep))
            telemetry["disk"] = {
                "total_gb": round(total / (1024 ** 3), 2),
                "used_gb": round(used / (1024 ** 3), 2),
                "free_gb": round(free / (1024 ** 3), 2),
                "usage_percent": round((used / total) * 100, 1) if total > 0 else 0.0,
            }
        except Exception:
            telemetry["disk"] = {"total_gb": 0.0, "used_gb": 0.0, "free_gb": 0.0, "usage_percent": 0.0}

        uptime_seconds = int(time.time() - _BOOT_TIME)
        hours, remainder = divmod(uptime_seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        telemetry["uptime"] = {
            "seconds": uptime_seconds,
            "formatted": f"{hours}h {minutes}m",
        }
        telemetry["process"] = {"memory_mb": 0.0, "threads": 1}

    return telemetry

