"""FR-47 — upload recordings (multi-file, per-file result)."""

from __future__ import annotations

from fastapi import APIRouter, UploadFile

router = APIRouter(prefix="/upload", tags=["upload"])


@router.get("")
async def upload_page() -> dict:
    raise NotImplementedError("render the drag-and-drop upload page")


@router.post("")
async def do_upload(files: list[UploadFile]) -> dict:
    """Accept each file via ``deps.intake.accept_upload``; return per-file
    ``accepted | duplicate | rejected(reason)`` (FR-47, FR-1)."""
    raise NotImplementedError(
        "validate format/size against config.ingest; for each file "
        "deps.intake.accept_upload(filename=..., content=await f.read()); "
        "catch DuplicateRecording -> 'duplicate'"
    )
