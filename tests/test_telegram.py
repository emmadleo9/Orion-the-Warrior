"""Tests for the Orion Telegram module (client, routes, proxies).

These exercise the *API surface* of :class:`OrionTelegramClient` — the methods the
``/api/telegram/*`` routes call — without ever making a live MTProto handshake.
Live mode is opt-in (``ORION_TELEGRAM_LIVE=1``), so every method must return a
usable dict/list payload in local/demo mode and never raise ``AttributeError``.
"""

from __future__ import annotations

import re
import threading
from pathlib import Path

import pytest


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """A demo-mode Telegram client writing into a per-test data dir."""
    monkeypatch.delenv("ORION_TELEGRAM_LIVE", raising=False)
    from orion_app.telegram.client import OrionTelegramClient

    return OrionTelegramClient(workdir=tmp_path)


def test_every_route_method_exists_on_the_client(client):
    """Every ``telegram_client.<method>`` referenced by routes.py must exist."""
    routes_src = (
        Path(__file__).resolve().parent.parent / "orion_app" / "telegram" / "routes.py"
    ).read_text(encoding="utf-8")
    names = sorted(set(re.findall(r"telegram_client\.(\w+)", routes_src)))
    assert names, "routes.py should call telegram_client methods"
    missing = [name for name in names if not hasattr(client, name)]
    assert missing == []


def test_get_status_reports_real_state_in_demo_mode(client):
    status = client.get_status()
    # No live session, so the client is not 'connected' nor 'authorized'.
    assert status["connected"] is False
    assert status["authorized"] is False
    assert status["live_enabled"] is False
    assert status["pyrogram_available"] in (True, False)
    # A proxy is always reported from the managed pool.
    assert status["current_proxy"] is not None
    assert isinstance(status["ping"], int)


def test_sync_returns_profile_chats_and_contacts(client):
    snapshot = client.sync()
    assert set(snapshot) == {"status", "me", "chats", "contacts"}
    assert snapshot["me"]["first_name"]
    assert isinstance(snapshot["chats"], list) and snapshot["chats"]
    assert isinstance(snapshot["contacts"], list)


def test_send_message_returns_a_message_dict(client):
    message = client.send_message(-100192837482, "hello from Orion")
    assert isinstance(message, dict)
    assert message["text"] == "hello from Orion"
    assert message["outgoing"] is True
    assert message["chat_id"] == -100192837482
    # The sent message is persisted into the local history.
    history = client.get_messages(-100192837482)
    assert history[-1]["text"] == "hello from Orion"


@pytest.mark.parametrize(
    "method, args",
    [
        ("get_me", ()),
        ("get_me_photo", ()),
        ("get_chats", ()),
        ("get_contacts", ()),
        ("get_blocked_users", ()),
        ("get_my_bots", ()),
        ("get_updates", ()),
    ],
)
def test_read_methods_return_valid_types(client, method, args):
    result = getattr(client, method)(*args)
    assert isinstance(result, (list, dict))


@pytest.mark.parametrize(
    "method, args",
    [
        ("pin_message", (11, 22)),
        ("unpin_message", (11,)),
        ("forward_messages", (11, 22, [33])),
        ("edit_message", (11, 22, "new text")),
        ("reply_message", (11, 22, "a reply")),
        ("join_chat", ()),
        ("leave_chat", (11,)),
        ("archive_chat", (11,)),
        ("mute_chat", (11,)),
        ("block_user", (11,)),
        ("set_typing", (11,)),
        ("download_media", (11, 22)),
        ("invite_to_chat", (11, [22, 33])),
        ("promote_admin", (11, 22)),
        ("demote_admin", (11, 22)),
    ],
)
def test_action_methods_return_dicts_in_demo_mode(client, method, args):
    result = getattr(client, method)(*args)
    assert isinstance(result, dict)


def test_forward_message_alias_matches_forward_messages(client):
    via_alias = client.forward_message(11, 22, 33)
    direct = client.forward_messages(11, 22, 33)
    assert isinstance(via_alias, dict)
    assert via_alias["forwarded"] == direct["forwarded"] == 1


def test_create_group_and_channel_return_chat_dicts(client):
    group = client.create_group("Orion Test Group", user_ids=[1, 2])
    assert group["title"] == "Orion Test Group"
    assert group["type"] == "group"

    channel = client.create_group("Orion Test Channel", is_channel=True)
    assert channel["type"] == "channel"


def test_search_and_history_are_non_destructive(client):
    assert client.search_chats("")  # empty query returns the chat list
    assert client.search_global("proxy") == {"query": "proxy", "results": [], "count": 0}
    assert client.search_messages(-100192837482, "proxy") == []
    assert isinstance(client.get_chat_history(-100192837482), list)


def test_get_updates_drains_the_event_queue(client):
    client._events_queue.put({"id": 1, "text": "hi"})
    client._events_queue.put({"id": 2, "text": "there"})
    updates = client.get_updates(limit=10)
    assert [u["id"] for u in updates] == [1, 2]
    assert client.get_updates() == []


def test_logout_clears_session_state(client, monkeypatch):
    client._is_authorized = True
    client._is_connected = True
    client._me_cache = {"first_name": "Orion"}
    result = client.logout()
    assert result["status"] == "logged_out"
    assert client._is_authorized is False
    assert client._is_connected is False
    assert client._me_cache is None


def test_demo_edit_profile_updates_profile(client):
    updated = client.edit_profile("Festus", "Warrior", "Orion operator")
    assert updated["first_name"] == "Festus"
    assert updated["last_name"] == "Warrior"
    assert client.get_me()["first_name"] == "Festus"
