from __future__ import annotations

import copy
import queue
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator


class TaskMonitor:
    def __init__(self, max_runs: int = 100) -> None:
        self._max_runs = max_runs
        self._max_logs_per_run = 200
        self._runs: list[dict] = []
        self._subscribers: set[queue.Queue[dict]] = set()
        self._lock = threading.RLock()

    def start(self, title: str, category: str = "operation") -> str:
        now = self._now()
        run = {
            "id": str(uuid.uuid4()),
            "title": title,
            "category": category,
            "status": "running",
            "started_at": now,
            "completed_at": None,
            "logs": [],
        }
        with self._lock:
            self._runs.insert(0, run)
            self._trim_history_locked()
            self._append_log_locked(run, "Execution started.", "info")
            self._publish_locked(run)
        return run["id"]

    def log(self, run_id: str, message: str, level: str = "info") -> None:
        with self._lock:
            run = self._find_locked(run_id)
            if run["status"] != "running":
                return
            self._append_log_locked(run, message, level)
            self._publish_locked(run)

    def finish(self, run_id: str, status: str, message: str) -> None:
        if status not in {"completed", "failed", "cancelled"}:
            raise ValueError("Task status must be completed, failed, or cancelled.")
        with self._lock:
            run = self._find_locked(run_id)
            if run["status"] != "running":
                return
            run["status"] = status
            run["completed_at"] = self._now()
            self._append_log_locked(run, message, "error" if status == "failed" else "success")
            self._publish_locked(run)
            self._trim_history_locked()

    def list_runs(self, limit: int | None = None) -> list[dict]:
        if limit is not None and not 1 <= limit <= self._max_runs:
            raise ValueError(f"limit must be between 1 and {self._max_runs}.")
        with self._lock:
            if limit is not None:
                return copy.deepcopy(self._runs[:limit])
            return copy.deepcopy(self._runs)

    def clear_finished(self) -> int:
        with self._lock:
            before = len(self._runs)
            self._runs = [run for run in self._runs if run["status"] == "running"]
            return before - len(self._runs)

    @contextmanager
    def subscribe(self) -> Iterator[queue.Queue[dict]]:
        subscriber: queue.Queue[dict] = queue.Queue()
        with self._lock:
            self._subscribers.add(subscriber)
        try:
            yield subscriber
        finally:
            with self._lock:
                self._subscribers.discard(subscriber)

    def _find_locked(self, run_id: str) -> dict:
        for run in self._runs:
            if run["id"] == run_id:
                return run
        raise KeyError(f"Task run {run_id} is not available.")

    def _append_log_locked(self, run: dict, message: str, level: str) -> None:
        run["logs"].append(
            {"timestamp": self._now(), "level": level, "message": message}
        )
        del run["logs"][: max(0, len(run["logs"]) - self._max_logs_per_run)]

    def _publish_locked(self, run: dict) -> None:
        event = copy.deepcopy(run)
        for subscriber in self._subscribers:
            subscriber.put(event)

    def _trim_history_locked(self) -> None:
        while len(self._runs) > self._max_runs:
            oldest_finished = next(
                (index for index in range(len(self._runs) - 1, -1, -1)
                 if self._runs[index]["status"] != "running"),
                None,
            )
            if oldest_finished is None:
                return
            self._runs.pop(oldest_finished)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
