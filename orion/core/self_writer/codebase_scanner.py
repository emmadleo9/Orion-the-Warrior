"""Orion Self-Writer — codebase scanner.

Reads the current Orion source tree so the LLM understands what exists before
generating or rewriting code. Only source files are indexed (not .venv, node_modules,
build artifacts, databases, or cached data).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# Directories/files to skip when scanning.
SKIP_DIRS = {
    ".venv",
    "venv",
    "__pycache__",
    ".git",
    "node_modules",
    ".pytest_cache",
    ".next",
    "dist",
    "build",
    ".mypy_cache",
    ".ruff_cache",
    "backups",  # never scan backups
}

SKIP_FILES = {
    ".DS_Store",
    "thumbs.db",
}

# Source extensions Orion cares about (Python + frontend + config).
SOURCE_EXTENSIONS = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".html",
    ".css",
    ".json",
    ".toml",
    ".env",
    ".md",
}

MAX_FILE_BYTES = 200_000  # skip enormous files


@dataclass
class SourceFile:
    path: str
    rel_path: str
    size: int
    language: str
    content: Optional[str] = None


@dataclass
class CodebaseSnapshot:
    root: str
    files: list[SourceFile] = field(default_factory=list)
    structure: str = ""
    total_bytes: int = 0

    @property
    def python_files(self) -> list[SourceFile]:
        return [f for f in self.files if f.language == "python"]

    @property
    def js_files(self) -> list[SourceFile]:
        return [f for f in self.files if f.language in {"javascript", "jsx", "typescript", "tsx"}]

    @property
    def html_files(self) -> list[SourceFile]:
        return [f for f in self.files if f.language == "html"]

    def find(self, rel_path: str) -> Optional[SourceFile]:
        for f in self.files:
            if f.rel_path == rel_path:
                return f
        return None


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


def scan_codebase(root: str | Path, include_content: bool = True) -> CodebaseSnapshot:
    """Walk ``root`` and return a snapshot of source files.

    If ``include_content`` is True, each file's contents are read so the LLM can
    understand them. Very large files (>200 KB) are truncated/skipped to keep
    the context window manageable.
    """
    root_path = Path(root).resolve()
    snapshot = CodebaseSnapshot(root=str(root_path))
    tree_lines: list[str] = [f"{root_path.name}/"]

    for dirpath, dirnames, filenames in os.walk(root_path):
        # Prune skip directories in-place so os.walk does not descend into them.
        dirnames[:] = [
            d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")
        ]
        dirnames.sort()

        rel_dir = Path(dirpath).relative_to(root_path)
        if rel_dir != Path("."):
            tree_lines.append(f"{rel_dir}/")

        for filename in sorted(filenames):
            if filename in SKIP_FILES:
                continue
            if Path(filename).suffix.lower() not in SOURCE_EXTENSIONS:
                continue

            full_path = Path(dirpath) / filename
            rel_path = str(full_path.relative_to(root_path))
            try:
                size = full_path.stat().st_size
            except OSError:
                continue

            language = _detect_language(rel_path)
            content: Optional[str] = None
            if include_content:
                if size > MAX_FILE_BYTES:
                    content = f"[FILE TOO LARGE ({size} bytes) — truncated]"
                    # Still try to read the head for context.
                    try:
                        content += "\n" + full_path.read_text(encoding="utf-8", errors="replace")[:20_000]
                    except OSError:
                        pass
                else:
                    try:
                        content = full_path.read_text(encoding="utf-8", errors="replace")
                    except OSError:
                        content = None

            snapshot.files.append(
                SourceFile(
                    path=str(full_path),
                    rel_path=rel_path,
                    size=size,
                    language=language,
                    content=content,
                )
            )
            snapshot.total_bytes += size

    snapshot.structure = "\n".join(tree_lines)
    return snapshot


def render_snapshot_for_llm(snapshot: CodebaseSnapshot, max_files: int = 60) -> str:
    """Render the snapshot as a text block the LLM can read in its context."""
    lines: list[str] = []
    lines.append("=== ORION CODEBASE STRUCTURE ===")
    lines.append(snapshot.structure)
    lines.append("")
    lines.append(f"Total source files: {len(snapshot.files)}")
    lines.append(f"Total bytes: {snapshot.total_bytes:,}")
    lines.append("")
    lines.append("=== FILES ===")

    # Prioritize the most relevant files first (app entry, ai, routes, static).
    priority = ["orion_app/main.py", "orion_app/ai.py", "orion_app/config.py"]
    ordered = sorted(
        snapshot.files,
        key=lambda f: (0 if f.rel_path in priority else 1, f.rel_path),
    )

    shown = 0
    for f in ordered:
        if shown >= max_files:
            lines.append(f"[... {len(ordered) - shown} more files omitted ...]")
            break
        lines.append(f"--- {f.rel_path} ({f.language}, {f.size} bytes) ---")
        if f.content is not None:
            lines.append(f.content)
        else:
            lines.append("[unreadable]")
        lines.append("")
        shown += 1

    return "\n".join(lines)
