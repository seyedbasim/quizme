"""FR-50 — knowledge-base browsing (FR-19) + manual corrections (FR-33..35)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException

from quizme.domain.ids import new_id
from quizme.domain.ku import Actor, KUOperation, KUOpType
from quizme.web.deps import get_deps

router = APIRouter(prefix="/kb", tags=["knowledge-base"])


@router.get("/topics")
async def topics() -> dict[str, Any]:
    deps = get_deps()
    kus = [k for k in deps.store.load_kus().values() if k.quiz_eligible]
    tids = sorted({t for k in kus for t in k.topic_ids})
    labels = deps.store.topic_labels(tids)
    out = []
    for tid in tids:
        note = deps.store.get_topic_note(tid)
        out.append(
            {
                "id": tid,
                "label": labels.get(tid, tid),
                "ku_count": sum(1 for k in kus if tid in k.topic_ids),
                "note": note["markdown"] if note else None,
            }
        )
    return {"topics": out}


@router.get("/search")
async def search(q: str) -> dict[str, Any]:
    deps = get_deps()
    ql = q.lower()
    hits = [
        {
            "id": k.id,
            "canonical": k.canonical,
            "alt_phrasings": list(k.alt_phrasings),
            "sources": [{"recording_id": s.recording_id, "start": s.start, "end": s.end} for s in k.sources],
        }
        for k in deps.store.load_kus().values()
        if k.quiz_eligible and (ql in k.canonical.lower() or any(ql in a.lower() for a in k.alt_phrasings))
    ]
    return {"hits": hits[:50]}


@router.post("/ku/{ku_id}/edit")
async def edit_ku(
    ku_id: str,
    canonical: str | None = None,
    topic_labels: list[str] | None = Body(default=None),
) -> dict[str, str]:
    deps = get_deps()
    ku = deps.store.load_kus().get(ku_id)
    if ku is None:
        raise HTTPException(404)
    now = deps.clock.now()
    if canonical:
        _op(deps, KUOpType.EDIT, (ku_id,), {"ku_id": ku_id, "canonical": canonical}, now)
    if topic_labels is not None:
        tids = [deps.store.get_or_create_topic(t) for t in topic_labels]
        _op(deps, KUOpType.RETOPIC, (ku_id,), {"ku_id": ku_id, "topic_ids": tids}, now)
    return {"status": "edited"}


@router.post("/ku/{ku_id}/archive")
async def archive_ku(ku_id: str) -> dict[str, str]:
    deps = get_deps()
    _op(deps, KUOpType.ARCHIVE, (ku_id,), {"ku_id": ku_id}, deps.clock.now())
    return {"status": "archived"}


def _op(deps: Any, t: KUOpType, ins: tuple[str, ...], payload: dict[str, Any], now: Any) -> None:
    op = KUOperation(
        op_id=new_id(), ts=now, actor=Actor.USER, type=t, ku_ids_in=ins, payload=payload, rationale="web edit"
    )
    deps.store.append_ops([op])
