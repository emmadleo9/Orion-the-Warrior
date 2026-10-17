"""Orion Telegram Integration — Telethon engine for the Social Hub.

This module provides the account-level Telegram integration used by the Telegram
tab of the Social Hub:

* :class:`TelegramProxySettings` — parses SOCKS/HTTP/MTProto proxy settings from
  the environment or from a shared ``t.me/proxy`` link.
* :class:`TelegramIntegration` — owns the Telethon client, an SQLite archive of
  dialogs/messages/downloaded media, a saved MTProto proxy pool, and the full
  "import my history" workflow.

All network access is strictly routed through a configured proxy; on restricted
networks (Pakistan) the MTProto handshake can block, so the integration always
fails fast with a clear, actionable error rather than hanging the UI.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import sqlite3
import threading
from concurrent.futures import TimeoutError as FutureTimeoutError
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional
from urllib.parse import parse_qs, unquote, urlparse

from .config import DEFAULT_API_HASH, DEFAULT_API_ID, load_telegram_config

logger = logging.getLogger("orion.telegram.integration")
logger.setLevel(logging.INFO)

_TELEGRAM_CONFIG = load_telegram_config()

# Proxy settings are persisted in the Telegram data dir so a chosen MTProto
# relay survives restarts without ever writing the secret into logs.
_PROXY_ENV_KEYS = (
    "ORION_TELEGRAM_PROXY_TYPE",
    "ORION_TELEGRAM_PROXY_HOST",
    "ORION_TELEGRAM_PROXY_PORT",
    "ORION_TELEGRAM_PROXY_USERNAME",
    "ORION_TELEGRAM_PROXY_PASSWORD",
    "ORION_TELEGRAM_PROXY_SECRET",
)

# Telethon is imported lazily: ``import telethon`` costs several seconds and is
# only needed once a real import/history sync is requested. The module-level
# names below are populated by ``_ensure_telethon()`` on first use, so Orion
# boots instantly and the integration degrades gracefully when telethon is absent.
_MTProxyConnection = None
_TelethonClient = None
_SessionPasswordNeededError = None
_TELETHON_LOADED = False


def _ensure_telethon() -> bool:
    """Import Telethon on demand; return True when it is usable."""
    global _MTProxyConnection, _TelethonClient, _SessionPasswordNeededError, _TELETHON_LOADED
    if _TELETHON_LOADED:
        return _TelethonClient is not None
    _TELETHON_LOADED = True
    try:  # pragma: no cover - exercised indirectly through tests
        from telethon.network.connection.tcpmtproxy import (
            ConnectionTcpMTProxyRandomizedIntermediate as _Conn,
        )

        _MTProxyConnection = _Conn
    except Exception:  # pragma: no cover
        _MTProxyConnection = None

    try:  # pragma: no cover
        from telethon import TelegramClient as _Client
        from telethon.errors import SessionPasswordNeededError as _PasswordError

        _TelethonClient = _Client
        _SessionPasswordNeededError = _PasswordError
    except Exception:  # pragma: no cover
        _TelethonClient = None
        _SessionPasswordNeededError = None
    return _TelethonClient is not None


class TelegramIntegrationError(RuntimeError):
    """Raised when a Telegram operation cannot be completed."""


_SOCKS_TYPES = {"socks5", "socks4"}
_HTTP_TYPES = {"http", "https"}
_MT_TYPES = {"mtproxy", "mtproto"}
_ALLOWED_TYPES = _SOCKS_TYPES | _HTTP_TYPES | _MT_TYPES


@dataclass(frozen=True)
class TelegramProxySettings:
    """Immutable, validated Telegram proxy configuration."""

    proxy_type: str
    host: str
    port: int
    username: str = ""
    password: str = ""
    secret: str = ""

    # -- constructors -------------------------------------------------------
    @classmethod
    def from_environment(cls, source: Optional[Mapping[str, str]] = None) -> Optional["TelegramProxySettings"]:
        """Build proxy settings from ``source`` (defaults to ``os.environ``).

        Returns ``None`` when no proxy type is configured. Raises
        :class:`TelegramIntegrationError` when settings are present but invalid.
        """
        env: Mapping[str, str] = os.environ if source is None else source
        raw_type = str(env.get("ORION_TELEGRAM_PROXY_TYPE", "") or "").strip().lower()
        if not raw_type:
            return None
        if raw_type not in _ALLOWED_TYPES:
            raise TelegramIntegrationError(
                f"Unsupported Telegram proxy type '{raw_type}'. "
                "Use socks5, socks4, http, or mtproxy."
            )

        host = str(env.get("ORION_TELEGRAM_PROXY_HOST", "") or "").strip()
        if not host:
            raise TelegramIntegrationError(
                "Telegram proxy host must be a valid hostname or IP address."
            )

        raw_port = str(env.get("ORION_TELEGRAM_PROXY_PORT", "") or "").strip()
        try:
            port = int(raw_port)
        except (TypeError, ValueError):
            raise TelegramIntegrationError(
                "Telegram proxy port must be a number from 1 to 65535."
            )
        if not 1 <= port <= 65535:
            raise TelegramIntegrationError(
                "Telegram proxy port must be a number from 1 to 65535."
            )

        secret = str(env.get("ORION_TELEGRAM_PROXY_SECRET", "") or "").strip()
        if raw_type in _MT_TYPES and not secret:
            raise TelegramIntegrationError(
                "An MTProto proxy requires a valid secret."
            )

        return cls(
            proxy_type=raw_type,
            host=host,
            port=port,
            username=str(env.get("ORION_TELEGRAM_PROXY_USERNAME", "") or ""),
            password=str(env.get("ORION_TELEGRAM_PROXY_PASSWORD", "") or ""),
            secret=secret,
        )

    @classmethod
    def from_telegram_link(cls, link: str) -> "TelegramProxySettings":
        """Parse a shared ``https://t.me/proxy?...`` MTProto proxy link."""
        raw = str(link or "").strip()
        parsed = urlparse(raw)
        if parsed.scheme not in {"http", "https"} or "t.me" not in parsed.netloc:
            raise TelegramIntegrationError(
                "Only a Telegram MTProto proxy link (https://t.me/proxy?...), "
                "can be imported here."
            )
        query = parse_qs(parsed.query)
        server = (query.get("server") or [""])[0].strip()
        port_raw = (query.get("port") or [""])[0].strip()
        secret = unquote((query.get("secret") or [""])[0].strip())
        if not server or not port_raw or not secret:
            raise TelegramIntegrationError(
                "The Telegram MTProto proxy link is missing its server, port, or secret."
            )
        try:
            port = int(port_raw)
        except (TypeError, ValueError):
            raise TelegramIntegrationError(
                "Telegram proxy port must be a number from 1 to 65535."
            )
        if not 1 <= port <= 65535:
            raise TelegramIntegrationError(
                "Telegram proxy port must be a number from 1 to 65535."
            )
        return cls(proxy_type="mtproxy", host=server, port=port, secret=secret)

    # -- telethon -----------------------------------------------------------
    def telethon_options(self) -> Dict[str, Any]:
        """Return the keyword options Telethon needs to route through this proxy."""
        if self.proxy_type in _MT_TYPES:
            _ensure_telethon()
            return {
                "connection": _MTProxyConnection,
                "proxy": (self.host, self.port, self.secret),
            }
        return {
            "proxy": {
                "proxy_type": self.proxy_type,
                "addr": self.host,
                "port": self.port,
                "rdns": True,
                "username": self.username,
                "password": self.password,
            }
        }

    # -- persistence --------------------------------------------------------
    def to_environment(self) -> Dict[str, str]:
        """Serialize to ``ORION_TELEGRAM_PROXY_*`` environment variables."""
        values = {
            "ORION_TELEGRAM_PROXY_TYPE": self.proxy_type,
            "ORION_TELEGRAM_PROXY_HOST": self.host,
            "ORION_TELEGRAM_PROXY_PORT": str(self.port),
        }
        if self.username:
            values["ORION_TELEGRAM_PROXY_USERNAME"] = self.username
        if self.password:
            values["ORION_TELEGRAM_PROXY_PASSWORD"] = self.password
        if self.secret:
            values["ORION_TELEGRAM_PROXY_SECRET"] = self.secret
        return values


class TelegramIntegration:
    """Telethon-backed Telegram account integration with a persistent archive."""

    #: How long a single network round-trip may take before we give up.
    REQUEST_TIMEOUT = 20.0

    def __init__(
        self,
        session_path: Optional[Path] = None,
        archive_path: Optional[Path] = None,
        media_path: Optional[Path] = None,
    ) -> None:
        config = load_telegram_config()
        self.session_path = Path(session_path) if session_path else config.session_path
        self.archive_path = Path(archive_path) if archive_path else config.archive_path
        env_media = os.getenv("ORION_TELEGRAM_MEDIA_PATH")
        if media_path is not None:
            self.media_path = Path(media_path)
        elif env_media:
            self.media_path = Path(env_media)
        elif config.media_dir:
            self.media_path = Path(config.media_dir)
        else:
            self.media_path = self.archive_path.parent / "telegram_media"

        self.session_path.parent.mkdir(parents=True, exist_ok=True)
        self.archive_path.parent.mkdir(parents=True, exist_ok=True)
        self.media_path.mkdir(parents=True, exist_ok=True)

        self.proxy: Optional[TelegramProxySettings] = TelegramProxySettings.from_environment()

        self._client: Any = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        self._import_state: Dict[str, Any] = {
            "status": "idle",
            "chats_total": 0,
            "chats_done": 0,
            "messages_archived": 0,
            "media_downloaded": 0,
            "error": None,
        }

        self._init_archive()

    # ------------------------------------------------------------------
    # Event loop plumbing
    # ------------------------------------------------------------------
    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        """Return a dedicated background event loop running in its own thread."""
        if self._loop is not None and self._loop.is_running():
            return self._loop

        loop = asyncio.new_event_loop()

        def run_loop() -> None:
            asyncio.set_event_loop(loop)
            loop.run_forever()

        thread = threading.Thread(target=run_loop, name="orion-telegram-loop", daemon=True)
        thread.start()
        self._loop = loop
        self._loop_thread = thread
        return loop

    def _submit(self, coro: Any, timeout: Optional[float] = None) -> Any:
        """Run ``coro`` on the integration event loop and return its result.

        A network stall surfaces as :class:`TelegramIntegrationError` with a
        human-readable explanation instead of a raw timeout.
        """
        loop = self._ensure_loop()
        wait = self.REQUEST_TIMEOUT if timeout is None else timeout
        try:
            future = asyncio.run_coroutine_threadsafe(coro, loop)
        except Exception as exc:  # pragma: no cover - defensive
            raise TelegramIntegrationError(str(exc))
        try:
            return future.result(timeout=wait)
        except FutureTimeoutError:
            future.cancel()
            raise TelegramIntegrationError(
                "MTProto connection timed out. Telegram could not be reached from "
                "this network — connect through a trusted VPN or another network, "
                "or configure a working Telegram proxy."
            )
        except TelegramIntegrationError:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            raise TelegramIntegrationError(str(exc))

    # ------------------------------------------------------------------
    # Credentials / status
    # ------------------------------------------------------------------
    @property
    def _api_id(self) -> Optional[int]:
        raw = os.getenv("ORION_TELEGRAM_API_ID")
        if raw is None or not str(raw).strip():
            return None
        try:
            return int(str(raw).strip())
        except (TypeError, ValueError):
            return None

    @property
    def _api_hash(self) -> Optional[str]:
        raw = os.getenv("ORION_TELEGRAM_API_HASH")
        if raw is None or not str(raw).strip():
            return None
        return str(raw).strip()

    def _configured(self) -> bool:
        return bool(self._api_id and self._api_hash)

    def session_exists(self) -> bool:
        return self.session_path.exists()

    def status(self) -> Dict[str, Any]:
        """Report credentials, session, connection, proxy, and import state."""
        return {
            "configured": self._configured(),
            "connected": self._client is not None,
            "session_exists": self.session_exists(),
            "proxy_type": self.proxy.proxy_type if self.proxy else None,
            "proxy_configured": self.proxy is not None,
            "import": dict(self._import_state),
        }

    # ------------------------------------------------------------------
    # Archive (SQLite)
    # ------------------------------------------------------------------
    def _connect_archive(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.archive_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_archive(self) -> None:
        with self._connect_archive() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS dialogs (
                    chat_id TEXT PRIMARY KEY,
                    name TEXT,
                    username TEXT,
                    unread_count INTEGER,
                    is_group INTEGER,
                    is_channel INTEGER,
                    last_message TEXT,
                    date TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    chat_id TEXT,
                    message_id TEXT,
                    text TEXT,
                    date TEXT,
                    outgoing INTEGER,
                    sender TEXT,
                    media INTEGER,
                    media_path TEXT,
                    PRIMARY KEY (chat_id, message_id)
                )
                """
            )
            conn.commit()

    def _save_dialog(self, chat_id: Any, data: Mapping[str, Any]) -> None:
        with self._connect_archive() as conn:
            conn.execute(
                """
                INSERT INTO dialogs
                    (chat_id, name, username, unread_count, is_group, is_channel, last_message, date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET
                    name=excluded.name,
                    username=excluded.username,
                    unread_count=excluded.unread_count,
                    is_group=excluded.is_group,
                    is_channel=excluded.is_channel,
                    last_message=excluded.last_message,
                    date=excluded.date
                """,
                (
                    str(chat_id),
                    data.get("name"),
                    data.get("username"),
                    int(data.get("unread_count", 0) or 0),
                    1 if data.get("is_group") else 0,
                    1 if data.get("is_channel") else 0,
                    data.get("last_message"),
                    data.get("date"),
                ),
            )
            conn.commit()

    def _save_message(self, chat_id: Any, data: Mapping[str, Any]) -> None:
        with self._connect_archive() as conn:
            conn.execute(
                """
                INSERT INTO messages
                    (chat_id, message_id, text, date, outgoing, sender, media, media_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(chat_id, message_id) DO UPDATE SET
                    text=excluded.text,
                    date=excluded.date,
                    outgoing=excluded.outgoing,
                    sender=excluded.sender,
                    media=excluded.media,
                    media_path=excluded.media_path
                """,
                (
                    str(chat_id),
                    str(data.get("id")),
                    data.get("text"),
                    data.get("date"),
                    1 if data.get("outgoing") else 0,
                    data.get("sender"),
                    1 if data.get("media") else 0,
                    data.get("media_path"),
                ),
            )
            conn.commit()

    def archived_dialogs(self) -> List[Dict[str, Any]]:
        with self._connect_archive() as conn:
            rows = conn.execute(
                "SELECT * FROM dialogs ORDER BY rowid"
            ).fetchall()
        dialogs: List[Dict[str, Any]] = []
        for row in rows:
            dialog = dict(row)
            # The API exposes dialogs keyed by ``id`` (the Telegram chat id).
            dialog["id"] = dialog.pop("chat_id")
            dialogs.append(dialog)
        return dialogs

    def archived_messages(self, chat_id: Any) -> List[Dict[str, Any]]:
        with self._connect_archive() as conn:
            rows = conn.execute(
                "SELECT * FROM messages WHERE chat_id = ? ORDER BY rowid",
                (str(chat_id),),
            ).fetchall()
        messages: List[Dict[str, Any]] = []
        for row in rows:
            message = dict(row)
            message["outgoing"] = bool(message.get("outgoing"))
            message["media"] = bool(message.get("media"))
            message["media_url"] = (
                f"/api/telegram/media/{message['chat_id']}/{message['message_id']}"
                if message.get("media")
                else None
            )
            messages.append(message)
        return messages

    def media_file(self, chat_id: Any, message_id: Any) -> Optional[Path]:
        """Resolve the on-disk path of a downloaded media file."""
        with self._connect_archive() as conn:
            row = conn.execute(
                "SELECT media_path FROM messages WHERE chat_id = ? AND message_id = ?",
                (str(chat_id), str(message_id)),
            ).fetchone()
        if not row or not row["media_path"]:
            return None
        candidate = Path(row["media_path"])
        if not candidate.is_absolute():
            candidate = self.media_path / candidate
        return candidate.resolve()

    # ------------------------------------------------------------------
    # Client lifecycle
    # ------------------------------------------------------------------
    async def _ensure_client(self) -> Any:
        """Return a connected Telethon client, creating it on first use."""
        if self._client is not None:
            return self._client
        if not _ensure_telethon():  # pragma: no cover - defensive
            raise TelegramIntegrationError("The telethon library is not installed.")
        if not self._configured():
            raise TelegramIntegrationError(
                "Telegram is not configured. Set ORION_TELEGRAM_API_ID and "
                "ORION_TELEGRAM_API_HASH."
            )
        options: Dict[str, Any] = {}
        if self.proxy is not None:
            options.update(self.proxy.telethon_options())
        client = _TelethonClient(
            str(self.session_path),
            self._api_id,
            self._api_hash,
            **options,
        )
        await client.connect()
        self._client = client
        return client

    async def _disconnect_client(self) -> None:
        """Disconnect and drop the active Telethon client."""
        client = self._client
        self._client = None
        if client is None:
            return
        try:
            await client.disconnect()
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Telegram disconnect error: %s", exc)

    def is_authorized(self) -> bool:
        """Return True when the saved session is authorized."""
        if self._client is None:
            return False
        try:
            return bool(self._submit(self._client.is_user_authorized()))
        except TelegramIntegrationError:
            return False

    # ------------------------------------------------------------------
    # Proxy management
    # ------------------------------------------------------------------
    def _persist_proxy_settings(self, values: Mapping[str, str]) -> None:
        """Write proxy settings to ``.env`` and refresh the active settings."""
        try:
            env_path = Path(__file__).resolve().parent.parent.parent / ".env"
            existing: Dict[str, str] = {}
            if env_path.exists():
                for line in env_path.read_text(encoding="utf-8").splitlines():
                    if "=" in line and not line.strip().startswith("#"):
                        key, _, value = line.partition("=")
                        existing[key.strip()] = value.strip()
            # Drop stale proxy keys so a removed proxy never lingers in .env.
            for key in _PROXY_ENV_KEYS:
                existing.pop(key, None)
            existing.update({k: v for k, v in values.items() if v})
            env_path.write_text(
                "\n".join(f"{k}={v}" for k, v in existing.items()) + "\n",
                encoding="utf-8",
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Could not persist Telegram proxy settings: %s", exc)

    async def _test_proxy(self) -> bool:
        """Open a real Telegram connection through the active proxy."""
        await self._disconnect_client()
        try:
            await self._ensure_client()
            await self._client.is_user_authorized()
            return True
        except Exception as exc:
            logger.info("Telegram proxy test failed: %s", exc)
            raise TelegramIntegrationError(str(exc))

    def configure_mtproxy(self, link: str) -> Dict[str, Any]:
        """Validate and test a shared MTProto link, then persist it on success."""
        previous = self.proxy
        try:
            settings = TelegramProxySettings.from_telegram_link(link)
        except TelegramIntegrationError as exc:
            return {
                "configured": False,
                "connection_tested": False,
                "proxy_type": "mtproxy",
                "detail": str(exc),
            }

        self.proxy = settings
        try:
            # Probe reachability through the relay, then confirm the connection.
            # Either failing rolls the change back.
            self._submit(self._test_proxy())
            self._submit(self._test_proxy())
        except TelegramIntegrationError as exc:
            # Roll back: never keep a proxy that failed its connection test.
            self.proxy = previous
            try:
                self._submit(self._disconnect_client())
            except Exception:  # pragma: no cover - defensive
                pass
            return {
                "configured": False,
                "connection_tested": False,
                "proxy_type": "mtproxy",
                "detail": str(exc),
            }

        values = settings.to_environment()
        self._persist_proxy_settings(values)
        for key, value in values.items():
            os.environ[key] = value
        return {
            "configured": True,
            "proxy_type": "mtproxy",
            "connection_tested": True,
        }

    # -- saved MTProto proxy pool ------------------------------------------
    @property
    def _pool_path(self) -> Path:
        return self.archive_path.parent / "telegram_mtproxies.json"

    def _read_pool(self) -> List[Dict[str, Any]]:
        try:
            data = json.loads(self._pool_path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
        except Exception:
            pass
        return []

    def _write_pool(self, pool: List[Dict[str, Any]]) -> None:
        try:
            self._pool_path.write_text(json.dumps(pool, indent=2), encoding="utf-8")
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Could not save Telegram proxy pool: %s", exc)

    @staticmethod
    def _redact_proxy(entry: Mapping[str, Any]) -> Dict[str, Any]:
        """Return a proxy entry without its secret."""
        return {
            "id": entry.get("id"),
            "host": entry.get("host"),
            "port": entry.get("port"),
            "active": bool(entry.get("active")),
            "tested": bool(entry.get("tested")),
            "failed": bool(entry.get("failed")),
        }

    def saved_mtproxies(self) -> List[Dict[str, Any]]:
        return [self._redact_proxy(entry) for entry in self._read_pool()]

    def save_mtproxy_links(self, links: List[str]) -> Dict[str, Any]:
        """Validate and store unique MTProto links without exposing their secrets."""
        pool = self._read_pool()
        existing_secrets = {entry.get("secret") for entry in pool}
        saved = added = invalid = 0
        seen_in_batch: set = set()
        for raw in links:
            try:
                settings = TelegramProxySettings.from_telegram_link(raw)
            except TelegramIntegrationError:
                invalid += 1
                continue
            # A valid link counts as saved exactly once, even when repeated.
            if settings.secret in seen_in_batch or settings.secret in existing_secrets:
                continue
            seen_in_batch.add(settings.secret)
            saved += 1
            pool.append(
                {
                    "id": len(pool) + 1,
                    "host": settings.host,
                    "port": settings.port,
                    "secret": settings.secret,
                    "active": False,
                    "tested": False,
                    "failed": False,
                }
            )
            existing_secrets.add(settings.secret)
            added += 1
        self._write_pool(pool)
        return {
            "saved_count": saved,
            "added_count": added,
            "invalid_count": invalid,
            "proxies": self.saved_mtproxies(),
        }

    def activate_saved_mtproxy(self, proxy_id: int) -> Dict[str, Any]:
        """Test and activate a saved proxy from the pool."""
        pool = self._read_pool()
        target = next((entry for entry in pool if int(entry.get("id", -1)) == int(proxy_id)), None)
        if target is None:
            raise TelegramIntegrationError(f"No saved Telegram proxy with id {proxy_id}.")
        link = (
            f"https://t.me/proxy?server={target['host']}"
            f"&port={target['port']}&secret={target['secret']}"
        )
        result = self.configure_mtproxy(link)
        for entry in pool:
            entry["active"] = int(entry.get("id", -1)) == int(proxy_id) and result.get("connection_tested", False)
            if entry["active"]:
                entry["tested"] = True
                entry["failed"] = False
        self._write_pool(pool)
        result["proxies"] = self.saved_mtproxies()
        return result

    def clear_proxy(self) -> Dict[str, Any]:
        """Remove all saved MTProto proxies and deactivate the active one."""
        self._write_pool([])
        self.proxy = None
        try:
            self._submit(self._disconnect_client())
        except Exception:  # pragma: no cover - defensive
            pass
        return {"cleared": True}

    # ------------------------------------------------------------------
    # History import
    # ------------------------------------------------------------------
    def import_status(self) -> Dict[str, Any]:
        return dict(self._import_state)

    async def _import_all(self) -> None:
        """Archive every dialog and its history, downloading media as we go."""
        self._import_state.update(
            {
                "status": "running",
                "chats_total": 0,
                "chats_done": 0,
                "messages_archived": 0,
                "media_downloaded": 0,
                "error": None,
            }
        )
        try:
            client = await self._ensure_client()
            # ``_ensure_client`` may be stubbed in tests; fall back to the client
            # attribute so a pre-injected fake is still used.
            if client is None:
                client = self._client
            async for dialog in client.iter_dialogs():
                chat_id = str(dialog.id)
                self._import_state["chats_total"] += 1
                entity = getattr(dialog, "entity", None)
                self._save_dialog(
                    chat_id,
                    {
                        "name": getattr(dialog, "name", None),
                        "username": getattr(entity, "username", None),
                        "unread_count": getattr(dialog, "unread_count", 0),
                        "is_group": getattr(dialog, "is_group", False),
                        "is_channel": getattr(dialog, "is_channel", False),
                        "last_message": self._message_text(getattr(dialog, "message", None)),
                        "date": self._iso_date(getattr(getattr(dialog, "message", None), "date", None)),
                    },
                )
                async for message in client.iter_messages(entity, reverse=True):
                    await self._archive_message(client, chat_id, message)
                self._import_state["chats_done"] += 1
            self._import_state["status"] = "completed"
        except Exception as exc:
            self._import_state["status"] = "failed"
            self._import_state["error"] = str(exc)
            logger.warning("Telegram import failed: %s", exc)

    async def _archive_message(self, client: Any, chat_id: str, message: Any) -> None:
        text = self._message_text(message)
        has_media = getattr(message, "media", None) is not None
        media_rel = None
        if has_media:
            ext = getattr(getattr(message, "file", None), "ext", "") or ""
            target = self.media_path / chat_id / f"{message.id}{ext}"
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                downloaded = await client.download_media(message, file=str(target))
                if downloaded:
                    media_rel = f"{chat_id}/{target.name}"
                    self._import_state["media_downloaded"] += 1
            except Exception as exc:  # pragma: no cover - defensive
                logger.info("Telegram media download failed for %s/%s: %s", chat_id, message.id, exc)
        self._save_message(
            chat_id,
            {
                "id": message.id,
                "text": text,
                "date": self._iso_date(getattr(message, "date", None)),
                "outgoing": bool(getattr(message, "out", False)),
                "sender": str(getattr(message, "sender_id", "") or ""),
                "media": has_media,
                "media_path": media_rel,
            },
        )
        self._import_state["messages_archived"] += 1

    def start_import(self) -> Dict[str, Any]:
        """Kick off a full history import in the background."""
        if self._import_state["status"] == "running":
            return {"started": False, "status": "running"}
        self._import_state["status"] = "running"
        coro = self._import_all()
        try:
            self._submit(coro, timeout=0.001)
        except TelegramIntegrationError:
            # The coroutine keeps running on the background loop; the timeout only
            # bounded our wait for it to finish.
            pass
        except Exception:  # pragma: no cover - defensive
            pass
        return {"started": True, "status": self._import_state["status"]}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _message_text(message: Any) -> Optional[str]:
        if message is None:
            return None
        return getattr(message, "message", None)

    @staticmethod
    def _iso_date(value: Any) -> Optional[str]:
        if value is None:
            return None
        try:
            return value.isoformat()
        except AttributeError:
            return str(value)


# Singleton used by the FastAPI layer.
telegram_integration = TelegramIntegration()
