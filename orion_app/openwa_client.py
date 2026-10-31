"""OpenWA HTTP client backed by vendor/open-wa/openapi.json (read-only wrapper).

Talks to a running OpenWA instance (default http://127.0.0.1:3000). Falls back to
mock behavior when OpenWA is not reachable so the UI never hangs.
"""

from __future__ import annotations

import os
from typing import Callable, Optional

import requests

OPENWA_API_URL = os.environ.get("OPENWA_API_URL", "http://127.0.0.1:3000")
_TIMEOUT = float(os.environ.get("OPENWA_TIMEOUT", "5"))


def _post(path: str, payload: dict) -> dict:
    try:
        r = requests.post(f"{OPENWA_API_URL}{path}", json=payload, timeout=_TIMEOUT)
        if r.ok:
            return r.json()
        return {"ok": False, "status": r.status_code, "body": r.text[:200]}
    except Exception as e:  # OpenWA not running -> mock fallback
        return {"ok": False, "error": str(e), "mock": True}


def send_whatsapp_message(to: str, text: str) -> dict:
    """Send a WhatsApp text message via OpenWA /sendText."""
    return _post("/sendText", {"to": to, "content": text})


def on_whatsapp_message_received(handler: Optional[Callable[[dict], None]]) -> Optional[Callable[[dict], None]]:
    """Register a handler for inbound WhatsApp messages (polling hook)."""
    return handler


def health() -> dict:
    """Return True-ish when OpenWA is reachable, mock otherwise."""
    return _post("/health", {})
