"""Orion Self-Writer — safety sandbox.

Before any generated code is written to disk, the sandbox:

1. Parses Python files with ``ast`` to catch syntax errors.
2. Parses JS/TS/HTML files with a lightweight structural check.
3. Runs an optional build/typecheck command when available.
4. On failure, sends the error back to the LLM to self-correct (max 5 loops).
5. Backs up the original file in ``/orion/backups/`` before overwriting.
6. Returns a DiffResult the admin can approve or reject.

Nothing is ever written to a live source file until the admin approves the diff.
"""

from __future__ import annotations

import ast
import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from .model_client import ChatMessage, ModelClient


@dataclass
class TestResult:
    ok: bool
    error: Optional[str] = None
    output: Optional[str] = None
    fixed_code: Optional[str] = None


@dataclass
class DiffResult:
    file_path: str
    old_code: Optional[str]
    new_code: str
    approved: bool = False
    applied: bool = False
    backup_path: Optional[str] = None
    message: str = ""


@dataclass
class SandboxConfig:
    root: str | Path
    max_fix_loops: int = 5
    backup_dir: str | Path | None = None
    build_cmd: Optional[list[str]] = None  # e.g. ["npm", "run", "build"]
    typecheck_cmd: Optional[list[str]] = None  # e.g. ["tsc", "--noEmit"]


class Sandbox:
    def __init__(self, config: SandboxConfig, model_client: Optional[ModelClient] = None) -> None:
        self.root = Path(config.root).resolve()
        self.max_fix_loops = max(1, config.max_fix_loops)
        self.backup_dir = (
            Path(config.backup_dir).resolve()
            if config.backup_dir
            else self.root / "orion" / "backups"
        )
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.build_cmd = config.build_cmd
        self.typecheck_cmd = config.typecheck_cmd
        self.model = model_client

    # ------------------------------------------------------------------ #
    # Public entry point: generate, test, auto-fix, return a diff
    # ------------------------------------------------------------------ #
    def generate_and_validate(
        self,
        admin_command: str,
        snapshot_text: str,
        target_rel_path: str,
        write_code_fn: Callable[[str, str], str],
    ) -> DiffResult:
        """Full rewrite loop for one file.

        ``write_code_fn(command, snapshot) -> new_code`` asks the LLM for code.
        The result is tested; on failure it is sent back to the LLM with the
        error for up to ``max_fix_loops`` iterations.
        """
        target_path = self.root / target_rel_path
        old_code = None
        if target_path.is_file():
            try:
                old_code = target_path.read_text(encoding="utf-8")
            except OSError:
                old_code = None

        new_code = write_code_fn(admin_command, snapshot_text)

        # Test + auto-fix loop.
        for attempt in range(1, self.max_fix_loops + 1):
            test = self._test_code(target_rel_path, new_code)
            if test.ok:
                break
            if attempt >= self.max_fix_loops:
                return DiffResult(
                    file_path=target_rel_path,
                    old_code=old_code,
                    new_code=new_code,
                    message=(
                        f"Sandbox validation failed after {self.max_fix_loops} attempts. "
                        f"Last error: {test.error}\n\nLast output:\n{test.output or ''}"
                    ),
                )
            # Ask the LLM to fix its own code.
            new_code = self._self_correct(
                admin_command,
                snapshot_text,
                new_code,
                test.error or "unknown error",
                test.output or "",
                attempt,
            )

        return DiffResult(
            file_path=target_rel_path,
            old_code=old_code,
            new_code=new_code,
            message="Sandbox validation passed.",
        )

    # ------------------------------------------------------------------ #
    # Testing
    # ------------------------------------------------------------------ #
    def _test_code(self, rel_path: str, code: str) -> TestResult:
        language = _detect_language(rel_path)

        if language == "python":
            return self._test_python(code)
        if language in {"javascript", "jsx", "typescript", "tsx"}:
            return self._test_js(rel_path, code)
        if language == "html":
            return self._test_html(code)
        # Unknown language — basic sanity check only.
        return TestResult(ok=True)

    def _test_python(self, code: str) -> TestResult:
        try:
            ast.parse(code)
        except SyntaxError as exc:
            line = exc.lineno or 0
            offset = exc.offset or 0
            return TestResult(
                ok=False,
                error=f"Python syntax error at line {line}, offset {offset}: {exc.msg}",
                output=code,
            )
        # Also try compiling to bytecode for deeper validation.
        try:
            compile(code, "<self_writer_generated>", "exec")
        except SyntaxError as exc:
            return TestResult(
                ok=False,
                error=f"Python compile error: {exc.msg}",
                output=code,
            )
        return TestResult(ok=True)

    def _test_js(self, rel_path: str, code: str) -> TestResult:
        # Lightweight structural sanity: balanced braces/parens and no obvious
        # dangling tokens. A full build is attempted if a build command exists.
        problems = self._balance_check(code)
        if problems:
            return TestResult(ok=False, error=problems, output=code)

        if self.build_cmd:
            return self._run_build(rel_path, code)
        if self.typecheck_cmd:
            return self._run_typecheck(rel_path, code)
        return TestResult(ok=True)

    def _test_html(self, code: str) -> TestResult:
        # Basic tag balance check.
        open_tags = re.findall(r"<([a-zA-Z0-9]+)[^>/]*>", code)
        close_tags = re.findall(r"</([a-zA-Z0-9]+)>", code)
        void_elements = {
            "area", "base", "br", "col", "embed", "hr", "img", "input",
            "link", "meta", "param", "source", "track", "wbr",
        }
        from collections import Counter
        open_counter = Counter(t for t in open_tags if t not in void_elements)
        close_counter = Counter(close_tags)
        diff = open_counter - close_counter
        if diff:
            missing = ", ".join(f"{k} x{v}" for k, v in diff.items())
            return TestResult(
                ok=False,
                error=f"Unclosed HTML tags: {missing}",
                output=code,
            )
        return TestResult(ok=True)

    def _balance_check(self, code: str) -> Optional[str]:
        pairs = {")": "(", "]": "[", "}": "{"}
        stack: list[str] = []
        in_string: Optional[str] = None
        escape = False
        for ch in code:
            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == in_string:
                    in_string = None
                continue
            if ch in ('"', "'", "`"):
                in_string = ch
                continue
            if ch in pairs.values():
                stack.append(ch)
            elif ch in pairs:
                if not stack or stack[-1] != pairs[ch]:
                    return f"Unbalanced bracket: unexpected '{ch}'"
                stack.pop()
        if stack:
            return f"Unclosed brackets: {''.join(stack)}"
        return None

    def _run_build(self, rel_path: str, code: str) -> TestResult:
        """Write code to a temp location and run the build command."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp) / Path(rel_path).name
            tmp_path.write_text(code, encoding="utf-8")
            try:
                proc = subprocess.run(
                    self.build_cmd,
                    cwd=str(tmp_path.parent),
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
            except FileNotFoundError:
                return TestResult(ok=True)  # build tool not installed — skip
            except subprocess.TimeoutExpired:
                return TestResult(ok=False, error="Build timed out.", output=code)
            if proc.returncode != 0:
                return TestResult(
                    ok=False,
                    error=proc.stderr.strip() or proc.stdout.strip() or "Build failed.",
                    output=code,
                )
        return TestResult(ok=True)

    def _run_typecheck(self, rel_path: str, code: str) -> TestResult:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp) / Path(rel_path).name
            tmp_path.write_text(code, encoding="utf-8")
            try:
                proc = subprocess.run(
                    self.typecheck_cmd,
                    cwd=str(tmp_path.parent),
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
            except FileNotFoundError:
                return TestResult(ok=True)
            except subprocess.TimeoutExpired:
                return TestResult(ok=False, error="Typecheck timed out.", output=code)
            if proc.returncode != 0:
                return TestResult(
                    ok=False,
                    error=proc.stderr.strip() or proc.stdout.strip() or "Typecheck failed.",
                    output=code,
                )
        return TestResult(ok=True)

    # ------------------------------------------------------------------ #
    # Self-correction
    # ------------------------------------------------------------------ #
    def _self_correct(
        self,
        admin_command: str,
        snapshot_text: str,
        broken_code: str,
        error: str,
        output: str,
        attempt: int,
    ) -> str:
        if self.model is None:
            return broken_code  # cannot self-correct without a model

        messages = [
            ChatMessage(
                "system",
                "You are an expert software engineer fixing code that failed validation. "
                "Return ONLY the corrected, complete file contents — no markdown fences, "
                "no explanations.",
            ),
            ChatMessage(
                "user",
                (
                    "Task: {command}\n\n"
                    "Codebase context:\n{snapshot}\n\n"
                    "Your previous code failed validation (attempt {attempt}/{max_loops}).\n"
                    "Error: {error}\n\n"
                    "Validator output:\n{output}\n\n"
                    "Here is the broken code:\n```\n{code}\n```\n\n"
                    "Rewrite the full corrected file contents now.",
                ).format(
                    command=admin_command,
                    snapshot=snapshot_text,
                    attempt=attempt,
                    max_loops=self.max_fix_loops,
                    error=error,
                    output=output,
                    code=broken_code,
                ),
            ),
        ]
        return self.model.chat(messages, temperature=0.1)

    # ------------------------------------------------------------------ #
    # Backup + apply
    # ------------------------------------------------------------------ #
    def backup(self, rel_path: str, code: str) -> str:
        """Back up existing file content and return the backup path."""
        target = self.root / rel_path
        if not target.is_file() or code is None:
            # Nothing to back up; write a placeholder so the diff is still valid.
            placeholder = self.backup_dir / f"{rel_path.replace(os.sep, '__')}.missing"
            placeholder.write_text("", encoding="utf-8")
            return str(placeholder)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        safe_name = rel_path.replace(os.sep, "__")
        backup_path = self.backup_dir / f"{timestamp}__{safe_name}"
        backup_path.write_text(code, encoding="utf-8")
        return str(backup_path)

    def apply(self, diff: DiffResult) -> bool:
        """Apply an approved diff: back up the old file, write the new one."""
        if not diff.approved:
            return False
        target = self.root / diff.file_path
        target.parent.mkdir(parents=True, exist_ok=True)

        # Back up old content first (if any).
        if diff.old_code is not None:
            diff.backup_path = self.backup(diff.file_path, diff.old_code)

        target.write_text(diff.new_code, encoding="utf-8")
        diff.applied = True
        return True


def _detect_language(rel_path: str) -> str:
    ext = Path(rel_path).suffix.lower()
    mapping = {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "jsx",
        ".ts": "typescript",
        ".tsx": "tsx",
        ".html": "html",
        ".css": "css",
        ".json": "json",
        ".toml": "toml",
        ".env": "env",
        ".md": "markdown",
    }
    return mapping.get(ext, "text")
