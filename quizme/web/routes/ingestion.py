"""FR-48 — ingestion status & run history."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from quizme.web.deps import get_deps

router = APIRouter(prefix="/ingestion", tags=["ingestion"])


@router.get("")
async def status_page() -> dict[str, Any]:
    return {"recordings": get_deps().store.ingestion_status()}


@router.post("/{recording_id}/retry")
async def retry(recording_id: str) -> dict[str, str]:
    get_deps().intake.reenqueue(recording_id)
    return {"status": "re-enqueued"}
