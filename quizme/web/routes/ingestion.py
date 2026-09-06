"""FR-48 — ingestion status & run history."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/ingestion", tags=["ingestion"])


@router.get("")
async def status_page() -> dict:
    raise NotImplementedError("in-flight + recent Recordings: transcription state, counts, errors")


@router.post("/{recording_id}/retry")
async def retry(recording_id: str) -> dict:
    raise NotImplementedError("re-enqueue a parked Recording (FR-36)")
