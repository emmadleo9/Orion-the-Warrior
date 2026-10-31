"""WhatsApp adapter wrapping vendor/open-wa (read-only)."""

import os
import requests

OPENWA_API_URL = os.environ.get("OPENWA_API_URL", "http://127.0.0.1:3000")


def send_whatsapp_message(to: str, text: str) -> dict:
    try:
        r = requests.post(
            f"{OPENWA_API_URL}/sendText",
            json={"to": to, "content": text},
            timeout=10,
        )
        return r.json() if r.ok else {"ok": False, "status": r.status_code}
    except Exception as e:
        return {"ok": False, "error": str(e), "mock": True}


def on_whatsapp_message_received(handler):
    return handler
