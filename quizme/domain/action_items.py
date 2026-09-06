"""Action Items — the to-do list (FR-39..FR-45).

**AD-12** — Action Items are tracked task state, not knowledge. They live in their
own store, reference KUs / Sources / Topics read-only, and never produce a
KUOperation or touch a Card. Creation is *upsert on a dedup key*, never blind
insert:

* ``("revisit", ku_id)``                       for Revisit items (FR-41)
* ``("follow_up", topic_id, intent_hash)``     for Follow-ups (FR-40, FR-42)
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum

from quizme.domain.ids import new_id
from quizme.domain.ku import SourceRef

_NON_WORD = re.compile(r"[^a-z0-9 ]+")


def _intent_hash(text: str) -> str:
    """Aggressive normalisation for follow-up dedup: lowercase, strip all
    punctuation, collapse whitespace. "Check the RFC." == "check the rfc"."""
    norm = _NON_WORD.sub(" ", text.lower())
    norm = " ".join(norm.split())
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


class Origin(str, Enum):
    FOLLOW_UP = "follow_up"
    REVISIT = "revisit"


class AIStatus(str, Enum):
    OPEN = "open"
    SNOOZED = "snoozed"
    DONE = "done"
    DISMISSED = "dismissed"


@dataclass(frozen=True, slots=True)
class ActionItem:
    id: str
    origin: Origin
    status: AIStatus
    dedup_key: str
    trigger_text: str
    sources: tuple[SourceRef, ...]
    trigger_count: int
    created_at: datetime
    updated_at: datetime
    ku_id: str | None = None
    topic_id: str | None = None
    revisit_at: datetime | None = None
    resolved_at: datetime | None = None
    resolution: str | None = None  # "done" | "dismissed" | "auto"


def revisit_key(ku_id: str) -> str:
    return f"revisit:{ku_id}"


def followup_key(topic_id: str | None, intent_text: str) -> str:
    return f"follow_up:{topic_id or '_'}:{_intent_hash(intent_text)}"


def upsert(
    existing: ActionItem | None,
    *,
    origin: Origin,
    dedup_key: str,
    trigger_text: str,
    now: datetime,
    sources: tuple[SourceRef, ...] = (),
    ku_id: str | None = None,
    topic_id: str | None = None,
    resurrect_cooldown_days: int = 14,
) -> ActionItem:
    """Create the item, or bump ``trigger_count`` and union sources on the
    existing one (FR-42).

    A ``dismissed`` item is not silently re-opened by an identical trigger within
    the cooldown — it is left dismissed but its ``trigger_count`` still rises, so
    the surfacing layer (FR-42) can flag "you keep mentioning this".
    """
    if existing is None:
        return ActionItem(
            id=new_id(),
            origin=origin,
            status=AIStatus.OPEN,
            dedup_key=dedup_key,
            trigger_text=trigger_text,
            sources=sources,
            trigger_count=1,
            created_at=now,
            updated_at=now,
            ku_id=ku_id,
            topic_id=topic_id,
        )

    merged_sources = _union_sources(existing.sources, sources)
    new_status = existing.status
    if existing.status == AIStatus.SNOOZED and (existing.revisit_at is None or existing.revisit_at <= now):
        new_status = AIStatus.OPEN
    elif existing.status == AIStatus.DISMISSED and existing.resolved_at is not None:
        days = (now - existing.resolved_at).total_seconds() / 86400.0
        if days >= resurrect_cooldown_days:
            new_status = AIStatus.OPEN

    return replace(
        existing,
        status=new_status,
        trigger_count=existing.trigger_count + 1,
        sources=merged_sources,
        trigger_text=existing.trigger_text or trigger_text,
        updated_at=now,
    )


def resolve(item: ActionItem, *, now: datetime, how: str) -> ActionItem:
    """Mark done / dismissed / auto-resolved (FR-44, FR-45)."""
    status = {
        "done": AIStatus.DONE,
        "dismissed": AIStatus.DISMISSED,
        "auto": AIStatus.DONE,
    }[how]
    return replace(item, status=status, resolved_at=now, resolution=how, updated_at=now)


def snooze(item: ActionItem, *, until: datetime, now: datetime) -> ActionItem:
    return replace(item, status=AIStatus.SNOOZED, revisit_at=until, updated_at=now)


def _union_sources(*groups: tuple[SourceRef, ...]) -> tuple[SourceRef, ...]:
    seen: dict[tuple[str, float, float], SourceRef] = {}
    for group in groups:
        for s in group:
            seen.setdefault((s.recording_id, s.start, s.end), s)
    return tuple(seen.values())
