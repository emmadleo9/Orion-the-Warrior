import json
import sys
from io import BytesIO
from types import ModuleType, SimpleNamespace
from urllib.error import URLError

import pytest
from PIL import Image

import orion_app.ai as ai_module
from orion_app.ai import NicoAssistant
from orion_app.devices import DeviceManager
from orion_app.memory import ConversationMemory


def test_nico_can_answer_a_user_prompt():
    assistant = NicoAssistant("Nico de Angelo")
    response = assistant.respond("Summarize my day and prepare a next action")

    assert response["assistant_name"] == "Nico de Angelo"
    assert "Summary" in response["message"]
    assert "Next action" in response["message"]


def test_nico_chat_sends_conversation_to_local_model(monkeypatch, tmp_path):
    response_body = BytesIO(
        json.dumps({"message": {"content": "Hello! Ready when you are."}}).encode()
    )
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["body"] = json.loads(request.data)
        captured["timeout"] = timeout
        return response_body

    monkeypatch.setattr(ai_module, "urlopen", fake_urlopen)
    assistant = NicoAssistant(output_dir=str(tmp_path))
    result = assistant.chat(
        "What did I ask you?",
        [{"role": "user", "content": "Remember this detail"}],
    )

    assert result["assistant_name"] == "Nico de Angelo"
    assert result["message"] == "Hello! Ready when you are."
    assert captured["url"] == "http://127.0.0.1:11434/api/chat"
    assert captured["body"]["model"] == "qwen2.5:3b"
    assert captured["body"]["messages"][-2]["content"] == "Remember this detail"
    assert captured["body"]["messages"][-1]["content"] == "What did I ask you?"
    assert captured["timeout"] == 120


def test_nico_chat_reports_unavailable_local_model(monkeypatch, tmp_path):
    def fail_urlopen(_request, timeout):
        raise URLError("connection refused")

    monkeypatch.setattr(ai_module, "urlopen", fail_urlopen)
    assistant = NicoAssistant(output_dir=str(tmp_path))

    with pytest.raises(ai_module.NicoModelError, match="Cannot reach Ollama"):
        assistant.chat("Hello")


def test_ollama_stream_emits_incremental_text_and_fast_options(monkeypatch, tmp_path):
    chunks = [
        {"message": {"content": "Quick "}, "done": False},
        {"message": {"content": "reply."}, "done": False},
        {"message": {"content": ""}, "done": True},
    ]
    response = BytesIO(
        b"".join(json.dumps(chunk).encode() + b"\n" for chunk in chunks)
    )
    captured = {}

    def fake_urlopen(request, timeout):
        captured["body"] = json.loads(request.data)
        captured["timeout"] = timeout
        return response

    monkeypatch.setattr(ai_module, "urlopen", fake_urlopen)
    assistant = NicoAssistant(output_dir=str(tmp_path))
    deltas = []
    result = assistant._ollama_chat([], [], on_delta=deltas.append)

    assert deltas == ["Quick ", "reply."]
    assert result["message"]["content"] == "Quick reply."
    assert captured["body"]["stream"] is True
    assert captured["body"]["keep_alive"] == "30m"
    assert captured["body"]["options"]["num_ctx"] == 4096
    assert captured["body"]["options"]["num_predict"] == 256
    assert captured["timeout"] == 120


def test_nico_chat_uses_tools_for_live_data(monkeypatch, tmp_path):
    responses = iter(
        [
            {
                "message": {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "get_orion_status",
                                "arguments": {},
                            }
                        }
                    ],
                }
            },
            {"message": {"content": "There are no devices connected."}},
        ]
    )
    requests = []
    assistant = NicoAssistant(output_dir=str(tmp_path))

    def fake_ollama_chat(messages, tools, on_delta=None):
        requests.append((messages.copy(), tools))
        return next(responses)

    monkeypatch.setattr(assistant, "_ollama_chat", fake_ollama_chat)
    result = assistant.chat(
        "Are my devices online?",
        devices=[{"id": "a1", "name": "phone", "status": "online"}],
        tasks=[{"task": "check inbox", "status": "queued"}],
    )

    assert result["tools_used"] == ["get_orion_status"]
    assert result["message"] == "There are no devices connected."
    assert requests[0][1][0]["function"]["name"] == "web_search"
    tool_message = requests[1][0][-1]
    assert tool_message["role"] == "tool"
    assert json.loads(tool_message["content"])["devices"][0]["status"] == "online"


def test_live_web_search_extracts_title_url_and_snippet(monkeypatch):
    html = """
    <a class="result__a" href="https://example.com/news">Current report</a>
    <a class="result__snippet">Latest verified update.</a>
    """

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return html.encode()

    monkeypatch.setattr(ai_module, "urlopen", lambda *_args, **_kwargs: FakeResponse())
    result = NicoAssistant._search_web("current report")

    assert result["query"] == "current report"
    assert result["results"] == [
        {
            "title": "Current report",
            "url": "https://example.com/news",
            "snippet": "Latest verified update.",
        }
    ]


def test_live_weather_includes_human_readable_conditions(monkeypatch):
    results = iter(
        [
            {"results": [{"name": "London", "admin1": "England", "country": "United Kingdom", "latitude": 51.5, "longitude": -0.1}]},
            {
                "timezone": "Europe/London",
                "current": {
                    "time": "2026-10-07T17:45",
                    "temperature_2m": 12,
                    "apparent_temperature": 9,
                    "relative_humidity_2m": 82,
                    "precipitation": 0,
                    "wind_speed_10m": 18,
                    "weather_code": 3,
                    "is_day": 1,
                },
            },
        ]
    )
    monkeypatch.setattr(NicoAssistant, "_fetch_json", lambda _url: next(results))

    weather = NicoAssistant._get_weather("London")

    assert weather["weather_description"] == "Overcast"
    assert weather["source"] == "Open-Meteo"


def test_conversation_memory_persists_and_recalls_relevant_history(tmp_path):
    database_path = tmp_path / "conversation.sqlite3"
    memory = ConversationMemory(database_path)
    memory.add_message("browser-a", "user", "My favorite project is Orion.")
    memory.add_message("browser-a", "assistant", "I'll remember that project.")
    memory.add_message("browser-a", "user", "The weather today is sunny.")

    reopened = ConversationMemory(database_path)
    context = reopened.context("browser-a", "Tell me about my Orion project")

    assert reopened.count("browser-a") == 3
    assert len(reopened.recent("browser-a")) == 3
    assert any("favorite project is Orion" in turn["content"] for turn in context)


def test_conversation_memory_caps_messages_and_clears_fts_index(tmp_path, monkeypatch):
    import orion_app.memory as memory_module

    monkeypatch.setattr(memory_module, "MAX_MESSAGES_PER_CONVERSATION", 3)
    memory = ConversationMemory(tmp_path / "conversation.sqlite3")
    for index in range(4):
        memory.add_message("browser-a", "user", f"unique detail {index}")

    assert memory.count("browser-a") == 3
    assert not any("detail 0" in turn["content"] for turn in memory.context("browser-a", "detail 0"))
    memory.clear("browser-a")
    assert memory.count("browser-a") == 0


def test_device_manager_registers_and_queues_tasks():
    manager = DeviceManager()
    device = manager.register_device("phone-alpha", "phone")
    task = manager.enqueue_task(device["id"], "Check notifications")

    assert device["name"] == "phone-alpha"
    assert task["device_id"] == device["id"]
    assert task["status"] == "queued"
    assert task["task"] == "Check notifications"


def test_archer_offline_generation_uses_local_diffusion_pipeline(monkeypatch, tmp_path):
    calls = {}

    class FakePipeline:
        def to(self, device):
            calls["device"] = device
            return self

        def __call__(self, prompt, **options):
            calls["prompt"] = prompt
            calls["options"] = options
            return SimpleNamespace(images=[Image.new("RGB", (256, 256), "green")])

    class FakePipelineFactory:
        @staticmethod
        def from_pretrained(model, **options):
            calls["model"] = model
            calls["load_options"] = options
            return FakePipeline()

    fake_torch = ModuleType("torch")
    fake_torch.cuda = SimpleNamespace(is_available=lambda: False)
    fake_torch.float16 = "float16"
    fake_torch.float32 = "float32"
    fake_torch.set_num_threads = lambda threads: calls.setdefault("threads", threads)
    fake_diffusers = ModuleType("diffusers")
    fake_diffusers.AutoPipelineForText2Image = FakePipelineFactory
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setitem(sys.modules, "diffusers", fake_diffusers)

    assistant = NicoAssistant(output_dir=str(tmp_path))
    result = assistant.generate_archer_image("a luminous forest", width=256, height=256, mode="offline")

    assert result["mode"] == "offline"
    assert result["model"] == "stabilityai/sd-turbo"
    assert result["url"].startswith("/api/archer/images/archer_")
    assert (tmp_path / result["url"].rsplit("/", 1)[-1]).is_file()
    assert calls["device"] == "cpu"
    assert calls["load_options"]["local_files_only"] is True
    assert calls["load_options"]["variant"] == "fp16"
    assert calls["options"]["num_inference_steps"] == 1
    assert calls["threads"] == 4


def test_archer_auto_uses_offline_model_when_online_provider_fails(monkeypatch, tmp_path):
    assistant = NicoAssistant(output_dir=str(tmp_path))
    monkeypatch.setattr(
        assistant,
        "_generate_online_archer_image",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ai_module.LiveDataError("offline")),
    )
    monkeypatch.setattr(
        assistant,
        "_generate_offline_archer_image",
        lambda prompt, width, height: {
            "prompt": prompt,
            "width": width,
            "height": height,
            "mode": "offline",
        },
    )

    result = assistant.generate_archer_image("moonlit city", mode="auto")

    assert result == {
        "prompt": "moonlit city",
        "width": 512,
        "height": 512,
        "mode": "offline",
    }


def test_archer_online_generation_saves_a_valid_png_and_escapes_prompt(monkeypatch, tmp_path):
    image_data = BytesIO()
    Image.new("RGB", (256, 256), "green").save(image_data, format="PNG")
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return image_data.getvalue()

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(ai_module, "urlopen", fake_urlopen)
    assistant = NicoAssistant(output_dir=str(tmp_path))

    result = assistant.generate_archer_image(
        "bow & arrow / moon", width=256, height=256, mode="online"
    )

    assert "%26" in captured["url"]
    assert "%2F" in captured["url"]
    assert captured["timeout"] == 30
    assert result["mode"] == "online"
    with Image.open(tmp_path / result["url"].rsplit("/", 1)[-1]) as generated:
        assert generated.format == "PNG"


@pytest.mark.parametrize(
    ("prompt", "width", "mode", "message"),
    [
        (" ", 512, "offline", "prompts must be between"),
        ("a landscape", 128, "offline", "dimensions must be"),
        ("a landscape", 512, "unknown", "Choose online, offline, or auto"),
    ],
)
def test_archer_rejects_invalid_generation_requests(prompt, width, mode, message, tmp_path):
    assistant = NicoAssistant(output_dir=str(tmp_path))

    with pytest.raises(ai_module.ArcherGenerationError, match=message):
        assistant.generate_archer_image(prompt, width=width, height=512, mode=mode)


def test_archer_api_routes_generate_and_serve_images(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient

    import orion_app.main as main_module

    filename = "archer_test.png"
    Image.new("RGB", (16, 16), "green").save(tmp_path / filename)
    monkeypatch.setattr(main_module.assistant, "output_dir", tmp_path)
    monkeypatch.setattr(
        main_module.assistant,
        "generate_archer_image",
        lambda prompt, width, height, mode: {
            "prompt": prompt,
            "width": width,
            "height": height,
            "mode": mode,
            "url": f"/api/archer/images/{filename}",
        },
    )
    client = TestClient(main_module.app)

    response = client.post(
        "/api/archer/generate",
        json={"prompt": "green citadel", "mode": "offline", "width": 512, "height": 512},
    )
    image_response = client.get(f"/api/archer/images/{filename}")
    invalid_response = client.post(
        "/api/archer/generate",
        json={"prompt": "green citadel", "mode": "offline", "width": 255, "height": 512},
    )

    assert response.status_code == 200
    assert response.json()["mode"] == "offline"
    assert image_response.status_code == 200
    assert image_response.headers["content-type"] == "image/png"
    assert invalid_response.status_code == 422


def test_instagram_oauth_requests_supported_permissions_and_exchanges_tokens(monkeypatch):
    from urllib.parse import parse_qs, urlparse

    import orion_app.instagram as instagram_module

    monkeypatch.setenv("ORION_INSTAGRAM_APP_ID", "app-id")
    monkeypatch.setenv("ORION_INSTAGRAM_APP_SECRET", "app-secret")
    integration = instagram_module.InstagramIntegration()
    authorize_url = integration.authorization_url()
    authorize = parse_qs(urlparse(authorize_url).query)
    assert authorize["client_id"] == ["app-id"]
    assert authorize["redirect_uri"] == ["http://localhost:8000/api/instagram/callback"]
    assert set(authorize["scope"][0].split(",")) == set(integration.SCOPES)

    class FakeResponse:
        def __init__(self, payload):
            self.payload = json.dumps(payload).encode()

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return self.payload

    responses = iter(
        [
            FakeResponse(
                {
                    "access_token": "short-token",
                    "user_id": 123,
                    "permissions": ["instagram_business_basic"],
                }
            ),
            FakeResponse({"access_token": "long-token", "expires_in": 3600}),
        ]
    )
    requests = []

    def fake_urlopen(request, timeout):
        requests.append(request)
        assert timeout == 20
        return next(responses)

    monkeypatch.setattr(instagram_module, "urlopen", fake_urlopen)
    integration.complete_authorization("auth-code", authorize["state"][0])

    assert integration.status()["connected"] is True
    assert integration.status()["user_id"] == "123"
    assert integration.status()["scopes"] == ["instagram_business_basic"]
    assert b"auth-code" in requests[0].data
    assert b"short-token" in requests[1].full_url.encode()
    with pytest.raises(instagram_module.InstagramError, match="missing, expired, or already used"):
        integration.complete_authorization("auth-code", authorize["state"][0])


def test_instagram_api_calls_use_access_token_and_bound_message_actions(monkeypatch):
    import orion_app.instagram as instagram_module

    integration = instagram_module.InstagramIntegration()
    integration._token = instagram_module.InstagramToken(
        "private-access-token", "account-123", 9999999999, tuple(integration.SCOPES)
    )
    requests = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return b'{"data":[]}'

    def fake_urlopen(request, timeout):
        requests.append(request)
        return FakeResponse()

    monkeypatch.setattr(instagram_module, "urlopen", fake_urlopen)
    integration.conversations()
    assert "graph.instagram.com/v25.0/me/conversations" in requests[0].full_url
    assert "access_token=private-access-token" in requests[0].full_url

    with pytest.raises(instagram_module.InstagramError, match="1 to 1000 characters"):
        integration.send_message("recipient-1", " ")
    with pytest.raises(instagram_module.InstagramError, match="invalid identifier"):
        integration.conversation_messages("../other")
    with pytest.raises(instagram_module.InstagramError, match="publicly reachable HTTPS"):
        integration.publish_image("http://example.com/image.jpg")


def test_instagram_publish_waits_for_processing_before_publishing(monkeypatch):
    from urllib.parse import parse_qs

    import orion_app.instagram as instagram_module

    integration = instagram_module.InstagramIntegration()
    integration._token = instagram_module.InstagramToken(
        "private-access-token", "account-123", 9999999999, tuple(integration.SCOPES)
    )
    responses = iter(
        [
            {"id": "container-1"},
            {"status_code": "FINISHED"},
            {"id": "published-media-1"},
        ]
    )
    requests = []

    class FakeResponse:
        def __init__(self, payload):
            self.payload = json.dumps(payload).encode()

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return self.payload

    def fake_urlopen(request, timeout):
        requests.append(request)
        return FakeResponse(next(responses))

    monkeypatch.setattr(instagram_module, "urlopen", fake_urlopen)
    result = integration.publish_image("https://cdn.example.com/post.jpg", "A caption")

    assert result["id"] == "published-media-1"
    assert "/account-123/media" in requests[0].full_url
    assert parse_qs(requests[0].data.decode())["image_url"] == ["https://cdn.example.com/post.jpg"]
    assert "/container-1?fields=status_code" in requests[1].full_url
    assert "/account-123/media_publish" in requests[2].full_url


def test_instagram_routes_report_setup_and_reject_unconfigured_connection(monkeypatch):
    from fastapi.testclient import TestClient

    import orion_app.main as main_module
    from orion_app.instagram import InstagramIntegration

    monkeypatch.delenv("ORION_INSTAGRAM_APP_ID", raising=False)
    monkeypatch.delenv("ORION_INSTAGRAM_APP_SECRET", raising=False)
    monkeypatch.setattr(main_module, "instagram", InstagramIntegration())
    client = TestClient(main_module.app)

    status = client.get("/api/instagram/status")
    connect = client.get("/api/instagram/connect")

    assert status.status_code == 200
    assert status.json()["configured"] is False
    assert status.json()["connected"] is False
    assert connect.status_code == 503
    assert "ORION_INSTAGRAM_APP_ID" in connect.json()["detail"]


def test_telegram_archive_persists_chats_messages_and_downloaded_media(tmp_path, monkeypatch):
    from orion_app.telegram import TelegramIntegration

    archive_path = tmp_path / "telegram_archive.sqlite3"
    session_path = tmp_path / "telegram.session"
    media_root = tmp_path / "telegram_media"
    monkeypatch.setenv("ORION_TELEGRAM_MEDIA_PATH", str(media_root))
    integration = TelegramIntegration(session_path=session_path, archive_path=archive_path)
    media_file = media_root / "-123" / "456.jpg"
    media_file.parent.mkdir(parents=True)
    media_file.write_bytes(b"telegram image")
    integration._save_dialog(
        "-123",
        {
            "name": "Orion group",
            "username": None,
            "unread_count": 0,
            "is_group": True,
            "is_channel": False,
            "last_message": "Saved for later",
            "date": "2026-01-01T12:00:00+00:00",
        },
    )
    integration._save_message(
        "-123",
        {
            "id": "456",
            "text": "Saved for later",
            "date": "2026-01-01T12:00:00+00:00",
            "outgoing": False,
            "sender": "friend",
            "media": True,
            "media_path": "-123/456.jpg",
        },
    )

    reopened = TelegramIntegration(session_path=session_path, archive_path=archive_path)
    assert reopened.archived_dialogs() == [
        {
            "id": "-123",
            "name": "Orion group",
            "username": None,
            "unread_count": 0,
            "is_group": 1,
            "is_channel": 0,
            "last_message": "Saved for later",
            "date": "2026-01-01T12:00:00+00:00",
        }
    ]
    archived_messages = reopened.archived_messages("-123")
    assert archived_messages[0]["text"] == "Saved for later"
    assert archived_messages[0]["media_url"] == "/api/telegram/media/-123/456"
    assert reopened.media_file("-123", "456") == media_file.resolve()


def test_telegram_status_reports_missing_credentials_without_connecting(monkeypatch, tmp_path):
    from orion_app.telegram import TelegramIntegration

    monkeypatch.delenv("ORION_TELEGRAM_API_ID", raising=False)
    monkeypatch.delenv("ORION_TELEGRAM_API_HASH", raising=False)
    integration = TelegramIntegration(
        session_path=tmp_path / "telegram.session",
        archive_path=tmp_path / "telegram_archive.sqlite3",
    )

    status = integration.status()

    assert status["configured"] is False
    assert status["connected"] is False
    assert status["session_exists"] is False
    assert status["import"]["status"] == "idle"


def test_telegram_status_does_not_reconnect_a_saved_session(monkeypatch, tmp_path):
    from orion_app.telegram import TelegramIntegration

    monkeypatch.setenv("ORION_TELEGRAM_API_ID", "12345")
    monkeypatch.setenv("ORION_TELEGRAM_API_HASH", "test-hash")
    session_path = tmp_path / "telegram.session"
    session_path.touch()
    integration = TelegramIntegration(
        session_path=session_path,
        archive_path=tmp_path / "telegram_archive.sqlite3",
    )
    integration._submit = lambda *_args, **_kwargs: pytest.fail("status should not make a network request")

    status = integration.status()

    assert status["configured"] is True
    assert status["connected"] is False
    assert status["session_exists"] is True


def test_telegram_timeout_explains_network_handshake_failure(monkeypatch, tmp_path):
    import asyncio
    from concurrent.futures import TimeoutError

    from orion_app.telegram import TelegramIntegration, TelegramIntegrationError

    integration = TelegramIntegration(
        session_path=tmp_path / "telegram.session",
        archive_path=tmp_path / "telegram_archive.sqlite3",
    )

    class TimedOutFuture:
        def result(self, timeout):
            raise TimeoutError()

        def cancel(self):
            return True

    monkeypatch.setattr(
        asyncio,
        "run_coroutine_threadsafe",
        lambda *_args, **_kwargs: TimedOutFuture(),
    )

    with pytest.raises(TelegramIntegrationError, match="MTProto connection timed out") as error:
        integration._submit(object())

    assert "trusted VPN or another network" in str(error.value)


@pytest.mark.parametrize(
    ("proxy_type", "expected_type"),
    [
        ("socks5", "socks5"),
        ("socks4", "socks4"),
        ("http", "http"),
    ],
)
def test_telegram_proxy_parses_socks_and_http_settings(proxy_type, expected_type):
    from orion_app.telegram import TelegramProxySettings

    proxy = TelegramProxySettings.from_environment(
        {
            "ORION_TELEGRAM_PROXY_TYPE": proxy_type,
            "ORION_TELEGRAM_PROXY_HOST": "proxy.example.test",
            "ORION_TELEGRAM_PROXY_PORT": "1080",
            "ORION_TELEGRAM_PROXY_USERNAME": "orion-user",
            "ORION_TELEGRAM_PROXY_PASSWORD": "local-secret",
        }
    )

    assert proxy is not None
    assert proxy.proxy_type == expected_type
    assert proxy.telethon_options() == {
        "proxy": {
            "proxy_type": expected_type,
            "addr": "proxy.example.test",
            "port": 1080,
            "rdns": True,
            "username": "orion-user",
            "password": "local-secret",
        }
    }


def test_telegram_proxy_parses_mtproto_settings():
    from telethon.network.connection.tcpmtproxy import (
        ConnectionTcpMTProxyRandomizedIntermediate,
    )

    from orion_app.telegram import TelegramProxySettings

    proxy = TelegramProxySettings.from_environment(
        {
            "ORION_TELEGRAM_PROXY_TYPE": "mtproxy",
            "ORION_TELEGRAM_PROXY_HOST": "proxy.example.test",
            "ORION_TELEGRAM_PROXY_PORT": "443",
            "ORION_TELEGRAM_PROXY_SECRET": "0123456789abcdef0123456789abcdef",
        }
    )

    assert proxy is not None
    assert proxy.telethon_options() == {
        "connection": ConnectionTcpMTProxyRandomizedIntermediate,
        "proxy": ("proxy.example.test", 443, "0123456789abcdef0123456789abcdef"),
    }


@pytest.mark.parametrize(
    "secret",
    [
        "0123456789abcdef0123456789abcdef",
        "ee0123456789abcdef0123456789abcdef",
        "eeNEgYdJvXrFGRMCIMJdCQ",
    ],
)
def test_telegram_proxy_parses_shared_mtproto_link_secret_formats(secret):
    from urllib.parse import quote

    from orion_app.telegram import TelegramProxySettings

    proxy = TelegramProxySettings.from_telegram_link(
        f"https://t.me/proxy?server=proxy.example.test&port=443&secret={quote(secret)}"
    )

    assert proxy.proxy_type == "mtproxy"
    assert proxy.host == "proxy.example.test"
    assert proxy.port == 443
    assert proxy.secret == secret


def test_telegram_proxy_rejects_non_telegram_proxy_link():
    from orion_app.telegram import TelegramIntegrationError, TelegramProxySettings

    with pytest.raises(TelegramIntegrationError, match="Telegram MTProto proxy link"):
        TelegramProxySettings.from_telegram_link(
            "https://example.test/proxy?server=proxy.example.test&port=443&secret=secret"
        )


def test_telegram_proxy_configuration_persists_selected_link_without_exposing_secret(monkeypatch, tmp_path):
    import asyncio
    import orion_app.telegram as telegram_module
    from orion_app.telegram import TelegramIntegration

    monkeypatch.setenv("ORION_TELEGRAM_API_ID", "12345")
    monkeypatch.setenv("ORION_TELEGRAM_API_HASH", "test-hash")
    integration = TelegramIntegration(
        session_path=tmp_path / "telegram.session",
        archive_path=tmp_path / "telegram_archive.sqlite3",
    )
    persisted = {}
    monkeypatch.setattr(
        integration,
        "_persist_proxy_settings",
        lambda values: persisted.update(values),
    )

    async def no_op():
        return None

    monkeypatch.setattr(integration, "_disconnect_client", no_op)
    monkeypatch.setattr(integration, "_test_proxy", no_op)
    monkeypatch.setattr(
        integration,
        "_submit",
        lambda coroutine, **_kwargs: asyncio.run(coroutine),
    )
    secret = "ee0123456789abcdef0123456789abcdef"

    result = integration.configure_mtproxy(
        f"https://t.me/proxy?server=proxy.example.test&port=443&secret={secret}"
    )

    assert result == {
        "configured": True,
        "proxy_type": "mtproxy",
        "connection_tested": True,
    }
    assert persisted["ORION_TELEGRAM_PROXY_SECRET"] == secret
    assert integration.status()["proxy_type"] == "mtproxy"
    assert secret not in json.dumps(integration.status())


def test_telegram_proxy_is_not_saved_when_connection_test_fails(monkeypatch, tmp_path):
    import asyncio

    from orion_app.telegram import TelegramIntegration, TelegramIntegrationError

    integration = TelegramIntegration(
        session_path=tmp_path / "telegram.session",
        archive_path=tmp_path / "telegram_archive.sqlite3",
    )
    previous_proxy = integration.proxy
    persisted = []
    monkeypatch.setattr(integration, "_persist_proxy_settings", lambda values: persisted.append(values))

    async def no_op():
        return None

    monkeypatch.setattr(integration, "_disconnect_client", no_op)
    monkeypatch.setattr(integration, "_test_proxy", no_op)
    calls = 0

    def submit(coroutine, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            coroutine.close()
            raise TelegramIntegrationError("proxy unavailable")
        return asyncio.run(coroutine)

    monkeypatch.setattr(integration, "_submit", submit)
    result = integration.configure_mtproxy(
        "https://t.me/proxy?server=proxy.example.test&port=443&secret=secret"
    )

    assert result["configured"] is False
    assert result["connection_tested"] is False
    assert result["detail"] == "proxy unavailable"
    assert integration.proxy is previous_proxy
    assert not persisted


def test_telegram_proxy_pool_saves_valid_unique_links_without_exposing_secrets(tmp_path):
    from orion_app.telegram import TelegramIntegration

    integration = TelegramIntegration(
        session_path=tmp_path / "telegram.session",
        archive_path=tmp_path / "telegram_archive.sqlite3",
    )
    secret = "ee0123456789abcdef0123456789abcdef"
    valid_link = f"https://t.me/proxy?server=proxy.example.test&port=443&secret={secret}"

    result = integration.save_mtproxy_links(
        [
            valid_link,
            valid_link,
            "https://example.test/not-a-proxy",
        ]
    )

    assert result["saved_count"] == 1
    assert result["added_count"] == 1
    assert result["invalid_count"] == 1
    assert result["proxies"] == [
        {
            "id": 1,
            "host": "proxy.example.test",
            "port": 443,
            "active": False,
            "tested": False,
            "failed": False,
        }
    ]
    assert secret not in json.dumps(result)


def test_telegram_proxy_pool_can_activate_saved_proxy_and_clear_pool(monkeypatch, tmp_path):
    from orion_app.telegram import TelegramIntegration

    integration = TelegramIntegration(
        session_path=tmp_path / "telegram.session",
        archive_path=tmp_path / "telegram_archive.sqlite3",
    )
    secret = "ee0123456789abcdef0123456789abcdef"
    integration.save_mtproxy_links(
        [f"https://t.me/proxy?server=proxy.example.test&port=443&secret={secret}"]
    )
    requested = []
    monkeypatch.setattr(
        integration,
        "configure_mtproxy",
        lambda link: requested.append(link)
        or {"configured": True, "connection_tested": True, "proxy_type": "mtproxy"},
    )

    result = integration.activate_saved_mtproxy(1)

    assert requested and secret in requested[0]
    assert result["connection_tested"] is True
    assert result["proxies"][0]["tested"] is True
    monkeypatch.setattr(integration, "_persist_proxy_settings", lambda _settings: None)
    integration.clear_proxy()
    assert integration.saved_mtproxies() == []


@pytest.mark.parametrize(
    ("settings", "message"),
    [
        (
            {"ORION_TELEGRAM_PROXY_TYPE": "socks5"},
            "hostname or IP address",
        ),
        (
            {
                "ORION_TELEGRAM_PROXY_TYPE": "socks5",
                "ORION_TELEGRAM_PROXY_HOST": "proxy.example.test",
                "ORION_TELEGRAM_PROXY_PORT": "70000",
            },
            "1 to 65535",
        ),
        (
            {
                "ORION_TELEGRAM_PROXY_TYPE": "mtproxy",
                "ORION_TELEGRAM_PROXY_HOST": "proxy.example.test",
                "ORION_TELEGRAM_PROXY_PORT": "443",
            },
            "MTProto proxy",
        ),
    ],
)
def test_telegram_proxy_rejects_incomplete_or_invalid_settings(settings, message):
    from orion_app.telegram import TelegramIntegrationError, TelegramProxySettings

    with pytest.raises(TelegramIntegrationError, match=message):
        TelegramProxySettings.from_environment(settings)


def test_telegram_full_import_archives_history_and_downloadable_media(tmp_path):
    from datetime import datetime, timezone
    from pathlib import Path

    from orion_app.telegram import TelegramIntegration

    entity = SimpleNamespace(username="orion_group")
    dialog = SimpleNamespace(
        id=-123,
        name="Orion group",
        entity=entity,
        message=None,
        unread_count=0,
        is_group=True,
        is_channel=False,
    )
    messages = [
        SimpleNamespace(
            id=1,
            message="First archived message",
            date=datetime(2026, 1, 1, tzinfo=timezone.utc),
            out=False,
            sender_id=456,
            post_author=None,
            media=None,
            file=None,
        ),
        SimpleNamespace(
            id=2,
            message="An image",
            date=datetime(2026, 1, 2, tzinfo=timezone.utc),
            out=False,
            sender_id=456,
            post_author=None,
            media=object(),
            file=SimpleNamespace(ext=".jpg"),
        ),
    ]

    class FakeTelegramClient:
        async def is_user_authorized(self):
            return True

        async def iter_dialogs(self):
            yield dialog

        async def iter_messages(self, _entity, reverse=False):
            assert reverse is True
            for item in messages:
                yield item

        async def download_media(self, _message, file):
            media_path = Path(file)
            media_path.write_bytes(b"telegram media")
            return str(media_path)

    integration = TelegramIntegration(
        session_path=tmp_path / "telegram.session",
        archive_path=tmp_path / "telegram_archive.sqlite3",
        media_path=tmp_path / "telegram_media",
    )
    integration._client = FakeTelegramClient()

    async def ensure_fake_client():
        return None

    integration._ensure_client = ensure_fake_client
    integration._submit(integration._import_all())

    status = integration.import_status()
    archived = integration.archived_messages("-123")
    assert status["status"] == "completed"
    assert status["chats_total"] == status["chats_done"] == 1
    assert status["messages_archived"] == 2
    assert status["media_downloaded"] == 1
    assert [message["text"] for message in archived] == ["First archived message", "An image"]
    assert archived[1]["media_url"] == "/api/telegram/media/-123/2"
    assert integration.media_file("-123", "2").read_bytes() == b"telegram media"
