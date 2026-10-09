import pytest

from orion_app.task_monitor import TaskMonitor


def test_task_monitor_publishes_run_lifecycle_and_keeps_messages_safe():
    monitor = TaskMonitor()
    with monitor.subscribe() as subscriber:
        run_id = monitor.start("Nico assistant response", "ai")
        started = subscriber.get_nowait()
        assert started["id"] == run_id
        assert started["status"] == "running"

        monitor.log(run_id, "Local model response stream started.")
        progress = subscriber.get_nowait()
        assert progress["logs"][-1]["message"] == "Local model response stream started."

        monitor.finish(run_id, "completed", "Nico finished the response.")
        finished = subscriber.get_nowait()

    assert finished["status"] == "completed"
    assert finished["completed_at"] is not None
    assert monitor.list_runs() == [finished]


def test_task_monitor_records_failures_and_caps_history():
    monitor = TaskMonitor(max_runs=2)
    for index in range(3):
        run_id = monitor.start(f"Run {index}")
        monitor.finish(run_id, "failed", "Operation failed.")

    runs = monitor.list_runs()
    assert len(runs) == 2
    assert [run["title"] for run in runs] == ["Run 2", "Run 1"]
    assert all(run["status"] == "failed" for run in runs)


def test_task_monitor_retains_active_runs_when_history_is_full():
    monitor = TaskMonitor(max_runs=1)
    first = monitor.start("Long-running operation")
    second = monitor.start("New operation")

    assert {run["id"] for run in monitor.list_runs()} == {first, second}
    monitor.finish(first, "completed", "Finished.")
    assert len(monitor.list_runs()) == 1


def test_task_monitor_rejects_invalid_status_and_history_limits():
    monitor = TaskMonitor()
    run_id = monitor.start("Example")

    with pytest.raises(ValueError, match="Task status"):
        monitor.finish(run_id, "unknown", "Done.")
    with pytest.raises(ValueError, match="limit"):
        monitor.list_runs(0)
