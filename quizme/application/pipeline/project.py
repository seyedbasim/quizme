"""Stage 5 — project the operation log into the live KB (FR-17).

``domain.ku.fold`` is the source of truth (AD-3); this stage refreshes the
``knowledge_unit`` materialised table for fast browsing / retrieval, gives every
new quiz-eligible KU an FSRS Card, and reports which Topics changed so
``notes.run`` knows what to regenerate.

Cheap and fully idempotent (all upserts) — safe to run every time.
"""

from __future__ import annotations

from typing import Any

from quizme.application.deps import Deps
from quizme.domain.ku import KUStatus
from quizme.domain.scheduling import Card

STAGE = "project"
STAGE_VERSION = "2026-09-06.1"


def run(recording_id: str, deps: Deps) -> dict[str, Any]:
    kus = deps.store.load_kus()
    deps.store.upsert_ku_projection(list(kus.values()))

    now = deps.clock.now()
    new_cards = 0
    for ku in kus.values():
        if ku.status is KUStatus.ACTIVE and deps.store.get_card(ku.id) is None:
            deps.store.upsert_card(Card.new(ku.id, now=now))
            new_cards += 1

    changed_topics = sorted({t for ku in kus.values() if ku.status is KUStatus.ACTIVE for t in ku.topic_ids})
    return {
        "live_kus": sum(1 for k in kus.values() if k.quiz_eligible),
        "new_cards": new_cards,
        "changed_topics": changed_topics,
    }
