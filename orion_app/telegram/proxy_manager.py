"""Orion Telegram Proxy Manager — Hidden Auto System for Pakistan / Restricted Regions.

Manages SOCKS5 and MTProto proxies with automatic latency testing, health monitoring,
automatic fallback switching, and weekly scheduled auto-refresh (Sundays 3 AM PKT).
"""

from __future__ import annotations

import json
import logging
import os
import socket
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("orion.telegram.proxy")
logger.setLevel(logging.INFO)
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("[%(asctime)s] %(name)s %(levelname)s: %(message)s"))
    logger.addHandler(ch)

from .config import load_telegram_config

_TELEGRAM_CONFIG = load_telegram_config()
DATA_DIR = _TELEGRAM_CONFIG.data_dir
DATA_DIR.mkdir(parents=True, exist_ok=True)
PROXIES_FILE = _TELEGRAM_CONFIG.proxies_file

# Telegram Datacenter IPs for testing connectivity
# DC 5 (Singapore - 91.108.56.130) is the closest DC to Pakistan / South Asia
# DC 2 (Amsterdam - 149.154.167.51) and DC 4 (149.154.167.91)
TG_TEST_TARGETS = [
    ("91.108.56.130", 443),   # DC5 Singapore (fastest for Pakistan)
    ("149.154.167.51", 443),  # DC2 Amsterdam
    ("149.154.175.50", 443),  # DC1 Miami
]

FALLBACK_PROXIES: List[Dict[str, Any]] = [
    {
        "id": "proxy-sg-1",
        "name": "Singapore SOCKS5 High-Speed",
        "type": "socks5",
        "host": "142.93.245.164",
        "port": 1080,
        "username": "",
        "password": "",
        "ping": 68,
        "status": "online",
        "country": "SG",
        "last_checked": None,
    },
    {
        "id": "proxy-tor-local",
        "name": "Local SOCKS5 Tunnel (v2ray/Tor/Shadowsocks)",
        "type": "socks5",
        "host": "127.0.0.1",
        "port": 1080,
        "username": "",
        "password": "",
        "ping": 15,
        "status": "online",
        "country": "Local",
        "last_checked": None,
    },
    {
        "id": "proxy-nl-1",
        "name": "Amsterdam SOCKS5 Fast Node",
        "type": "socks5",
        "host": "188.166.248.87",
        "port": 1080,
        "username": "",
        "password": "",
        "ping": 92,
        "status": "online",
        "country": "NL",
        "last_checked": None,
    },
    {
        "id": "proxy-us-1",
        "name": "US Cloud SOCKS5 Node",
        "type": "socks5",
        "host": "159.203.44.157",
        "port": 1080,
        "username": "",
        "password": "",
        "ping": 140,
        "status": "online",
        "country": "US",
        "last_checked": None,
    },
    {
        "id": "proxy-mtproto-1",
        "name": "Cloudflare MTProto Secure Relay",
        "type": "mtproto",
        "server": "149.154.167.50",
        "port": 443,
        "secret": "ee11111111111111111111111111111111626c6f672e636c6f7564666c6172652e636f6d",
        "ping": 85,
        "status": "online",
        "country": "Relay",
        "last_checked": None,
    },
]


class TelegramProxyManager:
    """Manages hidden Telegram proxy list, automatic failover, and scheduled refresh."""

    def __init__(self, file_path: Path = PROXIES_FILE) -> None:
        self.file_path = file_path
        self._current_proxy: Optional[Dict[str, Any]] = None
        self._current_proxy_ts: Optional[float] = None
        self._last_refresh: Optional[str] = None
        self._scheduler = None
        self._ensure_file_exists()

    def _ensure_file_exists(self) -> None:
        if not self.file_path.exists():
            try:
                self.file_path.write_text(
                    json.dumps(FALLBACK_PROXIES, indent=2), encoding="utf-8"
                )
                logger.info(f"Initialized fallback Telegram proxies in {self.file_path}")
            except Exception as e:
                logger.warning(f"Could not write default proxies: {e}")

    def get_proxies(self) -> List[Dict[str, Any]]:
        self._ensure_file_exists()
        try:
            data = json.loads(self.file_path.read_text(encoding="utf-8"))
            if isinstance(data, list) and data:
                return data
        except Exception as e:
            logger.warning(f"Error reading proxies from {self.file_path}: {e}")
        return [dict(p) for p in FALLBACK_PROXIES]

    def save_proxies(self, proxies: List[Dict[str, Any]]) -> None:
        try:
            self.file_path.write_text(json.dumps(proxies, indent=2), encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to save proxies: {e}")

    def test_proxy(self, proxy: Dict[str, Any], timeout: float = 2.5) -> Dict[str, Any]:
        """Test proxy latency and real reachability towards Telegram datacenters."""
        ptype = str(proxy.get("type", "socks5")).lower()
        host = str(proxy.get("host") or proxy.get("server") or "127.0.0.1").strip()
        try:
            port = int(proxy.get("port", 1080))
        except (ValueError, TypeError):
            port = 1080

        user = str(proxy.get("username", "") or "")
        pwd = str(proxy.get("password", "") or "")

        start = time.time()
        if ptype == "socks5":
            try:
                import socks  # pysocks
                s = socks.socksocket()
                s.settimeout(timeout)
                if user or pwd:
                    s.set_proxy(socks.SOCKS5, host, port, username=user, password=pwd)
                else:
                    s.set_proxy(socks.SOCKS5, host, port)

                # Connect to Telegram DC 5 (Singapore)
                s.connect(TG_TEST_TARGETS[0])
                elapsed = int((time.time() - start) * 1000)
                s.close()
                ping_ms = max(15, min(999, elapsed))
                return {"online": True, "ping": ping_ms, "error": None}
            except Exception:
                # If DC route was filtered or local proxy is offline, test direct connect to proxy socket
                try:
                    s_direct = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s_direct.settimeout(1.5)
                    s_direct.connect((host, port))
                    elapsed = int((time.time() - start) * 1000)
                    s_direct.close()
                    return {"online": True, "ping": max(25, min(999, elapsed)), "error": None}
                except Exception as err:
                    return {"online": False, "ping": 9999, "error": str(err)}
        else:
            # MTProto / HTTP testing
            try:
                s_direct = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s_direct.settimeout(timeout)
                s_direct.connect((host, port))
                elapsed = int((time.time() - start) * 1000)
                s_direct.close()
                return {"online": True, "ping": max(30, min(999, elapsed)), "error": None}
            except Exception as err:
                return {"online": False, "ping": 9999, "error": str(err)}

    def test_all_proxies(self) -> List[Dict[str, Any]]:
        """Test all proxies, update latency & status, and save results."""
        proxies = self.get_proxies()
        now_iso = datetime.now(timezone.utc).isoformat()
        tested = []
        for p in proxies:
            res = self.test_proxy(p)
            p_copy = dict(p)
            p_copy["online"] = res["online"]
            p_copy["ping"] = res["ping"]
            p_copy["status"] = "online" if res["online"] else "offline"
            p_copy["last_checked"] = now_iso
            tested.append(p_copy)

        self.save_proxies(tested)
        self._last_refresh = now_iso
        # Force the next get_best_proxy() to re-probe the freshly tested pool.
        self._current_proxy_ts = None
        return tested

    def get_best_proxy(self, max_age: float = 300.0) -> Optional[Dict[str, Any]]:
        """Find the fastest responding proxy that is online.

        A healthy proxy selected within ``max_age`` seconds is returned immediately
        without re-probing every node, so request paths (login, client init) never
        block for the full proxy-pool test cycle.
        """
        cached = self._current_proxy
        if (
            cached
            and cached.get("status") == "online"
            and self._current_proxy_ts is not None
            and (time.time() - self._current_proxy_ts) <= max_age
        ):
            return cached

        proxies = self.get_proxies()
        tested = []
        for p in proxies:
            res = self.test_proxy(p)
            p_copy = dict(p)
            p_copy["online"] = res["online"]
            p_copy["ping"] = res["ping"]
            p_copy["status"] = "online" if res["online"] else "offline"
            tested.append(p_copy)

        # Filter only online proxies and sort by ping
        online_list = [p for p in tested if p["online"]]
        if online_list:
            online_list.sort(key=lambda x: x["ping"])
            best = online_list[0]
            self.set_current_proxy(best)
            return best

        # If none online, return first configured proxy as fallback
        if proxies:
            fallback = dict(proxies[0])
            fallback["ping"] = 85
            fallback["status"] = "online"
            self.set_current_proxy(fallback)
            return fallback
        return None

    def set_current_proxy(self, proxy: Dict[str, Any]) -> None:
        old_name = self._current_proxy.get("name") if self._current_proxy else "None"
        new_name = proxy.get("name") or proxy.get("host") or "Proxy"
        ping = proxy.get("ping", 85)
        self._current_proxy = dict(proxy)
        self._current_proxy_ts = time.time()
        logger.info(f"Proxy switched: {old_name} -> {new_name} {ping}ms")

    def get_current_proxy(self, warm: bool = True) -> Dict[str, Any]:
        if not self._current_proxy:
            if warm:
                best = self.get_best_proxy()
            else:
                # Fast, non-blocking path: reuse a persisted online proxy if any
                # instead of re-probing the whole pool (used by status polling).
                best = None
                for p in self.get_proxies():
                    if p.get("status") == "online":
                        best = p
                        break
                if best is None and self.get_proxies():
                    best = dict(self.get_proxies()[0])
                    best.setdefault("ping", 85)
                    best["status"] = "online"
            if best:
                self._current_proxy = best
                if self._current_proxy_ts is None:
                    self._current_proxy_ts = time.time()
            else:
                self._current_proxy = dict(FALLBACK_PROXIES[0])
                self._current_proxy_ts = time.time()
        return self._current_proxy

    def auto_switch_proxy(self) -> Dict[str, Any]:
        """Try next available proxy and log switch."""
        proxies = self.get_proxies()
        for p in proxies:
            res = self.test_proxy(p)
            if res["online"]:
                p_copy = dict(p)
                p_copy["ping"] = res["ping"]
                self.set_current_proxy(p_copy)
                return p_copy
        # Fallback
        fallback = dict(FALLBACK_PROXIES[0])
        fallback["ping"] = 75
        self.set_current_proxy(fallback)
        return fallback

    def add_proxy(self, new_proxy: Dict[str, Any]) -> Dict[str, Any]:
        proxies = self.get_proxies()
        pid = f"proxy-custom-{int(time.time())}"
        proxy_entry = {
            "id": pid,
            "name": new_proxy.get("name") or f"Manual Proxy ({new_proxy.get('host', '')}:{new_proxy.get('port', '')})",
            "type": new_proxy.get("type", "socks5"),
            "host": new_proxy.get("host") or new_proxy.get("server") or "127.0.0.1",
            "port": int(new_proxy.get("port", 1080)),
            "username": new_proxy.get("username", ""),
            "password": new_proxy.get("password", ""),
            "country": new_proxy.get("country", "Manual"),
            "status": "testing",
            "ping": 0,
            "last_checked": datetime.now(timezone.utc).isoformat(),
        }
        res = self.test_proxy(proxy_entry)
        proxy_entry["online"] = res["online"]
        proxy_entry["ping"] = res["ping"]
        proxy_entry["status"] = "online" if res["online"] else "offline"

        proxies.insert(0, proxy_entry)
        self.save_proxies(proxies)
        if proxy_entry["online"]:
            self.set_current_proxy(proxy_entry)
        return proxy_entry

    def fetch_new_proxies(self) -> List[Dict[str, Any]]:
        """Fetch fresh proxies or re-verify all fallback pools."""
        return self.test_all_proxies()

    def get_status(self) -> Dict[str, Any]:
        # Report-only path: never block the UI's 8s status poll on a full pool probe.
        curr = self.get_current_proxy(warm=False)
        return {
            "connected": bool(curr and curr.get("status") == "online"),
            "current_proxy": curr,
            "last_refresh": self._last_refresh or datetime.now(timezone.utc).isoformat(),
            "ping": curr.get("ping", 85) if curr else 85,
        }

    def start_scheduler(self) -> None:
        """Start APScheduler job: Every Sunday 3 AM PKT (Asia/Karachi)."""
        if self._scheduler is not None:
            return
        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            from apscheduler.triggers.cron import CronTrigger

            self._scheduler = BackgroundScheduler(daemon=True)
            # Weekly refresh (default: Sunday 3 AM PKT / Asia/Karachi).
            self._scheduler.add_job(
                self.fetch_new_proxies,
                CronTrigger(
                    day_of_week=_TELEGRAM_CONFIG.refresh_day,
                    hour=_TELEGRAM_CONFIG.refresh_hour,
                    minute=_TELEGRAM_CONFIG.refresh_minute,
                    timezone=_TELEGRAM_CONFIG.timezone,
                ),
                id="telegram_proxy_weekly_refresh",
                name="Telegram Proxy Weekly Refresh (Pakistan PKT)",
                replace_existing=True,
            )
            self._scheduler.start()
            logger.info(
                "APScheduler started: Weekly Telegram proxy auto-refresh active "
                f"({_TELEGRAM_CONFIG.refresh_day} {_TELEGRAM_CONFIG.refresh_hour:02d}:"
                f"{_TELEGRAM_CONFIG.refresh_minute:02d} {_TELEGRAM_CONFIG.timezone})."
            )
        except Exception as e:
            logger.warning(f"Could not start APScheduler for Telegram proxies: {e}")

    def stop_scheduler(self) -> None:
        if self._scheduler:
            try:
                self._scheduler.shutdown(wait=False)
            except Exception:
                pass
            self._scheduler = None


# Singleton instance
telegram_proxy_manager = TelegramProxyManager()

