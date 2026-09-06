"""Action Item service (FR-39..FR-45) — the application-side wrapper over
:mod:`quizme.domain.action_items`.

The domain module holds the pure lifecycle/dedup logic; this module persists it
and wires the loop-closing signals (AD-12):

* Revisit item on a failed grade (FR-41) — from ``application.quiz``.
* ``correct``x2 -> auto-resolve the Revisit item (FR-45).
* "possibly addressed" flag on a Follow-up when a later Recording adds KUs to its
  Topic (FR-45, second half — deferred to v1.1).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from quizme.application.deps import Deps
from quizme.domain.action_items import AIStatus, Origin, resolve, revisit_key, snooze, upsert


def raise_revisit(deps: Deps, *, ku_id: str, topic_id: str | None, ku_canonical: str, model_answer: str) -> None:
    now = deps.clock.now()
    key = revisit_key(ku_id)
    item = upsert(
        deps.store.get_action_item(key),
        origin=Origin.REVISIT,
        dedup_key=key,
        trigger_text=f"Missed: {ku_canonical}\nModel answer: {model_answer}",
        now=now,
        ku_id=ku_id,
        topic_id=topic_id,
    )
    deps.store.upsert_action_item(item)


def auto_resolve_revisit(deps: Deps, *, ku_id: str) -> None:
    item = deps.store.get_action_item(revisit_key(ku_id))
    if item and item.status is AIStatus.OPEN:
        deps.store.upsert_action_item(resolve(item, now=deps.clock.now(), how="auto"))


def set_status(deps: Deps, *, dedup_key: str, how: str, until: str | None = None) -> None:
    """From the To-Do UI (FR-44). ``how`` in {done, dismissed, snooze}."""
    item = deps.store.get_action_item(dedup_key)
    if item is None:
        return
    now = deps.clock.now()
    if how == "snooze":
        when = datetime.fromisoformat(until) if until else now
        deps.store.upsert_action_item(snooze(item, until=when, now=now))
    else:
        deps.store.upsert_action_item(resolve(item, now=now, how=how))


def list_items(deps: Deps, *, status: str | None = "open", origin: str | None = None) -> list[dict[str, Any]]:
    items = deps.store.list_action_items(status=status, origin=origin)
    labels = deps.store.topic_labels([i.topic_id for i in items if i.topic_id])
    now = deps.clock.now()
    return [
        {
            "id": i.id,
            "dedup_key": i.dedup_key,
            "origin": i.origin.value,
            "status": i.status.value,
            "topic": labels.get(i.topic_id or "", "(no topic)"),
            "trigger_text": i.trigger_text,
            "trigger_count": i.trigger_count,
            "overdue": i.revisit_at is not None and i.revisit_at <= now,
            "sources": [{"recording_id": x.recording_id, "start": x.start, "end": x.end} for x in i.sources],
        }
        for i in items
    ]
