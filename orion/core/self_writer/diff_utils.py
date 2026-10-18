"""Orion Self-Writer — diff utilities.

Produces a human-readable unified diff between old and new code so the admin
can review exactly what will change before approving.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass


@dataclass
class FileDiff:
    file_path: str
    old_code: str | None
    new_code: str
    unified_diff: str
    added_lines: int
    removed_lines: int
    is_new_file: bool


def build_diff(file_path: str, old_code: str | None, new_code: str) -> FileDiff:
    old_lines = (old_code or "").splitlines(keepends=True)
    new_lines = new_code.splitlines(keepends=True)

    diff = list(
        difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
            lineterm="",
        )
    )
    unified = "\n".join(diff) if diff else "(no changes)"

    added = sum(1 for line in diff if line.startswith("+") and not line.startswith("+++"))
    removed = sum(1 for line in diff if line.startswith("-") and not line.startswith("---"))

    return FileDiff(
        file_path=file_path,
        old_code=old_code,
        new_code=new_code,
        unified_diff=unified,
        added_lines=added,
        removed_lines=removed,
        is_new_file=old_code is None,
    )


def format_diff_for_ui(diff: FileDiff) -> str:
    """Return a UI-friendly summary string."""
    if diff.is_new_file:
        return f"NEW FILE: {diff.file_path} (+{diff.added_lines} lines)"
    return (
        f"{diff.file_path} "
        f"(+{diff.added_lines}/-{diff.removed_lines} lines)"
    )
