"""FastAPI routes for the Orion Self-Writer admin module.

Endpoints:
    POST   /api/self-write/status   — model availability & sandbox state
    POST   /api/self-write/write    — generate + validate code from a command
    POST   /api/self-write/apply    — apply an approved diff (hot-reload)
    GET    /api/self-write/backups  — list available backups
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from orion.core.self_writer import SelfWriter, WriteResult

router = APIRouter(prefix="/api/self-write", tags=["self-writer"])

PROJECT_ROOT = Path(__file__).resolve().parents[3]
BACKUP_DIR = PROJECT_ROOT / "orion" / "backups"

# Single engine instance for the lifetime of the app (keeps the codebase scan
# cached across requests within one process).
_writer: Optional[SelfWriter] = None


def _get_writer() -> SelfWriter:
    global _writer
    if _writer is None:
        _writer = SelfWriter(root=PROJECT_ROOT)
    return _writer


class StatusResponse(BaseModel):
    ok: bool
    model: dict
    max_fix_loops: int
    backup_dir: str


class WriteRequest(BaseModel):
    command: str = Field(min_length=1, max_length=4000, description="Admin instruction")
    target: Optional[str] = Field(
        default=None,
        description="Optional target file path (relative to project root)",
    )


class WriteResponse(BaseModel):
    success: bool
    message: str
    diff: Optional[dict] = None
    applied: bool = False
    backup_path: Optional[str] = None
    model_used: Optional[str] = None


class ApplyRequest(BaseModel):
    file_path: str = Field(min_length=1)
    old_code: str
    new_code: str = Field(min_length=1)


class ApplyResponse(BaseModel):
    success: bool
    message: str
    applied: bool = False
    backup_path: Optional[str] = None


class BackupItem(BaseModel):
    name: str
    path: str
    size: int
    created_at: str


@router.post("/status", response_model=StatusResponse)
def self_write_status() -> StatusResponse:
    writer = _get_writer()
    status = writer.status()
    return StatusResponse(
        ok=True,
        model=status["model"],
        max_fix_loops=status["max_fix_loops"],
        backup_dir=status["backup_dir"],
    )


@router.post("/write", response_model=WriteResponse)
def self_write(payload: WriteRequest) -> WriteResponse:
    writer = _get_writer()
    result = writer.write_code(payload.command, payload.target)
    return WriteResponse(
        success=result.success,
        message=result.message,
        diff=result.diff,
        applied=result.applied,
        backup_path=result.backup_path,
        model_used=result.model_used,
    )


@router.post("/apply", response_model=ApplyResponse)
def self_write_apply(payload: ApplyRequest) -> ApplyResponse:
    writer = _get_writer()
    diff_dict = {
        "file_path": payload.file_path,
        "old_code": payload.old_code,
        "new_code": payload.new_code,
    }
    result = writer.approve_and_apply(diff_dict)
    return ApplyResponse(
        success=result.success,
        message=result.message,
        applied=result.applied,
        backup_path=result.backup_path,
    )


@router.get("/backups", response_model=list[BackupItem])
def self_write_backups() -> list[BackupItem]:
    if not BACKUP_DIR.is_dir():
        return []
    items: list[BackupItem] = []
    for p in sorted(BACKUP_DIR.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if p.is_file():
            stat = p.stat()
            items.append(
                BackupItem(
                    name=p.name,
                    path=str(p),
                    size=stat.st_size,
                    created_at=__import__("datetime").datetime.fromtimestamp(
                        stat.st_mtime
                    ).isoformat(),
                )
            )
    return items


@router.delete("/backups/{name}")
def self_write_delete_backup(name: str) -> dict:
    target = BACKUP_DIR / name
    if not target.is_file():
        raise HTTPException(status_code=404, detail="Backup not found")
    # Safety: only allow files directly inside the backup dir.
    if target.resolve().parent != BACKUP_DIR.resolve():
        raise HTTPException(status_code=403, detail="Invalid backup path")
    target.unlink()
    return {"deleted": True, "name": name}
