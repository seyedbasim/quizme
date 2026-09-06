"""FR-52 — retention view (FR-32) + user settings (FR-28, FR-38 budget)."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/retention")
async def retention() -> dict:
    raise NotImplementedError(
        "per-Topic strong/ok/weak/overdue counts from domain.selection.strength_bucket over store.all_cards()"
    )


@router.get("/spend")
async def spend() -> dict:
    raise NotImplementedError("month-to-date + projected month-end, broken down by component (FR-38)")


@router.get("")
async def get_settings() -> dict:
    raise NotImplementedError("quiz time, daily cap, thresholds, monthly budget")


@router.post("")
async def update_settings() -> dict:
    raise NotImplementedError("persist to a settings table; changes take effect per the owning FR")
