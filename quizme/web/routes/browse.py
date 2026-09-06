"""FR-50 — knowledge-base browsing (FR-19) + manual corrections (FR-33..35)."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/kb", tags=["knowledge-base"])


@router.get("/topics")
async def topics() -> dict:
    raise NotImplementedError("list Topics + their regenerated Topic Notes")


@router.get("/search")
async def search(q: str) -> dict:
    raise NotImplementedError("search canonical + alt_phrasings; each hit exposes Sources + audio span")


@router.get("/ku/{ku_id}")
async def ku_detail(ku_id: str) -> dict:
    raise NotImplementedError("KU with Sources, audio playback links, KU Operation history")


@router.post("/ku/{ku_id}/edit")
async def edit_ku(ku_id: str) -> dict:
    raise NotImplementedError("append a user-actor EDIT / RETOPIC KUOperation (FR-33)")


@router.post("/ku/{ku_id}/archive")
async def archive_ku(ku_id: str) -> dict:
    raise NotImplementedError("append a user-actor ARCHIVE KUOperation (FR-34)")
