"""FR-47 — upload recordings (multi-file, per-file result)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, UploadFile

from quizme.domain.errors import DuplicateRecording
from quizme.web.deps import get_deps

router = APIRouter(prefix="/upload", tags=["upload"])


@router.post("")
async def do_upload(files: list[UploadFile]) -> dict[str, Any]:
    deps = get_deps()
    cfg = deps.config.ingest
    results = []
    for f in files:
        ext = (f.filename or "").rsplit(".", 1)[-1].lower()
        content = await f.read()
        if ext not in cfg.allowed_formats:
            results.append({"filename": f.filename, "status": "rejected", "reason": f"format .{ext} not allowed"})
            continue
        if len(content) > cfg.max_file_mb * 1024 * 1024:
            results.append({"filename": f.filename, "status": "rejected", "reason": "over size limit"})
            continue
        try:
            accepted = deps.intake.accept_upload(filename=f.filename or "upload", content=content)
            results.append({"filename": f.filename, "status": "accepted", "recording_id": accepted.recording_id})
        except DuplicateRecording as dup:
            results.append({"filename": f.filename, "status": "duplicate", "recording_id": dup.recording_id})
    return {"results": results}
