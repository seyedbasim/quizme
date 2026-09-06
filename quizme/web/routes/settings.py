"""FR-52 — retention view (FR-32) + spend (FR-38) + user settings (FR-28)."""

from __future__ import annotations

from collections import Counter
from typing import Any

from fastapi import APIRouter

from quizme.domain.selection import strength_bucket
from quizme.web.deps import get_deps

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/retention")
async def retention() -> dict[str, Any]:
    deps = get_deps()
    now = deps.clock.now()
    kus = {k.id: k for k in deps.store.load_kus().values() if k.quiz_eligible}
    labels = deps.store.topic_labels(sorted({t for k in kus.values() for t in k.topic_ids}))
    per_topic: dict[str, Counter] = {}
    for card in deps.store.all_cards():
        ku = kus.get(card.ku_id)
        if ku is None:
            continue
        bucket = strength_bucket(card, now=now)
        for tid in ku.topic_ids:
            per_topic.setdefault(tid, Counter())[bucket] += 1
    return {"topics": [{"topic": labels.get(tid, tid), **dict(counts)} for tid, counts in per_topic.items()]}


@router.get("/spend")
async def spend() -> dict[str, Any]:
    deps = get_deps()
    now = deps.clock.now()
    mtd = deps.store.month_spend_usd(year=now.year, month=now.month)
    return {
        "month_to_date_usd": round(mtd, 4),
        "projected_month_end_usd": round(deps.spend.projected_month_end_usd(), 4),
        "monthly_credit_usd": deps.config.budget.monthly_credit_usd,
        "throttled": deps.spend.is_throttled(),
    }


@router.get("")
async def get_settings() -> dict[str, Any]:
    q = get_deps().config.quiz
    return {
        "quiz_time_local": q.send_time_local,
        "max_questions_per_day": q.max_questions_per_day,
        "retrievability_threshold": q.retrievability_threshold,
    }
