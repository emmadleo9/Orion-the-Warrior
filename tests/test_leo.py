"""Tests for Leo Valdez assistant integration and routes."""

from fastapi.testclient import TestClient
import pytest

from orion_app.ai import LeoAssistant, ZaraAssistant
from orion_app import main as main_module


@pytest.fixture
def test_client():
    return TestClient(main_module.app)


def test_leo_assistant_alias():
    assert ZaraAssistant is LeoAssistant
    leo = LeoAssistant()
    assert leo.name == "Leo Valdez"
    assert "Leo Valdez" in LeoAssistant.SYSTEM_PROMPT


def test_api_leo_status(test_client, monkeypatch):
    monkeypatch.setattr(main_module.leo, "model_status", lambda: {
        "assistant_name": "Leo Valdez",
        "model": "qwen2.5:3b",
        "ollama_reachable": True,
        "installed_models": ["qwen2.5:3b"],
        "status_text": "🔥 Leo online · qwen2.5:3b",
    })

    res = test_client.get("/api/leo/status")
    assert res.status_code == 200
    data = res.json()
    assert data["assistant_name"] == "Leo Valdez"
    assert data["status_text"] == "🔥 Leo online · qwen2.5:3b"

    # Backwards-compatible route
    res_zara = test_client.get("/api/zara/status")
    assert res_zara.status_code == 200
    assert res_zara.json()["assistant_name"] == "Leo Valdez"


def test_api_leo_memory_clear(test_client):
    res = test_client.delete("/api/leo/memory/test-conv")
    assert res.status_code == 200
    assert res.json()["cleared"] is True


def test_index_html_contains_leo_valdez(test_client):
    res = test_client.get("/")
    assert res.status_code == 200
    html = res.text
    assert "Leo Valdez" in html
    assert "leo-messages" in html
    assert "Chat with Leo Valdez" in html

