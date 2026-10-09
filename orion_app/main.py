from __future__ import annotations

import json
import os
import queue
import threading
from pathlib import Path
from typing import Callable, Literal, TypeVar

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse

from .ai import ArcherGenerationError, LiveDataError, NicoAssistant, NicoModelError
from .devices import DeviceManager
from .instagram import InstagramError, InstagramIntegration
from .memory import MAX_MESSAGES_PER_CONVERSATION, ConversationMemory
from .task_monitor import TaskMonitor

BASE_DIR = Path(__file__).resolve().parent
assistant = NicoAssistant()
device_manager = DeviceManager()
task_monitor = TaskMonitor()
memory = ConversationMemory(
    os.getenv("ORION_MEMORY_PATH", str(BASE_DIR / "data" / "conversations.sqlite3"))
)
instagram = InstagramIntegration()
app = FastAPI(title="Orion the Warrior", version="0.1.0")
Result = TypeVar("Result")


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


class InstagramMessageRequest(BaseModel):
    recipient_id: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1, max_length=1000)

    @field_validator("message")
    @classmethod
    def message_must_not_be_blank(cls, message: str) -> str:
        message = message.strip()
        if not message:
            raise ValueError("message must not be blank")
        return message


class InstagramPublishRequest(BaseModel):
    image_url: str = Field(min_length=1, max_length=2048)
    caption: str = Field(default="", max_length=2200)


@app.get("/")
def read_index() -> FileResponse:
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.get("/static/{filename}")
def read_static(filename: str) -> FileResponse:
    file_path = BASE_DIR / "static" / filename
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "app": "Orion the Warrior", "assistant": assistant.name}


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


@app.get("/api/instagram/conversations/{conversation_id}/messages")
def instagram_conversation_messages(conversation_id: str) -> dict:
    try:
        return run_tracked(
            "Load Instagram conversation",
            "social",
            lambda: instagram.conversation_messages(conversation_id),
        )
    except InstagramError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.post("/api/instagram/messages")
def instagram_send_message(payload: InstagramMessageRequest) -> dict:
    try:
        return run_tracked(
            "Send Instagram message",
            "social",
            lambda: instagram.send_message(payload.recipient_id, payload.message),
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


@app.post("/api/archer/generate")
@app.post("/api/assistant/generate-image")
def generate_archer_image(payload: ArcherImageRequest) -> dict:
    try:
        return run_tracked(
            "Generate image with Archer",
            "image",
            lambda: assistant.generate_archer_image(
                payload.prompt,
                width=payload.width,
                height=payload.height,
                mode=payload.mode,
            ),
        )
    except (ArcherGenerationError, LiveDataError) as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


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
