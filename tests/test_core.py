from orion_app.ai import NicoAssistant
from orion_app.devices import DeviceManager


def test_nico_can_answer_a_user_prompt():
    assistant = NicoAssistant("Nico de Angelo")
    response = assistant.respond("Summarize my day and prepare a next action")

    assert response["assistant_name"] == "Nico de Angelo"
    assert "Summary" in response["message"]
    assert "Next action" in response["message"]


def test_device_manager_registers_and_queues_tasks():
    manager = DeviceManager()
    device = manager.register_device("phone-alpha", "phone")
    task = manager.enqueue_task(device["id"], "Check notifications")

    assert device["name"] == "phone-alpha"
    assert task["device_id"] == device["id"]
    assert task["status"] == "queued"
    assert task["task"] == "Check notifications"
