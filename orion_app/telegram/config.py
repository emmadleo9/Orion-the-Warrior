"""Configuration for the Orion Telegram module (Social Hub).

All Telegram settings are resolved from the environment (shell or ``.env``) with
safe defaults, so the module runs in local/demo mode with no setup and upgrades
to a live connection when credentials are provided.

Environment variables
---------------------
``ORION_TELEGRAM_API_ID``      Telegram API id (defaults to the public Desktop id).
``ORION_TELEGRAM_API_HASH``    Telegram API hash.
``ORION_TELEGRAM_LIVE``        ``1`` enables real MTProto handshakes (opt-in).
``ORION_TELEGRAM_SESSION``     Session file name (stored in the Telegram data dir).
``ORION_TELEGRAM_MEDIA_PATH``  Where downloaded media is cached.
``ORION_TELEGRAM_REFRESH_DAY`` Weekly proxy refresh day (default ``sun``).
``ORION_TELEGRAM_REFRESH_HOUR``Weekly proxy refresh hour, 24h (default ``3``).
``ORION_TELEGRAM_TIMEZONE``    Timezone for the refresh job (default ``Asia/Karachi``).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Optional

# Public Telegram Desktop credentials — usable without registering an app.
DEFAULT_API_ID = 2040
DEFAULT_API_HASH = "b18441a1ff607e10a989891a5462e627"

# Windows/macOS get a per-user data dir; elsewhere fall back to the project tree.
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"


def _data_dir() -> Path:
    """Directory holding Telegram session files, archives, and proxy lists."""
    override = os.getenv("ORION_TELEGRAM_DATA_DIR")
    base = Path(override).expanduser() if override else DEFAULT_DATA_DIR
    return base


@dataclass(frozen=True)
class TelegramConfig:
    """Resolved, immutable Telegram configuration."""

    api_id: int = DEFAULT_API_ID
    api_hash: str = DEFAULT_API_HASH
    live: bool = False
    session_name: str = "orion_telegram"
    data_dir: Path = field(default_factory=_data_dir)
    media_dir: Optional[Path] = None
    refresh_day: str = "sun"
    refresh_hour: int = 3
    refresh_minute: int = 0
    timezone: str = "Asia/Karachi"

    @property
    def session_path(self) -> Path:
        """Full path to the Pyrogram/Telegram session file."""
        return self.data_dir / f"{self.session_name}.session"

    @property
    def proxies_file(self) -> Path:
        """JSON file holding the managed proxy pool."""
        return self.data_dir / "telegram_proxies.json"

    @property
    def archive_path(self) -> Path:
        """SQLite archive of dialogs and messages."""
        return self.data_dir / "telegram_archive.sqlite3"

    def ensure_dirs(self) -> None:
        """Create the data/media directories if they do not exist yet."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        if self.media_dir:
            self.media_dir.mkdir(parents=True, exist_ok=True)


def _env_bool(source: Mapping[str, str], key: str, default: bool = False) -> bool:
    raw = source.get(key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(source: Mapping[str, str], key: str, default: int) -> int:
    raw = source.get(key)
    if raw is None:
        return default
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        return default


def load_telegram_config(source: Optional[Mapping[str, str]] = None) -> TelegramConfig:
    """Build a :class:`TelegramConfig` from ``source`` (defaults to ``os.environ``)."""
    env: Mapping[str, str] = os.environ if source is None else source
    media_override = env.get("ORION_TELEGRAM_MEDIA_PATH")

    config = TelegramConfig(
        api_id=_env_int(env, "ORION_TELEGRAM_API_ID", DEFAULT_API_ID),
        api_hash=env.get("ORION_TELEGRAM_API_HASH", DEFAULT_API_HASH).strip() or DEFAULT_API_HASH,
        live=_env_bool(env, "ORION_TELEGRAM_LIVE", False),
        session_name=env.get("ORION_TELEGRAM_SESSION", "orion_telegram").strip() or "orion_telegram",
        media_dir=Path(media_override).expanduser() if media_override else None,
        refresh_day=env.get("ORION_TELEGRAM_REFRESH_DAY", "sun").strip().lower() or "sun",
        refresh_hour=_env_int(env, "ORION_TELEGRAM_REFRESH_HOUR", 3),
        refresh_minute=_env_int(env, "ORION_TELEGRAM_REFRESH_MINUTE", 0),
        timezone=env.get("ORION_TELEGRAM_TIMEZONE", "Asia/Karachi").strip() or "Asia/Karachi",
    )
    return config
