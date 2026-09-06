"""FR-51 — To-Do (Action Items) UI (FR-39..45)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from quizme.application import action_items
from quizme.web.deps import get_deps

router = APIRouter(prefix="/todo", tags=["action-items"])


@router.get("")
async def list_items(status: str | None = "open", origin: str | None = None) -> dict[str, Any]:
    return {"items": action_items.list_items(get_deps(), status=status, origin=origin)}


@router.post("/{dedup_key}/done")
async def mark_done(dedup_key: str) -> dict[str, str]:
    action_items.set_status(get_deps(), dedup_key=dedup_key, how="done")
    return {"status": "done"}


@router.post("/{dedup_key}/dismiss")
async def dismiss(dedup_key: str) -> dict[str, str]:
    action_items.set_status(get_deps(), dedup_key=dedup_key, how="dismissed")
    return {"status": "dismissed"}


@router.post("/{dedup_key}/snooze")
async def snooze(dedup_key: str, until: str) -> dict[str, str]:
    action_items.set_status(get_deps(), dedup_key=dedup_key, how="snooze", until=until)
    return {"status": "snoozed"}
