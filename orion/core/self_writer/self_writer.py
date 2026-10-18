"""Orion Self-Writer — main engine.

Public entry point:
    write_code(admin_command: str) -> dict

Flow:
    1. Scan the Orion codebase so the LLM knows what exists.
    2. Ask the model to write/rewrite code for the admin command.
    3. Sandbox-test it (AST syntax check, build/typecheck when available).
    4. On failure, auto-correct with the model (max 5 loops).
    5. Produce a diff for admin review.
    6. After admin approval, apply the change (with backup).

The engine is stack-aware: it detects Orion is a Python/FastAPI app and targets
the correct directories (orion_app/, static/, etc.).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .codebase_scanner import scan_codebase, render_snapshot_for_llm
from .diff_utils import build_diff, format_diff_for_ui
from .model_client import ChatMessage, ModelClient, ModelClientError
from .sandbox import DiffResult, Sandbox, SandboxConfig

# Root of the Orion project (parent of this package: .../Orion The Warrior)
PROJECT_ROOT = Path(__file__).resolve().parents[3]

# Where self-written changes land. Orion is a Python/FastAPI app, so source lives
# under orion_app/ and static assets under orion_app/static/.
SOURCE_DIRS = ["orion_app", "static", "scripts"]
BACKUP_DIR = PROJECT_ROOT / "orion" / "backups"

# System prompt that teaches the model Orion's stack and conventions.
SYSTEM_PROMPT = """You are Orion's self-writing engineer. Orion is a local-first
FastAPI/Python web application with a vanilla HTML/JS/CSS frontend (cyber-tactical
neon aesthetic). It runs on Ollama locally (no paid APIs).

Your job: rewrite or add code to Orion based on an admin command.

Rules:
- Return ONLY the complete file contents — no markdown fences, no explanations.
- Match Orion's existing style: FastAPI routes in orion_app/main.py, assistants in
  orion_app/ai.py, static HTML/JS/CSS in orion_app/static/.
- Prefer adding new files over editing unrelated ones.
- Keep generated code self-contained, safe, and dependency-free where possible.
- Never delete existing functionality unless the command explicitly asks for it.
- For Python: use stdlib + FastAPI/Pydantic patterns already in the codebase.
- For frontend: vanilla JS, no React/Next.js unless the codebase already uses it.
- Admin commands are trusted, but still write defensive, bounded code.
"""


@dataclass
class WriteResult:
    success: bool
    message: str
    diff: Optional[dict] = None
    applied: bool = False
    backup_path: Optional[str] = None
    model_used: Optional[str] = None


class SelfWriter:
    def __init__(
        self,
        root: str | Path = PROJECT_ROOT,
        model_client: Optional[ModelClient] = None,
        max_fix_loops: int = 5,
    ) -> None:
        self.root = Path(root).resolve()
        self.model = model_client or ModelClient()
        self.max_fix_loops = max_fix_loops
        self.sandbox = Sandbox(
            SandboxConfig(
                root=self.root,
                max_fix_loops=max_fix_loops,
                backup_dir=BACKUP_DIR,
            ),
            model_client=self.model,
        )
        self._snapshot_text: Optional[str] = None

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def write_code(self, admin_command: str, target_rel_path: Optional[str] = None) -> WriteResult:
        """Orion self-writes code from an admin command.

        Parameters
        ----------
        admin_command : str
            Natural-language instruction, e.g. "add a dark mode toggle" or
            "create a login page".
        target_rel_path : str | None
            Optional hint for which file to write. If omitted, the model picks
            the best target based on the command and codebase.
        """
        try:
            return self._run(admin_command, target_rel_path)
        except ModelClientError as exc:
            return WriteResult(success=False, message=str(exc))
        except Exception as exc:  # pragma: no cover - defensive
            return WriteResult(success=False, message=f"Self-writer error: {exc}")

    def status(self) -> dict:
        return {
            "root": str(self.root),
            "backup_dir": str(BACKUP_DIR),
            "model": self.model.available(),
            "max_fix_loops": self.max_fix_loops,
        }

    # ------------------------------------------------------------------ #
    # Internal orchestration
    # ------------------------------------------------------------------ #
    def _run(self, admin_command: str, target_rel_path: Optional[str]) -> WriteResult:
        # 1. Scan codebase (cached within one run).
        if self._snapshot_text is None:
            snapshot = scan_codebase(self.root, include_content=True)
            self._snapshot_text = render_snapshot_for_llm(snapshot)

        # 2. Ask the model what file to target and what code to write.
        target = target_rel_path or self._pick_target(admin_command)
        new_code = self._generate_code(admin_command, target)

        # 3. Sandbox: test + auto-fix loop.
        def write_fn(command: str, snapshot_text: str) -> str:
            return self._generate_code(command, target)

        diff = self.sandbox.generate_and_validate(
            admin_command=admin_command,
            snapshot_text=self._snapshot_text,
            target_rel_path=target,
            write_code_fn=write_fn,
        )

        # 4. Build the UI diff.
        file_diff = build_diff(diff.file_path, diff.old_code, diff.new_code)
        diff_dict = {
            "file_path": file_diff.file_path,
            "unified_diff": file_diff.unified_diff,
            "added_lines": file_diff.added_lines,
            "removed_lines": file_diff.removed_lines,
            "is_new_file": file_diff.is_new_file,
            "summary": format_diff_for_ui(file_diff),
            "new_code": file_diff.new_code,
            "old_code": file_diff.old_code or "",
        }

        return WriteResult(
            success=True,
            message=diff.message or "Code generated and validated.",
            diff=diff_dict,
            applied=False,
            backup_path=None,
            model_used=getattr(self.model, "ollama_model", None),
        )

    def approve_and_apply(self, diff_dict: dict) -> WriteResult:
        """Apply a previously generated diff after admin approval."""
        diff = DiffResult(
            file_path=diff_dict["file_path"],
            old_code=diff_dict.get("old_code"),
            new_code=diff_dict["new_code"],
            approved=True,
        )
        ok = self.sandbox.apply(diff)
        if not ok:
            return WriteResult(
                success=False,
                message="Diff was not approved or could not be applied.",
            )
        return WriteResult(
            success=True,
            message=f"Applied and hot-reloadable: {diff.file_path}",
            applied=True,
            backup_path=diff.backup_path,
            diff={
                "file_path": diff.file_path,
                "summary": format_diff_for_ui(
                    build_diff(diff.file_path, diff.old_code, diff.new_code)
                ),
            },
        )

    # ------------------------------------------------------------------ #
    # Model prompts
    # ------------------------------------------------------------------ #
    def _pick_target(self, admin_command: str) -> str:
        """Ask the model which file to write, or default to a sensible path."""
        prompt = (
            "Orion is a Python/FastAPI app. Source lives under orion_app/\n"
            "and static assets under orion_app/static/.\n\n"
            "Admin command: {command}\n\n"
            "Codebase snapshot:\n{snapshot}\n\n"
            "Pick ONE target file path (relative to project root) to write "
            "for this command. Return ONLY the path, e.g. "
            "orion_app/static/self_writer.html or orion_app/main.py.\n"
            "If creating something new, pick a clear new path."
        ).format(command=admin_command, snapshot=self._snapshot_text or "")
        messages = [
            ChatMessage("system", SYSTEM_PROMPT),
            ChatMessage("user", prompt),
        ]
        target = self.model.chat(messages, temperature=0.0).strip().strip("`").strip()
        if not target or "/" not in target:
            target = "orion_app/static/self_writer.html"
        return target

    def _generate_code(self, admin_command: str, target_rel_path: str) -> str:
        prompt = (
            "Admin command: {command}\n\n"
            "Target file (relative to project root): {target}\n\n"
            "Codebase snapshot:\n{snapshot}\n\n"
            "Write the COMPLETE file contents for {target} that fulfills the "
            "admin command. Return ONLY the file contents — no markdown fences, "
            "no explanations, no lead-in text."
        ).format(
            command=admin_command,
            target=target_rel_path,
            snapshot=self._snapshot_text or "",
        )
        messages = [
            ChatMessage("system", SYSTEM_PROMPT),
            ChatMessage("user", prompt),
        ]
        return self.model.chat(messages, temperature=0.2)


# Convenience module-level function for simple scripting.
def write_code(admin_command: str, target_rel_path: Optional[str] = None) -> WriteResult:
    """Module-level helper: SelfWriter().write_code(command, target)."""
    return SelfWriter().write_code(admin_command, target_rel_path)
