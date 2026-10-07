from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from .ai import NicoAssistant
from .devices import DeviceManager

BASE_DIR = Path(__file__).resolve().parent
assistant = NicoAssistant()
device_manager = DeviceManager()
app = FastAPI(title="Orion the Warrior", version="0.1.0")


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


@app.post("/api/assistant/respond")
def assistant_respond(payload: dict) -> dict:
    prompt = str(payload.get("prompt", ""))
    return assistant.respond(prompt)


@app.post("/api/assistant/generate-image")
def generate_image(payload: dict) -> dict:
    prompt = str(payload.get("prompt", ""))
    return assistant.generate_image(prompt)


@app.get("/api/devices")
def list_devices() -> list[dict]:
    return device_manager.list_devices()


@app.post("/api/devices")
def create_device(payload: dict) -> dict:
    name = str(payload.get("name", "New device")).strip() or "New device"
    kind = str(payload.get("kind", "desktop"))
    return device_manager.register_device(name, kind)


@app.get("/api/tasks")
def list_tasks() -> list[dict]:
    return device_manager.list_tasks()


@app.post("/api/tasks")
def create_task(payload: dict) -> dict:
    device_id = str(payload.get("device_id", "")).strip()
    task = str(payload.get("task", "")).strip()

    if not device_id or not task:
        raise HTTPException(status_code=400, detail="device_id and task are required")

    return device_manager.enqueue_task(device_id, task)
