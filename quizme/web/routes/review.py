"""FR-49 — Review Queue UI (FR-21..23, FR-31)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body

from quizme.application import review_queue
from quizme.web.deps import get_deps

router = APIRouter(prefix="/review", tags=["review"])


@router.get("")
async def queue() -> dict[str, Any]:
    return {"items": review_queue.list_open(get_deps())}


@router.post("/{item_id}/resolve")
async def resolve(item_id: str, resolution: str, payload: dict[str, Any] | None = Body(default=None)) -> dict[str, str]:
    review_queue.resolve(get_deps(), item_id=item_id, resolution=resolution, payload=payload)
    return {"status": "resolved"}
