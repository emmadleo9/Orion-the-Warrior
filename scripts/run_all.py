"""Run Orion backend + OpenWA vendor service together (dev convenience)."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENDOR = ROOT / "vendor" / "open-wa"


def run_backend() -> subprocess.Popen:
    env = os.environ.copy()
    env.setdefault("HOST", "0.0.0.0")
    env.setdefault("PORT", "8000")
    return subprocess.Popen(
        [sys.executable, "main.py"], cwd=ROOT, env=env
    )


def run_openwa() -> subprocess.Popen | None:
    compose = VENDOR / "docker-compose.yml"
    dockerfile = VENDOR / "Dockerfile"
    if not compose.exists() and not dockerfile.exists():
        print("[run_all] No OpenWA compose/Dockerfile found; skipping OpenWA service.")
        return None
    if compose.exists():
        return subprocess.Popen(["docker", "compose", "up"], cwd=VENDOR)
    return subprocess.Popen(
        ["docker", "build", "-t", "open-wa", "."], cwd=VENDOR
    )


def main() -> int:
    procs: list[subprocess.Popen] = []
    try:
        openwa = run_openwa()
        if openwa:
            procs.append(openwa)
            time.sleep(3)
        backend = run_backend()
        procs.append(backend)
        for p in procs:
            p.wait()
    except KeyboardInterrupt:
        pass
    finally:
        for p in procs:
            p.terminate()
        for p in procs:
            try:
                p.wait(timeout=5)
            except Exception:
                p.kill()
    return 0


if __name__ == "__main__":
    sys.exit(main())
