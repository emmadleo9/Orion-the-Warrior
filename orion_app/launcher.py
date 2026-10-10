"""Bridge the Orion launcher (start_orion.bat) into the live task monitor.

The Windows launcher writes structured lines to ``logs/launcher.log`` while it
runs. This watcher tails that file and mirrors every line into the existing
``TaskMonitor`` so launcher activity appears in the in-app live execution
console and the Task activity view.
"""

from __future__ import annotations

import os
import threading
from datetime import datetime, timezone
from pathlib import Path

from .task_monitor import TaskMonitor

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LOG_PATH = PROJECT_ROOT / "logs" / "launcher.log"

# Lines written by the launcher look like: [ORION][INFO] Message text
LINE_PREFIX = "[ORION]"
RUN_TITLE = "Orion launcher · start_orion.bat"
RUN_CATEGORY = "launcher"
MAX_MESSAGE_LENGTH = 400

_LEVEL_TOKENS = {
    "INFO": "info",
    "SUCCESS": "success",
    "OK": "success",
    "WARN": "warning",
    "WARNING": "warning",
    "ERROR": "error",
    "FAIL": "error",
}
# Terminal token: log the message, then close the launcher run.
DONE_TOKEN = "DONE"


class LauncherMonitor:
    """Tail the launcher log file and publish its lines into a TaskMonitor."""

    def __init__(
        self,
        task_monitor: TaskMonitor,
        log_path: str | Path | None = None,
        poll_interval: float = 0.75,
    ) -> None:
        self._task_monitor = task_monitor
        configured = log_path or os.getenv("ORION_LAUNCHER_LOG") or DEFAULT_LOG_PATH
        self._log_path = Path(configured)
        self._poll_interval = poll_interval
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._offset = 0
        self._partial = ""
        self._run_id: str | None = None
        self._session_started_at: str | None = None
        self._lines_ingested = 0
        self._last_line: str | None = None

    # -- lifecycle ---------------------------------------------------------

    def start(self) -> None:
        """Start the background tail thread (idempotent)."""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._watch,
                name="orion-launcher-monitor",
                daemon=True,
            )
            self._thread.start()

    def stop(self) -> None:
        """Stop the background tail thread."""
        self._stop_event.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=2.0)

    # -- inspection --------------------------------------------------------

    @property
    def log_path(self) -> Path:
        return self._log_path

    def status(self) -> dict:
        """Report whether the launcher log is present and being followed."""
        with self._lock:
            return {
                "log_path": str(self._log_path),
                "log_exists": self._log_path.is_file(),
                "attached": self._run_id is not None,
                "run_id": self._run_id,
                "session_started_at": self._session_started_at,
                "lines_ingested": self._lines_ingested,
                "last_line": self._last_line,
            }

    # -- polling -----------------------------------------------------------

    def poll(self) -> None:
        """Read any new launcher output. Safe to call from any thread."""
        path = self._log_path
        if not path.is_file():
            return

        with path.open("rb") as handle:
            if handle.seek(0, os.SEEK_END) < self._offset:
                # The launcher truncated the log: a brand new session began.
                self._reset_session()
            handle.seek(self._offset)
            chunk = handle.read()
            offset = handle.tell()

        if not chunk:
            return

        with self._lock:
            self._offset = offset

        text = self._partial + chunk.decode("utf-8", errors="replace")
        lines = text.split("\n")
        self._partial = lines.pop()

        for raw_line in lines:
            self._ingest(raw_line)

    def _watch(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.poll()
            except OSError:
                pass
            self._stop_event.wait(self._poll_interval)

    # -- internals ---------------------------------------------------------

    def _reset_session(self) -> None:
        """Close the previous launcher run and rewind to the start of the log."""
        with self._lock:
            self._offset = 0
            self._partial = ""
        self._close_run("Launcher session ended.")

    def _ingest(self, raw_line: str) -> None:
        message, level, is_terminal = self._parse(raw_line)
        if not message:
            return

        self._ensure_run()
        with self._lock:
            run_id = self._run_id
        if run_id is None:
            return

        try:
            self._task_monitor.log(run_id, message, level)
        except KeyError:
            # The run was trimmed from history; start a fresh one next line.
            with self._lock:
                self._run_id = None
            return

        with self._lock:
            self._lines_ingested += 1
            self._last_line = message

        if is_terminal:
            self._close_run("Launcher finished.")

    def _ensure_run(self) -> None:
        with self._lock:
            if self._run_id is not None:
                return

        run_id = self._task_monitor.start(RUN_TITLE, RUN_CATEGORY)
        self._task_monitor.log(run_id, "Launcher session attached.", "info")
        with self._lock:
            self._run_id = run_id
            self._session_started_at = datetime.now(timezone.utc).isoformat()

    def _close_run(self, message: str) -> None:
        with self._lock:
            run_id, self._run_id = self._run_id, None
        if run_id is None:
            return
        try:
            self._task_monitor.finish(run_id, "completed", message)
        except KeyError:
            pass

    @staticmethod
    def _parse(raw_line: str) -> tuple[str, str, bool]:
        """Return (message, level, is_terminal) for one launcher log line."""
        line = raw_line.strip()
        if not line:
            return "", "info", False
        if not line.startswith(LINE_PREFIX):
            return line[:MAX_MESSAGE_LENGTH], "info", False

        remainder = line[len(LINE_PREFIX):].strip()
        if not remainder.startswith("["):
            return remainder[:MAX_MESSAGE_LENGTH], "info", False

        token, separator, message = remainder[1:].partition("]")
        if not separator:
            return remainder[:MAX_MESSAGE_LENGTH], "info", False

        token = token.strip().upper()
        message = message.strip()[:MAX_MESSAGE_LENGTH]
        if token == DONE_TOKEN:
            return message or "Launcher finished.", "success", True
        return message, _LEVEL_TOKENS.get(token, "info"), False
