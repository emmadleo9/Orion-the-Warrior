from __future__ import annotations
from dotenv import load_dotenv
load_dotenv()
import json
import os
import queue
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Callable, Literal, TypeVar

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, StreamingResponse

from .config import load_config

load_config()

from .ai import ArcherGenerationError, LiveDataError, NicoAssistant, NicoModelError, LeoAssistant, ZaraAssistant
from .devices import DeviceManager
from .instagram import InstagramError, InstagramIntegration, InstagramManager
from .launcher import LauncherMonitor
from .memory import MAX_MESSAGES_PER_CONVERSATION, ConversationMemory
from .task_monitor import TaskMonitor
from .telemetry import get_system_telemetry
from .telegram import telegram_client, telegram_proxy_manager

BASE_DIR = Path(__file__).resolve().parent
assistant = NicoAssistant()
leo = LeoAssistant()
zara = leo  # Backwards compatibility alias
device_manager = DeviceManager()
task_monitor = TaskMonitor()
memory = ConversationMemory(
    os.getenv("ORION_MEMORY_PATH", str(BASE_DIR / "data" / "conversations.sqlite3"))
)
instagram = InstagramIntegration()
launcher_monitor = LauncherMonitor(task_monitor)
Result = TypeVar("Result")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Follow the Orion launcher log for the lifetime of the server."""
    launcher_monitor.start()
    # Start Telegram proxy manager background scheduler
    try:
        telegram_proxy_manager.start_scheduler()
        telegram_client.start()
    except Exception:
        pass
    try:
        yield
    finally:
        launcher_monitor.stop()
        try:
            telegram_proxy_manager.stop_scheduler()
        except Exception:
            pass


app = FastAPI(title="Orion the Warrior", version="0.1.0", lifespan=lifespan)

# Allow the phone (and any origin) to reach the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def run_tracked(title: str, category: str, operation: Callable[[], Result]) -> Result:
    run_id = task_monitor.start(title, category)
    try:
        task_monitor.log(run_id, "Operation dispatched.")
        result = operation()
    except Exception:
        task_monitor.finish(run_id, "failed", "Operation failed.")
        raise
    task_monitor.finish(run_id, "completed", "Operation completed successfully.")
    return result


class ChatRequest(BaseModel):
    conversation_id: str = Field(
        min_length=1,
        max_length=64,
        pattern="^[A-Za-z0-9_-]+$",
    )
    message: str = Field(min_length=1, max_length=4000)

    @field_validator("message")
    @classmethod
    def message_must_not_be_blank(cls, message: str) -> str:
        message = message.strip()
        if not message:
            raise ValueError("message must not be blank")
        return message


class ArcherImageRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=1000)
    mode: Literal["online", "offline", "auto"] = "auto"
    width: int = Field(default=512, ge=256, le=1024, multiple_of=8)
    height: int = Field(default=512, ge=256, le=1024, multiple_of=8)

    @field_validator("prompt")
    @classmethod
    def prompt_must_not_be_blank(cls, prompt: str) -> str:
        prompt = prompt.strip()
        if not prompt:
            raise ValueError("prompt must not be blank")
        return prompt


class InstagramReplyRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)

    @field_validator("message")
    @classmethod
    def reply_must_not_be_blank(cls, message: str) -> str:
        message = message.strip()
        if not message:
            raise ValueError("message must not be blank")
        return message


class InstagramSendRequest(BaseModel):
    recipient_id: str = Field(min_length=1, max_length=200)
    text: str = Field(default="", max_length=1000)
    message: str = Field(default="", max_length=1000)

    @field_validator("text", "message", mode="after")
    @classmethod
    def strip_text(cls, v: str) -> str:
        return v.strip() if v else ""


InstagramMessageRequest = InstagramSendRequest


class InstagramPublishRequest(BaseModel):
    image_url: str = Field(min_length=1, max_length=2048)
    caption: str = Field(default="", max_length=2200)


@app.get("/")
def read_index() -> FileResponse:
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.get("/instagram", response_class=HTMLResponse)
def read_instagram_inbox() -> HTMLResponse:
    """Built-in Instagram inbox for Orion, styled with dark theme and Tailwind."""
    inbox_html = BASE_DIR / "static" / "instagram.html"
    if not inbox_html.is_file():
        raise HTTPException(status_code=404, detail="Instagram inbox view not found")
    return HTMLResponse(content=inbox_html.read_text(encoding="utf-8"))


@app.get("/telegram", response_class=HTMLResponse)
def read_telegram() -> HTMLResponse:
    """Full-page Telegram client.

    Telegram is part of the Social Hub. This route serves the same Telegram
    module full-screen for direct/deep links; the Social Hub embeds it in its
    Telegram tab, and both use the identical client and API.
    """
    tg_html = BASE_DIR / "static" / "telegram.html"
    if not tg_html.is_file():
        raise HTTPException(status_code=404, detail="Telegram module not found")
    return HTMLResponse(content=tg_html.read_text(encoding="utf-8"))


@app.get("/manifest.json")
def read_manifest() -> FileResponse:
    return FileResponse(BASE_DIR / "static" / "manifest.json", media_type="application/manifest+json")


@app.get("/sw.js")
def read_sw() -> FileResponse:
    """Serve the service worker from root scope so it can control all pages."""
    return FileResponse(
        BASE_DIR / "static" / "sw.js",
        media_type="application/javascript",
        headers={"Service-Worker-Allowed": "/"},
    )


@app.get("/static/{filename}")
def read_static(filename: str) -> FileResponse:
    file_path = BASE_DIR / "static" / filename
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "app": "Orion the Warrior", "assistant": assistant.name}


@app.get("/api/diagnostics")
def diagnostics() -> dict:
    """System-wide diagnostic snapshot used by the dashboard."""
    return get_system_telemetry()


@app.get("/api/launcher/status")
def launcher_status() -> dict:
    """Report whether the Orion launcher log is present and being followed."""
    return launcher_monitor.status()


@app.get("/api/task-runs")
def task_runs(limit: int = 50) -> list[dict]:
    try:
        return task_monitor.list_runs(limit)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.get("/api/task-runs/events")
def task_run_events() -> StreamingResponse:
    def stream_events():
        with task_monitor.subscribe() as subscriber:
            yield f"event: snapshot\ndata: {json.dumps(task_monitor.list_runs())}\n\n"
            while True:
                try:
                    run = subscriber.get(timeout=15)
                except queue.Empty:
                    yield ": keep-alive\n\n"
                    continue
                yield f"data: {json.dumps(run)}\n\n"

    return StreamingResponse(
        stream_events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/instagram/status")
def instagram_status() -> dict:
    return instagram.status()


@app.get("/api/instagram/connect")
def instagram_connect() -> RedirectResponse:
    try:
        redirect = run_tracked(
            "Instagram authorization",
            "social",
            instagram.authorization_url,
        )
        return RedirectResponse(redirect, status_code=302)
    except InstagramError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.get("/api/instagram/callback")
def instagram_callback(
    code: str = "",
    state: str = "",
    error: str = "",
    error_description: str = "",
) -> RedirectResponse:
    from urllib.parse import urlencode

    if error:
        message = error_description or error
        return RedirectResponse(
            f"/?{urlencode({'view': 'social', 'instagram': 'error', 'detail': message})}",
            status_code=303,
        )
    try:
        run_tracked(
            "Complete Instagram authorization",
            "social",
            lambda: instagram.complete_authorization(code, state),
        )
    except InstagramError as integration_error:
        return RedirectResponse(
            f"/?{urlencode({'view': 'social', 'instagram': 'error', 'detail': str(integration_error)})}",
            status_code=303,
        )
    return RedirectResponse("/?view=social&instagram=connected", status_code=303)


@app.delete("/api/instagram/connection")
def instagram_disconnect() -> dict:
    run_tracked("Disconnect Instagram", "social", instagram.disconnect)
    return {"disconnected": True}


@app.post("/api/instagram/refresh")
def instagram_refresh() -> dict:
    try:
        return run_tracked("Refresh Instagram access", "social", instagram.refresh)
    except InstagramError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.get("/api/instagram/profile")
def instagram_profile() -> dict:
    try:
        return run_tracked("Load Instagram profile", "social", instagram.profile)
    except InstagramError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.get("/api/instagram/media")
def instagram_media(limit: int = 20) -> dict:
    try:
        return run_tracked(
            "Load Instagram media",
            "social",
            lambda: instagram.media(limit),
        )
    except InstagramError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.get("/api/instagram/insights")
def instagram_insights(period: str = "day") -> dict:
    try:
        return run_tracked(
            "Load Instagram insights",
            "social",
            lambda: instagram.insights(period),
        )
    except InstagramError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.get("/api/instagram/media/{media_id}/comments")
def instagram_comments(media_id: str) -> dict:
    try:
        return run_tracked(
            "Load Instagram comments",
            "social",
            lambda: instagram.comments(media_id),
        )
    except InstagramError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.post("/api/instagram/comments/{comment_id}/replies")
def instagram_reply(comment_id: str, payload: InstagramReplyRequest) -> dict:
    try:
        return run_tracked(
            "Reply to Instagram comment",
            "social",
            lambda: instagram.reply_to_comment(comment_id, payload.message),
        )
    except InstagramError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.get("/api/instagram/inbox")
def instagram_inbox() -> dict:
    status = instagram.status()
    connected = bool(status.get("connected", False))
    conversations = []
    if connected:
        try:
            conversations = instagram.get_conversations()
        except Exception:
            conversations = []
    return {
        "connected": connected,
        "conversations": conversations,
    }


@app.get("/api/instagram/conversations")
def instagram_conversations() -> dict:
    try:
        return run_tracked(
            "Load Instagram inbox",
            "social",
            instagram.conversations,
        )
    except InstagramError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.get("/api/instagram/conversation/{conversation_id}/messages")
@app.get("/api/instagram/conversations/{conversation_id}/messages")
def instagram_conversation_messages(conversation_id: str) -> dict:
    if not conversation_id or len(conversation_id) > 200:
        raise HTTPException(status_code=400, detail="Invalid conversation_id")
    try:
        raw = run_tracked(
            "Load Instagram conversation",
            "social",
            lambda: instagram.conversation_messages(conversation_id),
        )
        messages = []
        if isinstance(raw, dict):
            if "messages" in raw and isinstance(raw["messages"], dict):
                messages = raw["messages"].get("data", [])
            elif "data" in raw and isinstance(raw["data"], list):
                messages = raw["data"]
            elif "messages" in raw and isinstance(raw["messages"], list):
                messages = raw["messages"]
        return {
            "conversation_id": conversation_id,
            "messages": messages,
            "raw": raw,
        }
    except InstagramError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.post("/api/instagram/send")
@app.post("/api/instagram/messages")
def instagram_send_message(payload: InstagramSendRequest) -> dict:
    content = payload.text or payload.message
    if not content:
        raise HTTPException(status_code=400, detail="text or message must not be blank")
    try:
        return run_tracked(
            "Send Instagram message",
            "social",
            lambda: instagram.send_message(payload.recipient_id, text=content),
        )
    except InstagramError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.post("/api/instagram/publish")
def instagram_publish(payload: InstagramPublishRequest) -> dict:
    try:
        return run_tracked(
            "Publish Instagram image",
            "social",
            lambda: instagram.publish_image(payload.image_url, payload.caption),
        )
    except InstagramError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.post("/api/assistant/respond")
def assistant_respond(payload: dict) -> dict:
    prompt = str(payload.get("prompt", ""))
    return run_tracked(
        "Generate Nico response",
        "ai",
        lambda: assistant.respond(prompt),
    )


@app.get("/api/assistant/status")
def assistant_status() -> dict:
    return assistant.model_status()


@app.post("/api/assistant/chat")
def assistant_chat(payload: ChatRequest) -> StreamingResponse:
    context = memory.context(payload.conversation_id, payload.message)
    memory.add_message(payload.conversation_id, "user", payload.message)
    run_id = task_monitor.start("Nico assistant response", "ai")
    task_monitor.log(run_id, "Preparing local model request.")
    events: queue.Queue[dict | None] = queue.Queue()

    def run_chat() -> None:
        streamed_chunks = 0

        def on_delta(text: str) -> None:
            nonlocal streamed_chunks
            streamed_chunks += 1
            if streamed_chunks == 1:
                task_monitor.log(run_id, "Local model response stream started.")
            elif streamed_chunks % 64 == 0:
                task_monitor.log(
                    run_id,
                    f"Response streaming; {streamed_chunks} content chunks received.",
                )
            events.put({"type": "delta", "content": text})

        try:
            result = assistant.chat(
                payload.message,
                context,
                device_manager.list_devices(),
                device_manager.list_tasks(),
                on_delta=on_delta,
                on_queue_task=lambda dev_id, tsk: device_manager.enqueue_task(dev_id, tsk),
            )
        except NicoModelError as error:
            task_monitor.finish(run_id, "failed", "The local model could not complete the request.")
            events.put({"type": "error", "message": str(error)})
        except Exception:
            task_monitor.finish(run_id, "failed", "An unexpected error interrupted the request.")
            events.put({"type": "error", "message": "An unexpected error interrupted the request."})
        else:
            memory.add_message(payload.conversation_id, "assistant", result["message"])
            for tool_name in result["tools_used"]:
                task_monitor.log(run_id, f"Completed built-in tool: {tool_name}.")
            task_monitor.finish(run_id, "completed", "Nico finished the response.")
            events.put(
                {
                    "type": "done",
                    "message": result["message"],
                    "tools_used": result["tools_used"],
                    "model": result["model"],
                    "memory_count": memory.count(payload.conversation_id),
                    "memory_limit": MAX_MESSAGES_PER_CONVERSATION,
                }
            )
        finally:
            events.put(None)

    def stream_events():
        worker = threading.Thread(target=run_chat, daemon=True)
        worker.start()
        while True:
            try:
                event = events.get(timeout=15)
            except queue.Empty:
                yield '{"type":"ping"}\n'
                continue
            if event is None:
                break
            yield json.dumps(event, ensure_ascii=False) + "\n"

    return StreamingResponse(
        stream_events(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/assistant/memory/{conversation_id}")
def get_conversation_memory(conversation_id: str, limit: int = 100) -> dict:
    if not conversation_id or len(conversation_id) > 64:
        raise HTTPException(status_code=400, detail="invalid conversation_id")
    return {
        "messages": memory.recent(conversation_id, limit),
        "count": memory.count(conversation_id),
        "limit": MAX_MESSAGES_PER_CONVERSATION,
    }


@app.delete("/api/assistant/memory/{conversation_id}")
def clear_conversation_memory(conversation_id: str) -> dict:
    if not conversation_id or len(conversation_id) > 64:
        raise HTTPException(status_code=400, detail="invalid conversation_id")
    memory.clear(conversation_id)
    return {
        "cleared": True,
        "conversation_id": conversation_id,
        "limit": MAX_MESSAGES_PER_CONVERSATION,
    }


@app.get("/api/archer/status")
def archer_status() -> dict:
    return assistant.archer_status()


# ── Leo Valdez — backup offline chatbot ──────────────────────────────────────────

@app.get("/api/leo/status")
@app.get("/api/zara/status")
def leo_status() -> dict:
    return leo.model_status()


class LeoChatRequest(BaseModel):
    conversation_id: str = Field(min_length=1, max_length=64, pattern="^[A-Za-z0-9_-]+$")
    message: str = Field(min_length=1, max_length=4000)

    @field_validator("message")
    @classmethod
    def message_must_not_be_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("message must not be blank")
        return v


ZaraChatRequest = LeoChatRequest


@app.post("/api/leo/chat")
@app.post("/api/zara/chat")
def leo_chat(payload: LeoChatRequest) -> StreamingResponse:
    """Streaming chat endpoint for Leo Valdez, Orion's witty backup mechanic assistant."""
    conv_key = f"leo:{payload.conversation_id}"
    history = memory.recent(conv_key, limit=30)
    memory.add_message(conv_key, "user", payload.message)
    run_id = task_monitor.start("Leo Valdez assistant response", "ai")
    task_monitor.log(run_id, "Leo Valdez is tinkering with a response… 🔥")
    events: queue.Queue[dict | None] = queue.Queue()

    def run_leo() -> None:
        streamed_chunks = 0

        def on_delta(text: str) -> None:
            nonlocal streamed_chunks
            streamed_chunks += 1
            if streamed_chunks == 1:
                task_monitor.log(run_id, "Leo stream started.")
            events.put({"type": "delta", "content": text})

        try:
            result = leo.chat(payload.message, history=history, on_delta=on_delta)
        except NicoModelError as error:
            task_monitor.finish(run_id, "failed", "Leo Valdez could not complete the request.")
            events.put({"type": "error", "message": str(error)})
        except Exception:
            task_monitor.finish(run_id, "failed", "Leo Valdez encountered an unexpected error.")
            events.put({"type": "error", "message": "An unexpected error occurred."})
        else:
            memory.add_message(conv_key, "assistant", result["message"])
            task_monitor.finish(run_id, "completed", "Leo Valdez finished his response. 🔥")
            events.put({
                "type": "done",
                "message": result["message"],
                "model": result["model"],
                "memory_count": memory.count(conv_key),
                "memory_limit": MAX_MESSAGES_PER_CONVERSATION,
            })
        finally:
            events.put(None)

    def stream_events():
        worker = threading.Thread(target=run_leo, daemon=True)
        worker.start()
        while True:
            try:
                event = events.get(timeout=15)
            except queue.Empty:
                yield '{"type":"ping"}\n'
                continue
            if event is None:
                break
            yield json.dumps(event, ensure_ascii=False) + "\n"

    return StreamingResponse(
        stream_events(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.delete("/api/leo/memory/{conversation_id}")
@app.delete("/api/zara/memory/{conversation_id}")
def clear_leo_memory(conversation_id: str) -> dict:
    memory.clear(f"leo:{conversation_id}")
    memory.clear(f"zara:{conversation_id}")
    return {"cleared": True, "conversation_id": conversation_id}



@app.post("/api/archer/generate")
@app.post("/api/assistant/generate-image")
def generate_archer_image(payload: ArcherImageRequest) -> dict:
    run_id = task_monitor.start("Generate image with Archer", "image")
    task_monitor.log(run_id, f'Prompt: "{payload.prompt}" | Mode: {payload.mode}')
    try:
        task_monitor.log(run_id, f"Executing synthesis pipeline ({payload.mode} mode, {payload.width}x{payload.height})...")
        result = assistant.generate_archer_image(
            payload.prompt,
            width=payload.width,
            height=payload.height,
            mode=payload.mode,
        )
        task_monitor.log(run_id, f"Image synthesized: {result.get('url', 'generated')}")
        task_monitor.finish(run_id, "completed", f"Archer generation completed ({result.get('mode', payload.mode)}).")
        return result
    except (ArcherGenerationError, LiveDataError) as error:
        task_monitor.finish(run_id, "failed", f"Archer generation failed: {error}")
        raise HTTPException(status_code=503, detail=str(error)) from error
    except Exception:
        task_monitor.finish(run_id, "failed", "An unexpected error interrupted the request.")
        raise


@app.get("/api/archer/images/{filename}")
def get_archer_image(filename: str) -> FileResponse:
    if Path(filename).name != filename or not filename.startswith("archer_") or not filename.endswith(".png"):
        raise HTTPException(status_code=404, detail="Image not found")
    image_path = assistant.output_dir / filename
    if not image_path.is_file():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(image_path, media_type="image/png")


@app.get("/api/devices")
def list_devices() -> list[dict]:
    return device_manager.list_devices()


@app.post("/api/devices")
def create_device(payload: dict) -> dict:
    name = str(payload.get("name", "New device")).strip() or "New device"
    kind = str(payload.get("kind", "desktop")).strip() or "desktop"
    return run_tracked(
        "Register device",
        "device",
        lambda: device_manager.register_device(name, kind),
    )


@app.get("/api/tasks")
def list_tasks() -> list[dict]:
    return device_manager.list_tasks()


@app.post("/api/tasks")
def create_task(payload: dict) -> dict:
    device_id = str(payload.get("device_id", "")).strip()
    task = str(payload.get("task", "")).strip()

    if not device_id or not task:
        raise HTTPException(status_code=400, detail="device_id and task are required")

    if device_id not in device_manager.devices:
        raise HTTPException(status_code=404, detail="device not found")

    return run_tracked(
        "Queue device task",
        "device",
        lambda: device_manager.enqueue_task(device_id, task),
    )


@app.get("/api/system/metrics")
def system_metrics() -> dict:
    return get_system_telemetry()


@app.get("/api/system/processes")
def system_processes(limit: int = 30) -> dict:
    """Return top running processes sorted by CPU then memory for the sidebar Task Manager."""
    try:
        import psutil  # already a project dependency via telemetry
    except ImportError:
        return {"processes": [], "total": 0, "available": False}

    procs: list[dict] = []
    for p in psutil.process_iter(["pid", "name", "status", "cpu_percent", "memory_info"]):
        try:
            info = p.info
            mem_mb = round(info["memory_info"].rss / (1024 ** 2), 1) if info["memory_info"] else 0.0
            procs.append({
                "pid": info["pid"],
                "name": (info["name"] or "?")[:40],
                "status": info["status"] or "unknown",
                "cpu": round(info["cpu_percent"] or 0.0, 1),
                "cpu_percent": round(info["cpu_percent"] or 0.0, 1),
                "mem_mb": mem_mb,
                "memory_mb": mem_mb,
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    total = len(procs)
    procs.sort(key=lambda x: (-x["cpu"], -x["mem_mb"]))
    return {"processes": procs[:limit], "total": total, "available": True}


@app.delete("/api/devices/{device_id}")
def delete_device(device_id: str) -> dict:
    deleted = device_manager.delete_device(device_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="device not found")
    return {"deleted": True, "device_id": device_id}


@app.post("/api/devices/{device_id}/ping")
def ping_device(device_id: str) -> dict:
    try:
        return device_manager.ping_device(device_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="device not found")


@app.patch("/api/tasks/{task_id}")
@app.post("/api/tasks/{task_id}/status")
def update_task_status(task_id: str, payload: dict) -> dict:
    status = str(payload.get("status", "")).strip()
    if not status:
        raise HTTPException(status_code=400, detail="status is required")
    try:
        return device_manager.update_task_status(task_id, status)
    except KeyError:
        raise HTTPException(status_code=404, detail="task not found")
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


@app.delete("/api/tasks/{task_id}")
def delete_task(task_id: str) -> dict:
    deleted = device_manager.delete_task(task_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="task not found")
    return {"deleted": True, "task_id": task_id}


@app.get("/api/assistant/memory/{conversation_id}/export")
def export_conversation_memory(conversation_id: str, format: str = "markdown") -> dict:
    if not conversation_id or len(conversation_id) > 64:
        raise HTTPException(status_code=400, detail="invalid conversation_id")
    content = memory.export(conversation_id, export_format=format)
    return {"conversation_id": conversation_id, "format": format, "content": content}


@app.get("/api/ollama/models")
@app.get("/api/ai/models")
def get_ollama_models() -> dict:
    return assistant.model_status()


@app.post("/api/ollama/model")
def set_ollama_model(payload: dict) -> dict:
    model_name = str(payload.get("model", "")).strip()
    if not model_name:
        raise HTTPException(status_code=400, detail="model is required")
    try:
        active = assistant.set_model(model_name)
        return {"model": active, "status": assistant.model_status()}
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


@app.get("/api/archer/gallery")
def get_archer_gallery() -> list[dict]:
    return assistant.list_gallery()


@app.delete("/api/archer/images/{filename}")
def delete_archer_image(filename: str) -> dict:
    deleted = assistant.delete_gallery_image(filename)
    if not deleted:
        raise HTTPException(status_code=404, detail="Image not found")
    return {"deleted": True, "filename": filename}


@app.post("/api/task-runs/clear")
def clear_task_runs() -> dict:
    cleared = task_monitor.clear_finished()
    return {"cleared_count": cleared}


# ---------------------------------------------------------------------------
# Telegram Module (Social Hub)
# ---------------------------------------------------------------------------
# All Telegram endpoints and logic live inside orion_app/telegram. The router is
# mounted here so the Social Hub's Telegram tab has a single, self-contained API.
from .telegram.routes import router as telegram_router  # noqa: E402

app.include_router(telegram_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("orion_app.main:app", host="0.0.0.0", port=8000, reload=False)
