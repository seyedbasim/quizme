"""Action Item service (FR-39..FR-45) — the application-side wrapper over
:mod:`quizme.domain.action_items`.

The domain module holds the pure lifecycle/dedup logic; this module persists it
and wires the loop-closing signals (AD-12):

* Revisit item on a failed grade (FR-41) — called from ``application.quiz``.
* ``correct``x2 -> auto-resolve the Revisit item (FR-45).
* "possibly addressed" flag on a Follow-up when a later Recording adds KUs to its
  Topic (FR-45, second half — deferred to v1.1).
"""

from __future__ import annotations

from datetime import datetime

from quizme.application.deps import Deps
from quizme.domain.action_items import Origin, revisit_key, upsert


def raise_revisit(deps: Deps, *, ku_id: str, topic_id: str | None, ku_canonical: str, model_answer: str) -> None:
    now: datetime = deps.clock.now()
    key = revisit_key(ku_id)
    existing = deps.store.get_action_item(key)
    item = upsert(
        existing,
        origin=Origin.REVISIT,
        dedup_key=key,
        trigger_text=f"Missed in quiz. Model answer: {model_answer}",
        now=now,
        ku_id=ku_id,
        topic_id=topic_id,
    )
    deps.store.upsert_action_item(item)


def maybe_auto_resolve_revisit(deps: Deps, *, ku_id: str, consecutive_correct: int) -> None:
    if consecutive_correct < 2:
        return
    raise NotImplementedError(
        "maybe_auto_resolve_revisit: item = store.get_action_item(revisit_key(ku_id)); "
        "if item and item.status == OPEN -> domain.action_items.resolve(item, how='auto'); "
        "store.upsert_action_item(...)  (FR-45)"
    )


def list_items(deps: Deps, *, status: str | None = None, origin: str | None = None) -> list[dict]:
    raise NotImplementedError("list_items: grouped by Topic, overdue/snoozed-due highlighted (FR-43)")
