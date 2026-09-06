"""FR-51 — To-Do (Action Items) UI (FR-39..45)."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/todo", tags=["action-items"])


@router.get("")
async def list_items(status: str | None = None, origin: str | None = None) -> dict:
    raise NotImplementedError("application.action_items.list_items(deps, status=..., origin=...) grouped by Topic")


@router.post("/{item_id}/done")
async def mark_done(item_id: str) -> dict:
    raise NotImplementedError("domain.action_items.resolve(item, how='done')")


@router.post("/{item_id}/snooze")
async def snooze(item_id: str, until: str) -> dict:
    raise NotImplementedError("domain.action_items.snooze(item, until=parse(until))")


@router.post("/{item_id}/dismiss")
async def dismiss(item_id: str) -> dict:
    raise NotImplementedError("domain.action_items.resolve(item, how='dismissed')")
