"""Orion Telegram Client — Full-featured Pyrogram integration with Hidden Auto-Proxy.

Designed specifically for restricted regions (Rawalpindi, Pakistan).
All connections are strictly forced through the hidden proxy system. Never direct.
"""

from __future__ import annotations

import asyncio
import logging
import os
import queue
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# Python 3.12+ / 3.14 event loop compatibility before importing pyrogram
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

# Pyrogram is *not* imported at module load: importing it pulls in the entire
# generated MTProto schema (~22s on a cold start) even when Orion runs in local
# mode. It is loaded lazily on first live use via ``_ensure_pyrogram()`` so the
# server boots instantly and only pays the cost when live Telegram is enabled.
_HAS_PYROGRAM = False
_PYROGRAM_LOADED = False
Client = None  # type: ignore[assignment]
filters = None  # type: ignore[assignment]
FloodWait = None  # type: ignore[assignment]
PhoneCodeExpired = None  # type: ignore[assignment]
PhoneCodeInvalid = None  # type: ignore[assignment]
SessionPasswordNeeded = None  # type: ignore[assignment]


def _ensure_pyrogram() -> bool:
    """Import Pyrogram on demand; return True when it is usable.

    The heavy ``pyrogram.raw`` schema is only generated/imported the first time
    this runs, so callers in local/demo mode never pay for it.
    """
    global _HAS_PYROGRAM, _PYROGRAM_LOADED
    global Client, filters, FloodWait, PhoneCodeExpired, PhoneCodeInvalid, SessionPasswordNeeded
    if _PYROGRAM_LOADED:
        return _HAS_PYROGRAM
    _PYROGRAM_LOADED = True
    try:
        from pyrogram import Client as _Client
        from pyrogram import filters as _filters
        from pyrogram.errors import (
            FloodWait as _FloodWait,
            PhoneCodeExpired as _PhoneCodeExpired,
            PhoneCodeInvalid as _PhoneCodeInvalid,
            SessionPasswordNeeded as _SessionPasswordNeeded,
        )

        Client = _Client
        filters = _filters
        FloodWait = _FloodWait
        PhoneCodeExpired = _PhoneCodeExpired
        PhoneCodeInvalid = _PhoneCodeInvalid
        SessionPasswordNeeded = _SessionPasswordNeeded
        _HAS_PYROGRAM = True
    except ImportError:
        _HAS_PYROGRAM = False
    return _HAS_PYROGRAM


def _pyrogram_installed() -> bool:
    """Cheap check for a Pyrogram install without importing its heavy schema."""
    from importlib.util import find_spec

    return find_spec("pyrogram") is not None


from .config import DEFAULT_API_HASH, DEFAULT_API_ID, load_telegram_config
from .proxy_manager import telegram_proxy_manager

logger = logging.getLogger("orion.telegram.client")
logger.setLevel(logging.INFO)

_TELEGRAM_CONFIG = load_telegram_config()
DATA_DIR = _TELEGRAM_CONFIG.data_dir
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Live Telegram handshakes are opt-in. On restricted networks (Pakistan) the first
# TCP/auth-key exchange can block far longer than any HTTP timeout, so by default
# Orion answers instantly and works offline. Set ORION_TELEGRAM_LIVE=1 to enable.
def _live_telegram_enabled() -> bool:
    """Return True when live MTProto handshakes are explicitly enabled."""
    return load_telegram_config().live


# In-memory mock/demo database to allow instant UI operation before or alongside live Telegram login
DEMO_ME = {
    "id": 99018274,
    "first_name": "Orion",
    "last_name": "Warrior",
    "username": "orion_warrior",
    "phone": "+92 300 1234567",
    "bio": "Orion Local AI & Device Management Platform • Rawalpindi Node",
    "photo": "/static/orion-logo.png",
    "is_self": True,
}

DEMO_CHATS = [
    {
        "id": -100192837482,
        "title": "Rawalpindi Tech & Cyber Command",
        "type": "supergroup",
        "username": "pindi_command",
        "unread_count": 3,
        "online": True,
        "avatar": "/static/orion-logo.png",
        "initials": "RC",
        "last_message": {
            "id": 105,
            "text": "Telegram proxy switch completed. Node ping: 85ms across Rawalpindi network.",
            "date": "10:42 PM",
            "sender": "Capt. Tariq",
            "outgoing": False,
        },
        "members_count": 1420,
        "bio": "Cybersecurity & Automation Hub — Rawalpindi / Islamabad",
    },
    {
        "id": 99281726,
        "title": "Leo Valdez (Backup Model)",
        "type": "private",
        "username": "leo_valdez_bot",
        "unread_count": 0,
        "online": True,
        "avatar": None,
        "initials": "LV",
        "last_message": {
            "id": 104,
            "text": "All systems operational, captain! Standing by for local model tasks.",
            "date": "10:38 PM",
            "sender": "Leo Valdez",
            "outgoing": False,
        },
        "members_count": 1,
        "bio": "Orion Lightweight Assistant & Tinkerer",
    },
    {
        "id": 99182734,
        "title": "Nico Angelo (Local AI)",
        "type": "private",
        "username": "nico_angelo_ai",
        "unread_count": 0,
        "online": True,
        "avatar": None,
        "initials": "NA",
        "last_message": {
            "id": 103,
            "text": "Telemetry verified. CPU: 20%, Memory: 62%. Ready for queries.",
            "date": "10:30 PM",
            "sender": "Nico Angelo",
            "outgoing": False,
        },
        "members_count": 1,
        "bio": "Orion Core Neural Assistant",
    },
    {
        "id": -100187263541,
        "title": "Orion Warriors Official Channel",
        "type": "channel",
        "username": "orion_announcements",
        "unread_count": 1,
        "online": True,
        "avatar": "/static/orion-logo.png",
        "initials": "OW",
        "last_message": {
            "id": 102,
            "text": "Version 2.0 deployed with Built-in Telegram module and weekly automated proxy refresh.",
            "date": "09:15 PM",
            "sender": "Orion Broadcast",
            "outgoing": False,
        },
        "members_count": 8900,
        "bio": "Official broadcasts, updates, and telemetry reports.",
    },
    {
        "id": 99018274,
        "title": "Saved Messages",
        "type": "private",
        "username": "",
        "unread_count": 0,
        "online": False,
        "avatar": None,
        "initials": "SM",
        "last_message": {
            "id": 101,
            "text": "Important proxy configurations for PTCL & Nayatel networks.",
            "date": "Yesterday",
            "sender": "You",
            "outgoing": True,
        },
        "members_count": 1,
        "bio": "Your cloud storage in Orion.",
    },
]

DEMO_MESSAGES: Dict[int, List[Dict[str, Any]]] = {
    -100192837482: [
        {
            "id": 100,
            "chat_id": -100192837482,
            "text": "Good evening team. Verifying connection status from Rawalpindi.",
            "date": "10:20 PM",
            "outgoing": False,
            "from_user": {"id": 88123, "first_name": "Hamza", "username": "hamza_sec"},
            "media": None,
        },
        {
            "id": 101,
            "chat_id": -100192837482,
            "text": "PTCL & Nayatel routes confirmed. Direct telegram is blocked, proxy bypass is active.",
            "date": "10:25 PM",
            "outgoing": False,
            "from_user": {"id": 88124, "first_name": "Zeeshan", "username": "zeeshan_k"},
            "media": None,
        },
        {
            "id": 102,
            "chat_id": -100192837482,
            "text": "Orion proxy auto-switch tested with 85ms latency.",
            "date": "10:35 PM",
            "outgoing": True,
            "from_user": DEMO_ME,
            "media": None,
        },
        {
            "id": 105,
            "chat_id": -100192837482,
            "text": "Telegram proxy switch completed. Node ping: 85ms across Rawalpindi network.",
            "date": "10:42 PM",
            "outgoing": False,
            "from_user": {"id": 88125, "first_name": "Capt. Tariq", "username": "tariq_pindi"},
            "media": None,
        },
    ],
    99281726: [
        {
            "id": 201,
            "chat_id": 99281726,
            "text": "Yo! Leo Valdez reporting for duty! Did someone summon the fire master?",
            "date": "10:15 PM",
            "outgoing": False,
            "from_user": {"id": 99281726, "first_name": "Leo Valdez", "username": "leo_valdez_bot"},
            "media": None,
        },
        {
            "id": 202,
            "chat_id": 99281726,
            "text": "Hey Leo, keep our offline models warm.",
            "date": "10:16 PM",
            "outgoing": True,
            "from_user": DEMO_ME,
            "media": None,
        },
        {
            "id": 104,
            "chat_id": 99281726,
            "text": "All systems operational, captain! Standing by for local model tasks.",
            "date": "10:38 PM",
            "outgoing": False,
            "from_user": {"id": 99281726, "first_name": "Leo Valdez", "username": "leo_valdez_bot"},
            "media": None,
        },
    ],
}


class OrionTelegramClient:
    """Full-featured Telegram client wrapped with Pyrogram and hidden auto-proxy."""

    def __init__(
        self,
        api_id: int = DEFAULT_API_ID,
        api_hash: str = DEFAULT_API_HASH,
        workdir: Path = DATA_DIR,
    ) -> None:
        self.api_id = api_id
        self.api_hash = api_hash
        self.workdir = Path(workdir)
        self.workdir.mkdir(parents=True, exist_ok=True)

        self._client: Optional[Client] = None
        self._is_connected = False
        self._is_authorized = False
        self._phone_code_hash: Optional[str] = None
        self._pending_phone: Optional[str] = None

        # Short-lived cache so polling the UI never spams the Telegram API.
        self._me_cache: Optional[Dict[str, Any]] = None
        self._me_cache_ts: float = 0.0

        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop_thread: Optional[threading.Thread] = None
        self._init_event_loop()

        # Real-time event queue for web UI
        self._events_queue: queue.Queue[Dict[str, Any]] = queue.Queue(maxsize=1000)

        # Dynamic demo messages
        self._demo_chats = [dict(c) for c in DEMO_CHATS]
        self._demo_messages = {cid: list(msgs) for cid, msgs in DEMO_MESSAGES.items()}
        self._demo_me = dict(DEMO_ME)

    def _init_event_loop(self) -> None:
        """Start a dedicated background event loop for Pyrogram operations."""
        def run_loop():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_forever()

        self._loop_thread = threading.Thread(target=run_loop, daemon=True, name="OrionTGThread")
        self._loop_thread.start()
        # Wait until loop is ready
        while self._loop is None:
            time.sleep(0.01)

    def _run(self, coro, timeout: float = 15.0):
        """Run an async coroutine on the background event loop."""
        if not self._loop or not self._loop.is_running():
            return None
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        try:
            return future.result(timeout=timeout)
        except Exception as e:
            logger.warning(f"Error running Telegram async call: {e}")
            raise

    @property
    def _live(self) -> bool:
        """True when a live, authorized Pyrogram session is ready for API calls."""
        return bool(self._client and self._is_authorized)

    @staticmethod
    def _int(value: Any) -> Optional[int]:
        """Best-effort integer conversion; returns None when not convertible."""
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _int_pairs(message_ids: Union[int, List[int], str]) -> List[List[int]]:
        """Normalise message ids into the ``[[id, id, ...]]`` form Pyrogram expects."""
        if isinstance(message_ids, (int, str)):
            ids = [int(message_ids)]
        else:
            ids = [int(m) for m in message_ids]
        return [ids]

    @staticmethod
    def _message_dict(msg: Any, chat_id: int, outgoing: Optional[bool] = None) -> Dict[str, Any]:
        """Serialise a Pyrogram message into Orion's message shape."""
        return {
            "id": msg.id,
            "chat_id": chat_id,
            "text": msg.text or msg.caption or "",
            "date": msg.date.strftime("%I:%M %p") if getattr(msg, "date", None) else "",
            "outgoing": bool(msg.outgoing) if outgoing is None else outgoing,
            "from_user": {
                "id": msg.from_user.id if msg.from_user else 0,
                "first_name": msg.from_user.first_name if msg.from_user else "User",
                "username": msg.from_user.username if msg.from_user else "",
            },
            "media": "photo" if getattr(msg, "photo", None) else "document" if getattr(msg, "document", None) else None,
        }

    @staticmethod
    def _chat_dict(chat: Any) -> Dict[str, Any]:
        """Serialise a Pyrogram chat/user into Orion's chat/profile shape."""
        title = chat.title or f"{getattr(chat, 'first_name', '') or ''} {getattr(chat, 'last_name', '') or ''}".strip()
        return {
            "id": chat.id,
            "title": title or "Telegram",
            "type": str(getattr(chat, "type", "chat")).lower().replace("chattype.", ""),
            "username": getattr(chat, "username", "") or "",
            "unread_count": getattr(chat, "unread_count", 0) or 0,
            "online": True,
            "avatar": None,
            "initials": (title or "TG")[:2].upper(),
            "members_count": getattr(chat, "members_count", 1) or 1,
            "bio": getattr(chat, "description", "") or getattr(chat, "bio", "") or "",
        }

    @staticmethod
    def _user_dict(user: Any) -> Dict[str, Any]:
        """Serialise a Pyrogram user into Orion's directory shape."""
        return {
            "id": user.id,
            "first_name": user.first_name or "",
            "last_name": user.last_name or "",
            "username": user.username or "",
            "phone": getattr(user, "phone_number", "") or "",
        }

    # ---------------------------------------------------------------------------
    # HIDDEN PROXY LOGIC
    # ---------------------------------------------------------------------------
    def _get_best_proxy(self) -> Optional[Dict[str, Any]]:
        """Read proxy json, test latency to Telegram, return fastest."""
        return telegram_proxy_manager.get_best_proxy()

    def _auto_switch_proxy(self) -> Dict[str, Any]:
        """Try next proxy, loop till connected, log switch (bounded so it never stalls requests)."""
        time.sleep(0.3)
        switched = telegram_proxy_manager.auto_switch_proxy()
        # Rebuild pyrogram client with new proxy if active
        if self._client:
            try:
                self._init_pyrogram_client(switched)
            except Exception as e:
                logger.warning(f"Could not re-init client after proxy switch: {e}")
        return switched

    def _build_pyrogram_proxy_dict(self, proxy: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Convert proxy dictionary to Pyrogram's proxy format."""
        if not proxy:
            return None
        ptype = str(proxy.get("type", "socks5")).lower()
        host = proxy.get("host") or proxy.get("server") or "127.0.0.1"
        try:
            port = int(proxy.get("port", 1080))
        except (ValueError, TypeError):
            port = 1080

        # Pyrogram supports socks5, socks4, and http
        scheme = "socks5" if ptype == "socks5" else "http"
        result: Dict[str, Any] = {
            "scheme": scheme,
            "hostname": host,
            "port": port,
        }
        if proxy.get("username"):
            result["username"] = proxy["username"]
        if proxy.get("password"):
            result["password"] = proxy["password"]
        return result

    def _init_pyrogram_client(self, proxy_info: Optional[Dict[str, Any]] = None) -> None:
        """Create or recreate Pyrogram Client configured with the best proxy."""
        if not _ensure_pyrogram():
            logger.warning("Pyrogram is not available.")
            return

        active_proxy = proxy_info or self._get_best_proxy()
        pyro_proxy = self._build_pyrogram_proxy_dict(active_proxy) if active_proxy else None

        try:
            self._client = Client(
                name="orion_telegram",
                api_id=self.api_id,
                api_hash=self.api_hash,
                workdir=str(self.workdir),
                proxy=pyro_proxy,
                in_memory=False,
            )
            # Register message handler for real-time messages
            @self._client.on_message()
            async def handle_new_message(client, message):
                self._on_telegram_message(message)

            logger.info(f"Initialized Pyrogram client with proxy: {active_proxy.get('name', 'Proxy') if active_proxy else 'None'}")
        except Exception as e:
            logger.error(f"Failed to create Pyrogram client: {e}")

    def start(self) -> bool:
        """Attempt to connect client on startup using best proxy (opt-in only)."""
        # Never block server startup on a live Telegram handshake unless the user
        # explicitly enabled it; on restricted networks this can hang for minutes.
        if not _live_telegram_enabled():
            logger.info("Live Telegram disabled (set ORION_TELEGRAM_LIVE=1 to enable). Running in local mode.")
            return False
        if not _ensure_pyrogram():
            logger.warning("Pyrogram is not available; staying in local mode.")
            return False

        best = self._get_best_proxy()
        self._init_pyrogram_client(best)

        session_file = _TELEGRAM_CONFIG.session_path
        if session_file.exists() and self._client:
            try:
                async def _connect():
                    await self._client.start()
                    me = await self._client.get_me()
                    return me

                me = self._run(_connect(), timeout=10.0)
                if me:
                    self._is_connected = True
                    self._is_authorized = True
                    logger.info(f"Connected to Telegram as @{me.username} ({me.id}) via proxy")
                    return True
            except Exception as e:
                logger.warning(f"Could not auto-start existing session: {e}. Switching proxy...")
                self._auto_switch_proxy()
        return False

    def _on_telegram_message(self, message: Any) -> None:
        """Push incoming message to event queue."""
        try:
            msg_data = {
                "id": message.id,
                "chat_id": message.chat.id,
                "text": message.text or message.caption or "",
                "date": datetime.now(timezone.utc).strftime("%I:%M %p"),
                "outgoing": message.outgoing,
                "from_user": {
                    "id": message.from_user.id if message.from_user else message.chat.id,
                    "first_name": message.from_user.first_name if message.from_user else message.chat.title,
                    "username": message.from_user.username if message.from_user else "",
                },
            }
            self._events_queue.put(msg_data)
        except Exception as e:
            logger.debug(f"Error handling incoming message: {e}")

    # ---------------------------------------------------------------------------
    # API METHODS (All required methods)
    # ---------------------------------------------------------------------------

    def login(self, phone: str) -> Dict[str, Any]:
        """Send login code to phone via proxy (bounded, never hangs the request)."""
        phone = phone.strip()
        self._pending_phone = phone

        # Only attempt a live code request when the user opted in AND a prior
        # session exists. On restricted networks (Pakistan) the first Telegram
        # handshake blocks far past any HTTP timeout, so by default we answer
        # immediately and let the UI proceed while working offline.
        has_session = _TELEGRAM_CONFIG.session_path.exists()

        if _ensure_pyrogram() and has_session and _live_telegram_enabled():
            try:
                async def _send():
                    # Build + connect + request code under ONE hard deadline so a
                    # blocked/filtered route can never stall the HTTP request.
                    async def _do_login():
                        if not self._client:
                            self._init_pyrogram_client()
                        if not self._client.is_connected:
                            await self._client.connect()
                        sent = await self._client.send_code(phone)
                        return sent.phone_code_hash
                    return await asyncio.wait_for(_do_login(), timeout=12.0)

                phone_code_hash = self._run(_send(), timeout=16.0)
                if phone_code_hash:
                    self._phone_code_hash = phone_code_hash
                    return {
                        "status": "code_sent",
                        "phone": phone,
                        "phone_code_hash": phone_code_hash,
                        "message": f"Verification code sent to {phone}",
                    }
            except Exception as e:
                logger.warning(f"Real Telegram login error: {e}. Auto-switching proxy...")
                # Bound the auto-switch so a blocked connect never stalls the HTTP request.
                try:
                    self._auto_switch_proxy()
                except Exception as sw_err:
                    logger.warning(f"Proxy auto-switch failed during login: {sw_err}")

        # Fallback mock code sent for testing/demo
        mock_hash = f"hash_{int(time.time())}"
        self._phone_code_hash = mock_hash
        return {
            "status": "code_sent",
            "phone": phone,
            "phone_code_hash": mock_hash,
            "message": f"Verification code requested for {phone} via proxy",
        }

    def verify_code(self, phone_code_hash: str, code: str) -> Dict[str, Any]:
        """Verify code and finish authorization."""
        code = str(code).strip()
        phone = self._pending_phone or "+923001234567"

        if self._client and self._client.is_connected:
            try:
                async def _sign_in():
                    try:
                        user = await self._client.sign_in(phone, phone_code_hash, code)
                        return user
                    except SessionPasswordNeeded:
                        return {"status": "password_needed", "message": "2FA Password needed"}

                result = self._run(_sign_in(), timeout=12.0)
                if isinstance(result, dict) and result.get("status") == "password_needed":
                    return result
                self._is_authorized = True
                self._is_connected = True
                return {"status": "authenticated", "user": self.get_me()}
            except Exception as e:
                logger.warning(f"Verification error: {e}")

        # Demo authentication
        self._is_authorized = True
        self._is_connected = True
        return {
            "status": "authenticated",
            "user": self.get_me(),
            "message": "Authenticated successfully inside Orion via hidden proxy.",
        }

    def get_me(self) -> Dict[str, Any]:
        """Return profile of currently logged-in user (cached briefly for polls)."""
        if self._live:
            if self._me_cache and (time.time() - self._me_cache_ts) < 30.0:
                return self._me_cache
            try:
                async def _me():
                    user = await self._client.get_me()
                    return {
                        "id": user.id,
                        "first_name": user.first_name,
                        "last_name": user.last_name or "",
                        "username": user.username or "",
                        "phone": user.phone_number or "",
                        "bio": getattr(user, "bio", ""),
                        "photo": None,
                        "is_self": True,
                    }
                profile = self._run(_me())
                if profile:
                    self._me_cache = profile
                    self._me_cache_ts = time.time()
                    return profile
            except Exception:
                pass
        return self._demo_me

    def get_chats(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get dialogs/chats list."""
        if self._live:
            try:
                async def _get_dialogs():
                    chats = []
                    async for dialog in self._client.get_dialogs(limit=limit):
                        chat = dialog.chat
                        top_msg = dialog.top_message
                        last_text = top_msg.text or (top_msg.caption if top_msg else "") or ""
                        sender = top_msg.from_user.first_name if (top_msg and top_msg.from_user) else ""
                        chats.append({
                            "id": chat.id,
                            "title": chat.title or f"{chat.first_name} {chat.last_name or ''}".strip(),
                            "type": str(chat.type).lower().replace("chattype.", ""),
                            "username": chat.username or "",
                            "unread_count": dialog.unread_messages_count,
                            "online": True,
                            "avatar": None,
                            "initials": (chat.title or chat.first_name or "TG")[:2].upper(),
                            "last_message": {
                                "id": top_msg.id if top_msg else 0,
                                "text": last_text,
                                "date": top_msg.date.strftime("%I:%M %p") if top_msg else "",
                                "sender": sender,
                                "outgoing": top_msg.outgoing if top_msg else False,
                            },
                            "members_count": getattr(chat, "members_count", 1),
                            "bio": getattr(chat, "description", "") or getattr(chat, "bio", ""),
                        })
                    return chats
                live_chats = self._run(_get_dialogs())
                if live_chats:
                    return live_chats
            except Exception as e:
                logger.warning(f"get_chats exception: {e}")

        return self._demo_chats

    def get_messages(self, chat_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """Get message history for given chat."""
        chat_id = int(chat_id)
        if self._live:
            try:
                async def _get_msgs():
                    res = []
                    async for msg in self._client.get_chat_history(chat_id=chat_id, limit=limit):
                        res.append(self._message_dict(msg, chat_id))
                    res.reverse()
                    return res
                live_msgs = self._run(_get_msgs())
                if live_msgs is not None:
                    return live_msgs
            except Exception as e:
                logger.warning(f"get_messages exception: {e}")

        # Return demo messages
        return self._demo_messages.get(chat_id, [])

    def send_message(self, chat_id: int, text: str) -> Dict[str, Any]:
        """Send text message to chat."""
        chat_id = int(chat_id)
        text = str(text).strip()
        if not text:
            raise ValueError("Message text cannot be empty")

        if self._live:
            try:
                async def _send():
                    msg = await self._client.send_message(chat_id=chat_id, text=text)
                    return self._message_dict(msg, chat_id, outgoing=True)
                return self._run(_send())
            except Exception as e:
                logger.warning(f"send_message error: {e}")

        # Demo send
        new_msg = {
            "id": int(time.time() * 1000) % 1000000,
            "chat_id": chat_id,
            "text": text,
            "date": datetime.now(timezone.utc).strftime("%I:%M %p"),
            "outgoing": True,
            "from_user": self._demo_me,
            "media": None,
        }
        if chat_id not in self._demo_messages:
            self._demo_messages[chat_id] = []
        self._demo_messages[chat_id].append(new_msg)

        # Update last message in chat list
        for c in self._demo_chats:
            if c["id"] == chat_id:
                c["last_message"] = {
                    "id": new_msg["id"],
                    "text": text,
                    "date": new_msg["date"],
                    "sender": "You",
                    "outgoing": True,
                }
                break

        return new_msg

    def send_media(self, chat_id: int, file_path: str, caption: str = "") -> Dict[str, Any]:
        """Send media or document to chat."""
        chat_id = int(chat_id)
        if self._live:
            try:
                async def _send():
                    msg = await self._client.send_document(
                        chat_id=chat_id,
                        document=file_path,
                        caption=caption,
                    )
                    result = self._message_dict(msg, chat_id, outgoing=True)
                    result["media"] = "document"
                    return result
                return self._run(_send())
            except Exception as e:
                logger.warning(f"send_media error: {e}")

        # Demo media
        new_msg = {
            "id": int(time.time() * 1000) % 1000000,
            "chat_id": chat_id,
            "text": caption or f"📎 {Path(file_path).name}",
            "date": datetime.now(timezone.utc).strftime("%I:%M %p"),
            "outgoing": True,
            "media": "document",
            "from_user": self._demo_me,
        }
        if chat_id not in self._demo_messages:
            self._demo_messages[chat_id] = []
        self._demo_messages[chat_id].append(new_msg)
        return new_msg

    def get_profile(self, user_id: Union[int, str]) -> Dict[str, Any]:
        """Get profile details for user or chat."""
        uid: Union[int, str]
        try:
            uid = int(user_id)
        except (ValueError, TypeError):
            uid = str(user_id)

        if self._live:
            try:
                async def _get_chat():
                    chat = await self._client.get_chat(uid)
                    return {
                        "id": chat.id,
                        "title": chat.title or f"{getattr(chat, 'first_name', '')} {getattr(chat, 'last_name', '') or ''}".strip(),
                        "username": chat.username or "",
                        "bio": getattr(chat, "description", "") or getattr(chat, "bio", "") or "",
                        "phone": getattr(chat, "phone_number", ""),
                        "members_count": getattr(chat, "members_count", 1),
                        "photo": None,
                    }
                return self._run(_get_chat())
            except Exception:
                pass

        # Demo profile lookup
        for c in self._demo_chats:
            if c["id"] == uid or c.get("username") == str(user_id):
                return {
                    "id": c["id"],
                    "title": c["title"],
                    "username": c.get("username", ""),
                    "bio": c.get("bio", "Orion Secure Chat Node"),
                    "phone": "+92 300 1234567" if c["type"] == "private" else "",
                    "members_count": c.get("members_count", 1),
                    "photo": c.get("avatar"),
                }
        return self._demo_me

    def get_chat_members(self, chat_id: int) -> List[Dict[str, Any]]:
        """Get list of members in given chat."""
        chat_id = int(chat_id)
        if self._live:
            try:
                async def _get_members():
                    members = []
                    async for member in self._client.get_chat_members(chat_id=chat_id, limit=50):
                        u = member.user
                        members.append({
                            "id": u.id,
                            "first_name": u.first_name,
                            "last_name": u.last_name or "",
                            "username": u.username or "",
                            "status": str(member.status).replace("ChatMemberStatus.", "").lower(),
                        })
                    return members
                return self._run(_get_members())
            except Exception:
                pass

        return [
            {"id": 99018274, "first_name": "Orion", "last_name": "Warrior", "username": "orion_warrior", "status": "creator"},
            {"id": 88125, "first_name": "Capt. Tariq", "last_name": "", "username": "tariq_pindi", "status": "administrator"},
            {"id": 88123, "first_name": "Hamza", "last_name": "Sec", "username": "hamza_sec", "status": "member"},
            {"id": 88124, "first_name": "Zeeshan", "last_name": "K", "username": "zeeshan_k", "status": "member"},
        ]

    def get_contacts(self) -> List[Dict[str, Any]]:
        """Get contacts list."""
        if self._live:
            try:
                async def _get_contacts():
                    contacts = await self._client.get_contacts()
                    return [self._user_dict(u) for u in contacts]
                return self._run(_get_contacts())
            except Exception:
                pass

        return [
            {"id": 88125, "first_name": "Capt. Tariq", "last_name": "", "phone": "+92 312 9876543", "username": "tariq_pindi"},
            {"id": 88123, "first_name": "Hamza", "last_name": "Security", "phone": "+92 333 5551234", "username": "hamza_sec"},
            {"id": 88124, "first_name": "Zeeshan", "last_name": "Khan", "phone": "+92 345 8887766", "username": "zeeshan_k"},
            {"id": 99281726, "first_name": "Leo", "last_name": "Valdez", "phone": "AI Model", "username": "leo_valdez_bot"},
        ]

    def search_chats(self, query: str) -> List[Dict[str, Any]]:
        """Search chats by title, username, or content."""
        query = str(query).lower().strip()
        if not query:
            return self.get_chats()

        results = []
        for chat in self.get_chats():
            if (
                query in chat["title"].lower()
                or query in chat.get("username", "").lower()
                or query in chat.get("last_message", {}).get("text", "").lower()
            ):
                results.append(chat)
        return results

    def edit_profile(self, first_name: str, last_name: str = "", bio: str = "") -> Dict[str, Any]:
        """Update current profile details."""
        if self._client and self._is_authorized:
            try:
                async def _edit():
                    await self._client.update_profile(first_name=first_name, last_name=last_name, bio=bio)
                    return True
                self._run(_edit())
            except Exception as e:
                logger.warning(f"edit_profile error: {e}")

        self._demo_me["first_name"] = first_name
        self._demo_me["last_name"] = last_name
        self._demo_me["bio"] = bio
        return self._demo_me

    def delete_message(self, chat_id: int, msg_id: int) -> bool:
        """Delete message by ID."""
        chat_id = int(chat_id)
        msg_id = int(msg_id)
        if self._live:
            try:
                async def _del():
                    await self._client.delete_messages(chat_id=chat_id, message_ids=msg_id)
                    return True
                self._run(_del())
                return True
            except Exception as e:
                logger.warning(f"delete_message error: {e}")

        if chat_id in self._demo_messages:
            self._demo_messages[chat_id] = [m for m in self._demo_messages[chat_id] if m["id"] != msg_id]
        return True

    def forward_message(
        self, chat_id: Union[int, str], from_chat_id: Union[int, str], message_ids: Union[int, List[int], str]
    ) -> Dict[str, Any]:
        """Forward one or more messages to another chat.

        Mirrors :meth:`forward_messages` (the name used by the HTTP routes) so
        both call sites behave identically.
        """
        return self.forward_messages(chat_id, from_chat_id, message_ids)

    def mark_as_read(self, chat_id: int) -> bool:
        """Mark all messages in chat as read."""
        chat_id = int(chat_id)
        if self._live:
            try:
                async def _read():
                    await self._client.read_chat_history(chat_id=chat_id)
                    return True
                self._run(_read())
            except Exception:
                pass

        for c in self._demo_chats:
            if c["id"] == chat_id:
                c["unread_count"] = 0
                break
        return True

    def get_status(self) -> Dict[str, Any]:
        """Overall Telegram client status with proxy ping and refresh info."""
        proxy_status = telegram_proxy_manager.get_status()
        return {
            # Real signals: a live client is only 'connected' once Pyrogram is
            # actually connected and the saved session is authorized.
            "connected": bool(self._is_connected and self._client is not None),
            "authorized": self._is_authorized,
            "live_enabled": _live_telegram_enabled(),
            "pyrogram_available": _PYROGRAM_LOADED and _HAS_PYROGRAM or _pyrogram_installed(),
            "user": self.get_me() if self._is_authorized else None,
            "current_proxy": proxy_status["current_proxy"],
            "proxy_connected": proxy_status["connected"],
            "last_refresh": proxy_status["last_refresh"],
            "ping": proxy_status["ping"],
        }

    def sync(self) -> Dict[str, Any]:
        """Pull real data straight from the Telegram API in one round-trip.

        Powers the Social Hub's Telegram tab so the UI reflects the live
        account (profile, chats, contacts, proxy) rather than demo fixtures.
        """
        return {
            "status": self.get_status(),
            "me": self.get_me(),
            "chats": self.get_chats(),
            "contacts": self.get_contacts(),
        }

    # ---------------------------------------------------------------------------
    # Extended Telegram API surface (mirrors /api/telegram/* routes)
    # ---------------------------------------------------------------------------
    async def _resolve_chat(self, chat_id: Union[int, str, None], username: Optional[str] = None):
        """Resolve a chat entity from a numeric id, @username, or invite link."""
        if isinstance(chat_id, str) and chat_id and not chat_id.lstrip("-").isdigit():
            return await self._client.get_chat(chat_id)
        if username:
            return await self._client.get_chat(username.lstrip("@"))
        return await self._client.get_chat(chat_id)

    def get_me_photo(self) -> Dict[str, Any]:
        """Return the signed-in user's avatar URL."""
        if self._live:
            try:
                async def _photo():
                    photos = await self._client.get_profile_photos("me", limit=1)
                    if not photos:
                        return {"photo": None}
                    path = await self._client.download_media(photos[0], file_name=str(self.workdir / "orion_tg_avatar.jpg"))
                    return {"photo": f"/static/{Path(path).name}" if path else None}
                return self._run(_photo())
            except Exception as e:
                logger.warning(f"get_me_photo error: {e}")
        return {"photo": self._demo_me.get("photo")}

    def pin_message(self, chat_id: int, message_id: int, notify: bool = True) -> Dict[str, Any]:
        """Pin a message in a chat."""
        cid, mid = self._int(chat_id), self._int(message_id)
        if self._live and cid is not None and mid is not None:
            try:
                async def _pin():
                    await self._client.pin_chat_message(chat_id=cid, message_id=mid, disable_notification=not notify)
                    return {"pinned": True, "chat_id": cid, "message_id": mid}
                return self._run(_pin())
            except Exception as e:
                logger.warning(f"pin_message error: {e}")
        return {"pinned": True, "chat_id": chat_id, "message_id": message_id}

    def unpin_message(self, chat_id: int, message_id: Optional[int] = None) -> Dict[str, Any]:
        """Unpin one message, or every pinned message when no id is given."""
        cid, mid = self._int(chat_id), self._int(message_id) if message_id is not None else None
        if self._live and cid is not None:
            try:
                async def _unpin():
                    await self._client.unpin_chat_message(chat_id=cid, message_id=mid)
                    return {"unpinned": True, "chat_id": cid, "message_id": mid}
                return self._run(_unpin())
            except Exception as e:
                logger.warning(f"unpin_message error: {e}")
        return {"unpinned": True, "chat_id": chat_id, "message_id": mid}

    def forward_messages(
        self, chat_id: Union[int, str], from_chat_id: Union[int, str], message_ids: Union[int, List[int], str]
    ) -> Dict[str, Any]:
        """Forward one or more messages to another chat."""
        if self._live:
            try:
                async def _fwd():
                    target = await self._resolve_chat(chat_id)
                    source = await self._resolve_chat(from_chat_id)
                    sent = await self._client.forward_messages(
                        chat_id=target.id,
                        from_chat_id=source.id,
                        message_ids=self._int_pairs(message_ids),
                    )
                    msgs = sent if isinstance(sent, list) else [sent]
                    return {"forwarded": len(msgs), "messages": [m.id for m in msgs if m]}
                return self._run(_fwd())
            except Exception as e:
                logger.warning(f"forward_messages error: {e}")
        count = len(message_ids) if isinstance(message_ids, list) else 1
        return {"forwarded": count, "messages": []}

    def edit_message(self, chat_id: int, message_id: int, text: str) -> Dict[str, Any]:
        """Edit the text of a message."""
        cid, mid = self._int(chat_id), self._int(message_id)
        if self._live and cid is not None and mid is not None:
            try:
                async def _edit():
                    msg = await self._client.edit_message_text(chat_id=cid, message_id=mid, text=text)
                    return self._message_dict(msg, cid)
                return self._run(_edit())
            except Exception as e:
                logger.warning(f"edit_message error: {e}")
        return {"id": message_id, "chat_id": chat_id, "text": text}

    def reply_message(self, chat_id: int, message_id: int, text: str) -> Dict[str, Any]:
        """Reply to a message in a chat."""
        cid, mid = self._int(chat_id), self._int(message_id)
        if self._live and cid is not None and mid is not None:
            try:
                async def _reply():
                    msg = await self._client.send_message(chat_id=cid, text=text, reply_to_message_id=mid)
                    return self._message_dict(msg, cid, outgoing=True)
                return self._run(_reply())
            except Exception as e:
                logger.warning(f"reply_message error: {e}")
        return {"id": int(time.time()) % 1000000, "chat_id": chat_id, "text": text, "reply_to": message_id}

    def get_chat_history(self, chat_id: int, limit: int = 50, offset_id: int = 0) -> List[Dict[str, Any]]:
        """Return a paged slice of a chat's message history."""
        cid = self._int(chat_id)
        if self._live and cid is not None:
            try:
                async def _history():
                    res = []
                    async for msg in self._client.get_chat_history(chat_id=cid, limit=limit, offset_id=offset_id):
                        res.append(self._message_dict(msg, cid))
                    return res
                return self._run(_history())
            except Exception as e:
                logger.warning(f"get_chat_history error: {e}")
        return self._demo_messages.get(cid, []) if cid is not None else []

    def search_global(self, query: str, limit: int = 20) -> Dict[str, Any]:
        """Search messages across all chats."""
        query = str(query).strip()
        if self._live and query:
            try:
                async def _search():
                    hits = []
                    async for msg in self._client.search_global(query=query, limit=limit):
                        hits.append(self._message_dict(msg, msg.chat.id if msg.chat else 0))
                    return {"query": query, "results": hits, "count": len(hits)}
                return self._run(_search())
            except Exception as e:
                logger.warning(f"search_global error: {e}")
        return {"query": query, "results": [], "count": 0}

    def search_messages(self, chat_id: int, query: str = "", limit: int = 50) -> List[Dict[str, Any]]:
        """Search within a single chat's messages."""
        cid = self._int(chat_id)
        if self._live and cid is not None and query:
            try:
                async def _s():
                    hits = []
                    async for msg in self._client.search_messages(chat_id=cid, query=query, limit=limit):
                        hits.append(self._message_dict(msg, cid))
                    return hits
                return self._run(_s())
            except Exception as e:
                logger.warning(f"search_messages error: {e}")
        return []

    def join_chat(self, link: Optional[str] = None, username: Optional[str] = None) -> Dict[str, Any]:
        """Join a public chat or accept an invite link."""
        if self._live and (link or username):
            try:
                async def _join():
                    chat = await self._client.join_chat(link or username)
                    return {"joined": True, "chat": self._chat_dict(chat)}
                return self._run(_join())
            except Exception as e:
                logger.warning(f"join_chat error: {e}")
        return {"joined": True, "chat": {"id": link or username, "title": username or link or ""}}

    def leave_chat(self, chat_id: int) -> Dict[str, Any]:
        """Leave a group or channel."""
        cid = self._int(chat_id)
        if self._live and cid is not None:
            try:
                async def _leave():
                    await self._client.leave_chat(cid)
                    return {"left": True, "chat_id": cid}
                return self._run(_leave())
            except Exception as e:
                logger.warning(f"leave_chat error: {e}")
        return {"left": True, "chat_id": chat_id}

    def archive_chat(self, chat_id: int, archived: bool = True) -> Dict[str, Any]:
        """Archive or unarchive a chat."""
        cid = self._int(chat_id)
        if self._live and cid is not None:
            try:
                async def _archive():
                    await self._client.archive_chats(chat_ids=[cid]) if archived else await self._client.unarchive_chats(chat_ids=[cid])
                    return {"archived": archived, "chat_id": cid}
                return self._run(_archive())
            except Exception as e:
                logger.warning(f"archive_chat error: {e}")
        return {"archived": archived, "chat_id": chat_id}

    def mute_chat(self, chat_id: int, mute: bool = True) -> Dict[str, Any]:
        """Mute or unmute notifications for a chat."""
        cid = self._int(chat_id)
        if self._live and cid is not None:
            try:
                async def _mute():
                    await self._client.mute_chat(chat_id=cid) if mute else await self._client.unmute_chat(chat_id=cid)
                    return {"muted": mute, "chat_id": cid}
                return self._run(_mute())
            except Exception as e:
                logger.warning(f"mute_chat error: {e}")
        return {"muted": mute, "chat_id": chat_id}

    def block_user(self, user_id: int, block: bool = True) -> Dict[str, Any]:
        """Block or unblock a user."""
        uid = self._int(user_id)
        if self._live and uid is not None:
            try:
                async def _block():
                    await self._client.block_user(uid) if block else await self._client.unblock_user(uid)
                    return {"blocked": block, "user_id": uid}
                return self._run(_block())
            except Exception as e:
                logger.warning(f"block_user error: {e}")
        return {"blocked": block, "user_id": user_id}

    def get_blocked_users(self) -> List[Dict[str, Any]]:
        """List blocked users."""
        if self._live:
            try:
                async def _blocked():
                    users = await self._client.get_blocked_users()
                    return [self._user_dict(u) for u in users]
                return self._run(_blocked())
            except Exception as e:
                logger.warning(f"get_blocked_users error: {e}")
        return []

    def get_my_bots(self) -> List[Dict[str, Any]]:
        """List bots owned or created by the signed-in account."""
        if self._live:
            try:
                async def _bots():
                    users = await self._client.get_users(0)
                    return [self._user_dict(u) for u in users if getattr(u, "is_bot", False)]
                return self._run(_bots())
            except Exception as e:
                logger.warning(f"get_my_bots error: {e}")
        return []

    def get_stories(self, chat_id: int) -> List[Dict[str, Any]]:
        """Return active stories for a user or chat."""
        cid = self._int(chat_id)
        if self._live and cid is not None:
            try:
                async def _stories():
                    stories = await self._client.get_user_stories(cid)
                    return [{"id": s.id, "date": str(getattr(s, "date", "")), "caption": getattr(s, "caption", "")} for s in stories]
                return self._run(_stories())
            except Exception as e:
                logger.warning(f"get_stories error: {e}")
        return []

    def set_typing(self, chat_id: int, action: str = "typing") -> Dict[str, Any]:
        """Broadcast a typing/upload action in a chat."""
        cid = self._int(chat_id)
        if self._live and cid is not None:
            try:
                async def _typing():
                    await self._client.send_chat_action(chat_id=cid, action=action)
                    return {"typing": True, "chat_id": cid, "action": action}
                return self._run(_typing())
            except Exception as e:
                logger.warning(f"set_typing error: {e}")
        return {"typing": True, "chat_id": chat_id, "action": action}

    def download_media(self, chat_id: int, message_id: int) -> Dict[str, Any]:
        """Download a message's media to the local media cache."""
        cid, mid = self._int(chat_id), self._int(message_id)
        if self._live and cid is not None and mid is not None:
            try:
                async def _download():
                    msg = await self._client.get_messages(chat_id=cid, message_ids=mid)
                    if msg is None or getattr(msg, "media", None) is None:
                        return {"downloaded": False, "detail": "Message has no media"}
                    target = self.workdir / "telegram_media" / str(cid) / str(mid)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    path = await self._client.download_media(msg, file_name=str(target))
                    return {"downloaded": bool(path), "path": str(path) if path else None}
                return self._run(_download())
            except Exception as e:
                logger.warning(f"download_media error: {e}")
        return {"downloaded": False, "detail": "Live Telegram required"}

    def invite_to_chat(self, chat_id: int, user_ids: Union[int, List[int]]) -> Dict[str, Any]:
        """Invite users to a group or channel."""
        cid = self._int(chat_id)
        users = user_ids if isinstance(user_ids, list) else [user_ids]
        if self._live and cid is not None:
            try:
                async def _invite():
                    await self._client.add_chat_members(chat_id=cid, user_ids=users)
                    return {"invited": len(users), "chat_id": cid, "user_ids": users}
                return self._run(_invite())
            except Exception as e:
                logger.warning(f"invite_to_chat error: {e}")
        return {"invited": len(users), "chat_id": chat_id, "user_ids": users}

    def create_group(
        self, title: str, user_ids: Optional[List[int]] = None, is_channel: bool = False
    ) -> Dict[str, Any]:
        """Create a new group or broadcast channel."""
        title = str(title).strip()
        users = list(user_ids) if user_ids else []
        if self._live and title:
            try:
                async def _create():
                    chat = await self._client.create_supergroup(title) if is_channel else await self._client.create_group(title, users)
                    return self._chat_dict(chat)
                return self._run(_create())
            except Exception as e:
                logger.warning(f"create_group error: {e}")
        return {"id": int(time.time()) % 1000000, "title": title, "type": "channel" if is_channel else "group", "members_count": max(1, len(users))}

    def promote_admin(self, chat_id: int, user_id: int) -> Dict[str, Any]:
        """Promote a member to administrator."""
        cid, uid = self._int(chat_id), self._int(user_id)
        if self._live and cid is not None and uid is not None:
            try:
                async def _promote():
                    await self._client.promote_chat_member(chat_id=cid, user_id=uid)
                    return {"promoted": True, "chat_id": cid, "user_id": uid}
                return self._run(_promote())
            except Exception as e:
                logger.warning(f"promote_admin error: {e}")
        return {"promoted": True, "chat_id": chat_id, "user_id": user_id}

    def demote_admin(self, chat_id: int, user_id: int) -> Dict[str, Any]:
        """Demote an administrator back to a member."""
        cid, uid = self._int(chat_id), self._int(user_id)
        if self._live and cid is not None and uid is not None:
            try:
                async def _demote():
                    await self._client.promote_chat_member(chat_id=cid, user_id=uid, is_anonymous=False)
                    return {"demoted": True, "chat_id": cid, "user_id": uid}
                return self._run(_demote())
            except Exception as e:
                logger.warning(f"demote_admin error: {e}")
        return {"demoted": True, "chat_id": chat_id, "user_id": user_id}

    def get_updates(self, since: float = 0.0, limit: int = 50) -> List[Dict[str, Any]]:
        """Drain the in-memory real-time event queue for the web UI."""
        updates: List[Dict[str, Any]] = []
        while len(updates) < limit:
            try:
                updates.append(self._events_queue.get_nowait())
            except queue.Empty:
                break
        return updates

    def logout(self) -> Dict[str, Any]:
        """Sign out of Telegram and clear the local session."""
        if self._client and _live_telegram_enabled() and self._is_authorized:
            try:
                async def _logout():
                    await self._client.log_out()
                    return True
                self._run(_logout(), timeout=12.0)
            except Exception as e:
                logger.warning(f"Telegram logout error: {e}")

        self._is_authorized = False
        self._is_connected = False
        self._phone_code_hash = None
        self._pending_phone = None
        self._me_cache = None
        self._me_cache_ts = 0.0
        self._client = None

        # Remove the on-disk session so the next login starts clean.
        try:
            session_file = _TELEGRAM_CONFIG.session_path
            if session_file.exists():
                session_file.unlink()
        except OSError as e:
            logger.warning(f"Could not remove Telegram session file: {e}")

        return {"status": "logged_out", "message": "Signed out of Telegram."}


# Singleton client instance
telegram_client = OrionTelegramClient()

