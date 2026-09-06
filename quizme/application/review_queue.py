"""Review Queue service (FR-21..FR-23).

Resolving records a user-attributed KUOperation (AD-3) and never row-deletes a KU.
"""

from __future__ import annotations

from typing import Any

from quizme.application.deps import Deps
from quizme.domain.errors import QuizmeError
from quizme.domain.ids import new_id
from quizme.domain.ku import Actor, KnowledgeUnit, KUOperation, KUOpType, KUStatus, ku_payload
from quizme.domain.quiz import GradeValue
from quizme.domain.scheduling import Card, Rating, review

ITEM_KINDS = (
    "contradiction",
    "uncertain_extraction",
    "uncertain_followup",
    "disputed_grade",
    "proposed_merge",
)

_RATING = {GradeValue.CORRECT: Rating.GOOD, GradeValue.PARTIAL: Rating.HARD, GradeValue.MISSED: Rating.AGAIN}


def list_open(deps: Deps) -> list[dict[str, Any]]:
    kus = deps.store.load_kus()
    out = []
    for item in deps.store.list_review_items(status="open"):
        detail = [{"id": k, "canonical": kus[k].canonical} for k in item["ku_ids"] if k in kus]
        out.append({**item, "kus": detail})
    return out


def resolve(deps: Deps, *, item_id: str, resolution: str, payload: dict[str, Any] | None = None) -> None:
    item = deps.store.get_review_item(item_id)
    if item is None or item["status"] != "open":
        raise QuizmeError(f"review item {item_id} not open")
    payload = payload or {}
    now = deps.clock.now()
    ku_ids: list[str] = item["ku_ids"]

    def user_op(op_type: KUOpType, ins: tuple[str, ...], p: dict[str, Any], why: str) -> None:
        deps.store.append_ops(
            [
                KUOperation(
                    op_id=new_id(),
                    ts=now,
                    actor=Actor.USER,
                    type=op_type,
                    ku_ids_in=ins,
                    payload=p,
                    rationale=why,
                )
            ]
        )

    kind = item["kind"]

    if kind == "contradiction":
        a, b = (ku_ids + ["", ""])[:2]
        if resolution == "keep_a":
            user_op(KUOpType.ARCHIVE, (b,), {"ku_id": b}, "contradiction: kept A")
        elif resolution == "keep_b":
            user_op(KUOpType.ARCHIVE, (a,), {"ku_id": a}, "contradiction: kept B")
        elif resolution != "dismiss":
            raise QuizmeError(f"bad contradiction resolution: {resolution}")

    elif kind == "uncertain_extraction":
        ku_id = ku_ids[0]
        ku = deps.store.load_kus().get(ku_id)
        if ku and resolution == "confirm":
            active = KnowledgeUnit(
                id=ku.id,
                canonical=ku.canonical,
                topic_ids=ku.topic_ids,
                sources=ku.sources,
                alt_phrasings=ku.alt_phrasings,
                created_at=ku.created_at,
                updated_at=now,
                status=KUStatus.ACTIVE,
            )
            user_op(KUOpType.CREATE, (ku_id,), {"ku": ku_payload(active)}, "confirmed uncertain extraction")
        elif resolution == "reject":
            user_op(KUOpType.ARCHIVE, (ku_id,), {"ku_id": ku_id}, "rejected uncertain extraction")

    elif kind == "proposed_merge":
        a, b = (ku_ids + ["", ""])[:2]
        kus = deps.store.load_kus()
        if resolution == "merge" and a in kus and b in kus:
            user_op(
                KUOpType.MERGE,
                (b, a),
                {"survivor_id": b, "loser_id": a, "canonical": kus[b].canonical},
                "user confirmed proposed merge",
            )

    elif kind == "disputed_grade" and resolution == "overturn":
        corrected = GradeValue(payload["value"])
        qid = item["context"]["question_id"]
        deps.store.record_grade(
            {
                "question_id": qid,
                "value": corrected.value,
                "rationale": "overturned on review",
                "model": "user",
                "prompt_version": "review",
                "disputed": False,
            }
        )
        q = deps.store.get_question(qid)
        if q:
            card = deps.store.get_card(q["ku_id"]) or Card.new(q["ku_id"], now=now)
            deps.store.upsert_card(review(card, _RATING[corrected], now=now))

    deps.store.resolve_review_item(item_id, resolution=resolution)
