"""Orion Telegram — the Telegram module of the Social Hub.

Every piece of Telegram functionality in Orion lives inside this package and is
surfaced through the Telegram tab of the Social Hub. Nothing Telegram-related is
implemented outside ``orion_app/telegram``.

Layout
------
``client``        High-level Telegram client (Pyrogram) with demo/local fallback.
``integration``   Telethon-backed account integration with archive and proxy pool.
``proxy_manager`` Hidden auto-proxy engine for restricted regions (e.g. Pakistan).
``config``        Environment/configuration loading for the Telegram module.

The singletons below are what the FastAPI layer imports::

    from .telegram import telegram_client, telegram_integration
"""

from __future__ import annotations

from .client import OrionTelegramClient, telegram_client
from .config import TelegramConfig, load_telegram_config
from .integration import (
    TelegramIntegration,
    TelegramIntegrationError,
    TelegramProxySettings,
    telegram_integration,
)
from .proxy_manager import TelegramProxyManager, telegram_proxy_manager

__all__ = [
    "OrionTelegramClient",
    "telegram_client",
    "TelegramIntegration",
    "TelegramIntegrationError",
    "TelegramProxySettings",
    "telegram_integration",
    "TelegramProxyManager",
    "telegram_proxy_manager",
    "TelegramConfig",
    "load_telegram_config",
]
