"""Tests for Orion built-in Instagram inbox integration and UI routes."""

import io
import json
import time
from fastapi.testclient import TestClient
import pytest

from orion_app.instagram import InstagramError, InstagramIntegration, InstagramToken, InstagramManager
from orion_app import main as main_module


@pytest.fixture
def test_client():
    return TestClient(main_module.app)


def test_instagram_manager_alias():
    assert InstagramManager is InstagramIntegration


def test_get_conversations_returns_empty_when_not_connected():
    integration = InstagramIntegration()
    assert integration.get_conversations() == []
    assert integration.get_user_profile() == {}


def test_get_conversations_with_token(monkeypatch):
    integration = InstagramIntegration()
    integration._token = InstagramToken(
        "mock-token",
        "mock-user-123",
        time.time() + 3600,
        ("instagram_business_manage_messages",),
    )

    mock_conversations = [
        {
            "id": "conv-1",
            "snippet": "Hello Orion",
            "updated_time": "2026-10-10T12:00:00+00:00",
            "participants": {"data": [{"id": "user-2", "username": "alice"}]},
            "messages": {"data": [{"id": "m1", "message": "Hello Orion"}]},
        }
    ]

    requests_made = []

    def fake_urlopen(request, timeout=20):
        requests_made.append(request)
        return io.BytesIO(json.dumps({"data": mock_conversations}).encode("utf-8"))

    import orion_app.instagram as instagram_mod
    monkeypatch.setattr(instagram_mod, "urlopen", fake_urlopen)

    convs = integration.get_conversations()
    assert len(convs) == 1
    assert convs[0]["id"] == "conv-1"
    assert convs[0]["snippet"] == "Hello Orion"


def test_send_message_with_text_kwarg(monkeypatch):
    integration = InstagramIntegration()
    integration._token = InstagramToken(
        "mock-token",
        "mock-user-123",
        time.time() + 3600,
        ("instagram_business_manage_messages",),
    )

    requests_made = []

    def fake_urlopen(request, timeout=20):
        requests_made.append(request)
        return io.BytesIO(b'{"recipient_id": "user-2", "message_id": "mid.123"}')

    import orion_app.instagram as instagram_mod
    monkeypatch.setattr(instagram_mod, "urlopen", fake_urlopen)

    res = integration.send_message("user-2", text="Hello from Orion")
    assert res["message_id"] == "mid.123"


def test_api_instagram_inbox_disconnected(test_client, monkeypatch):
    integration = InstagramIntegration()
    monkeypatch.setattr(main_module, "instagram", integration)

    res = test_client.get("/api/instagram/inbox")
    assert res.status_code == 200
    data = res.json()
    assert "connected" in data
    assert data["connected"] is False
    assert data["conversations"] == []


def test_api_instagram_inbox_connected(test_client, monkeypatch):
    integration = InstagramIntegration()
    integration._token = InstagramToken(
        "mock-token",
        "mock-user-123",
        time.time() + 3600,
        ("instagram_business_manage_messages",),
    )
    monkeypatch.setattr(integration, "get_conversations", lambda: [{"id": "c1", "snippet": "Test"}])
    monkeypatch.setattr(main_module, "instagram", integration)

    res = test_client.get("/api/instagram/inbox")
    assert res.status_code == 200
    data = res.json()
    assert data["connected"] is True
    assert len(data["conversations"]) == 1


def test_api_instagram_conversation_messages(test_client, monkeypatch):
    integration = InstagramIntegration()
    integration._token = InstagramToken(
        "mock-token",
        "mock-user-123",
        time.time() + 3600,
        ("instagram_business_manage_messages",),
    )
    monkeypatch.setattr(
        integration,
        "conversation_messages",
        lambda cid: {"id": cid, "messages": {"data": [{"id": "m1", "message": "Hi"}]}},
    )
    monkeypatch.setattr(main_module, "instagram", integration)

    res = test_client.get("/api/instagram/conversation/c1/messages")
    assert res.status_code == 200
    data = res.json()
    assert data["conversation_id"] == "c1"
    assert len(data["messages"]) == 1
    assert data["messages"][0]["message"] == "Hi"


def test_api_instagram_send(test_client, monkeypatch):
    integration = InstagramIntegration()
    integration._token = InstagramToken(
        "mock-token",
        "mock-user-123",
        time.time() + 3600,
        ("instagram_business_manage_messages",),
    )
    monkeypatch.setattr(
        integration,
        "send_message",
        lambda recipient_id, text="", message="": {"recipient_id": recipient_id, "message_id": "mid.abc"},
    )
    monkeypatch.setattr(main_module, "instagram", integration)

    # Test with "message" field
    res = test_client.post("/api/instagram/send", json={"recipient_id": "user-9", "message": "Hey"})
    assert res.status_code == 200
    assert res.json()["message_id"] == "mid.abc"

    # Test with "text" field
    res = test_client.post("/api/instagram/send", json={"recipient_id": "user-9", "text": "Hey 2"})
    assert res.status_code == 200
    assert res.json()["message_id"] == "mid.abc"


def test_get_instagram_html_view(test_client):
    res = test_client.get("/instagram")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    html = res.text
    assert "https://cdn.tailwindcss.com" in html
    assert "#020d08" in html
    assert "#041a12" in html
    assert "#00ff9d" in html
    assert "Always stored locally in Orion" in html
    assert "Instagram Direct" in html


def test_dashboard_contains_builtin_instagram_button(test_client):
    res = test_client.get("/")
    assert res.status_code == 200
    html = res.text
    assert 'href="/instagram"' in html
    assert "Open Built-in Instagram" in html

