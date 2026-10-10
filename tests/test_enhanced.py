import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from orion_app.ai import NicoAssistant, LiveDataError
from orion_app.devices import DeviceManager
from orion_app.main import app, device_manager, assistant
from orion_app.memory import ConversationMemory
from orion_app.telemetry import get_system_telemetry


def test_system_telemetry_returns_valid_metrics():
    telemetry = get_system_telemetry()
    assert "timestamp" in telemetry
    assert "platform" in telemetry
    assert "cpu" in telemetry
    assert "memory" in telemetry
    assert "disk" in telemetry
    assert "uptime" in telemetry
    assert telemetry["platform"]["system"] != ""
    assert isinstance(telemetry["cpu"]["usage_percent"], (int, float))


def test_device_manager_sqlite_persistence_and_lifecycle(tmp_path):
    db_path = tmp_path / "devices.sqlite3"
    dm1 = DeviceManager(db_path=db_path)
    # Register custom device
    drone = dm1.register_device("recon-drone-01", "drone")
    assert drone["name"] == "recon-drone-01"
    assert drone["status"] == "online"

    # Enqueue task
    task = dm1.enqueue_task(drone["id"], "Survey perimeter")
    assert task["status"] == "queued"

    # Update task status
    updated = dm1.update_task_status(task["id"], "in_progress")
    assert updated["status"] == "in_progress"

    # Reopen database in second manager instance
    dm2 = DeviceManager(db_path=db_path)
    assert drone["id"] in dm2.devices
    assert dm2.devices[drone["id"]]["name"] == "recon-drone-01"
    persisted_task = next(t for t in dm2.list_tasks() if t["id"] == task["id"])
    assert persisted_task["status"] == "in_progress"

    # Ping device
    pinged = dm2.ping_device(drone["id"])
    assert pinged["status"] == "online"
    assert pinged["last_seen"] is not None

    # Complete task
    completed = dm2.update_task_status(task["id"], "completed")
    assert completed["status"] == "completed"
    assert completed["completed_at"] is not None

    # Delete task
    assert dm2.delete_task(task["id"]) is True
    assert all(t["id"] != task["id"] for t in dm2.list_tasks())

    # Delete device
    assert dm2.delete_device(drone["id"]) is True
    assert drone["id"] not in dm2.devices


def test_nico_calculator_and_telemetry_tools(tmp_path):
    nico = NicoAssistant(output_dir=tmp_path)

    # Test calculator tool
    calc_res = nico._run_tool("calculator", {"expression": "25 * 4 + 10"}, [], [])
    assert calc_res["result"] == 110

    sqrt_res = nico._run_tool("calculator", {"expression": "sqrt(144)"}, [], [])
    assert sqrt_res["result"] == 12

    # Test telemetry tool
    telem_res = nico._run_tool("get_system_telemetry", {}, [], [])
    assert "cpu" in telem_res
    assert "memory" in telem_res

    # Test queue device task tool with callback
    queued_calls = []
    task_res = nico._run_tool(
        "queue_device_task",
        {"device_id": "dev-1", "task": "Run diagnostics"},
        [],
        [],
        on_queue_task=lambda d, t: queued_calls.append((d, t)) or {"queued": True},
    )
    assert queued_calls == [("dev-1", "Run diagnostics")]
    assert task_res == {"queued": True}


def test_conversation_memory_export(tmp_path):
    db_path = tmp_path / "conv.sqlite3"
    mem = ConversationMemory(db_path)
    mem.add_message("test-conv", "user", "What is the mission?")
    mem.add_message("test-conv", "assistant", "Our mission is Orion.")

    md_export = mem.export("test-conv", export_format="markdown")
    assert "What is the mission?" in md_export
    assert "Our mission is Orion." in md_export
    assert "# Orion Chat Export" in md_export

    json_export = mem.export("test-conv", export_format="json")
    parsed = json.loads(json_export)
    assert len(parsed) == 2
    assert parsed[0]["content"] == "What is the mission?"


def test_archer_gallery_and_model_switching(tmp_path):
    nico = NicoAssistant(output_dir=tmp_path)

    # Create dummy image in output_dir
    dummy_img = tmp_path / "archer_12345.png"
    dummy_img.write_bytes(b"dummy image bytes")

    gallery = nico.list_gallery()
    assert len(gallery) == 1
    assert gallery[0]["filename"] == "archer_12345.png"
    assert gallery[0]["url"] == "/api/archer/images/archer_12345.png"

    # Model switching
    nico.set_model("llama3.2:1b")
    assert nico.model == "llama3.2:1b"

    # Delete image
    assert nico.delete_gallery_image("archer_12345.png") is True
    assert len(nico.list_gallery()) == 0


def test_enhanced_api_endpoints():
    client = TestClient(app)

    # Telemetry endpoint
    metrics_res = client.get("/api/system/metrics")
    assert metrics_res.status_code == 200
    metrics = metrics_res.json()
    assert "cpu" in metrics
    assert "memory" in metrics

    # Device lifecycle via API
    dev_res = client.post("/api/devices", json={"name": "test-sensor", "kind": "iot"})
    assert dev_res.status_code == 200
    device_id = dev_res.json()["id"]

    ping_res = client.post(f"/api/devices/{device_id}/ping")
    assert ping_res.status_code == 200
    assert ping_res.json()["status"] == "online"

    # Task lifecycle via API
    task_res = client.post("/api/tasks", json={"device_id": device_id, "task": "Calibrate sensor"})
    assert task_res.status_code == 200
    task_id = task_res.json()["id"]

    patch_res = client.patch(f"/api/tasks/{task_id}", json={"status": "in_progress"})
    assert patch_res.status_code == 200
    assert patch_res.json()["status"] == "in_progress"

    del_task_res = client.delete(f"/api/tasks/{task_id}")
    assert del_task_res.status_code == 200

    del_dev_res = client.delete(f"/api/devices/{device_id}")
    assert del_dev_res.status_code == 200

    # Task monitor clear
    clear_res = client.post("/api/task-runs/clear")
    assert clear_res.status_code == 200
    assert "cleared_count" in clear_res.json()

