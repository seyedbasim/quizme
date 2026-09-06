"""FR-49 — Review Queue UI (FR-21..23, FR-31)."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/review", tags=["review"])


@router.get("")
async def queue() -> dict:
    raise NotImplementedError("application.review_queue.list_open(deps)")


@router.post("/{item_id}/resolve")
async def resolve(item_id: str, resolution: str) -> dict:
    raise NotImplementedError("application.review_queue.resolve(deps, item_id=..., resolution=..., payload=...)")
