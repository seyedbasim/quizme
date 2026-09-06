"""Spaced-repetition scheduling — a thin wrapper over the ``fsrs`` package (AD-9).

The Card is scheduling state, not knowledge: its own store keyed by ``ku_id``,
written only by the quiz/grade flow, read-only everywhere else. Deleting all Cards
must not affect the KB.

We keep the raw ``fsrs.Card`` dict in ``fsrs_json`` (source of truth for the
scheduler) plus a few denormalised columns for querying/selection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import IntEnum
from typing import Any

_STATE_NAME = {1: "learning", 2: "review", 3: "relearning"}


class Rating(IntEnum):
    """Maps a Quizme Grade onto the FSRS 1..4 scale."""

    AGAIN = 1  # Grade.MISSED
    HARD = 2  # Grade.PARTIAL
    GOOD = 3  # Grade.CORRECT
    EASY = 4  # reserved


@dataclass(frozen=True, slots=True)
class Card:
    ku_id: str
    due: datetime
    stability: float  # 0.0 when never reviewed
    difficulty: float
    state: str  # "new" | "learning" | "review" | "relearning"
    last_review: datetime | None
    reps: int
    lapses: int
    fsrs_json: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def new(cls, ku_id: str, *, now: datetime) -> Card:
        from fsrs import Card as FsrsCard  # noqa: PLC0415

        fc = FsrsCard(due=now)
        return _from_fsrs(ku_id, dict(fc.to_dict()), reps=0, lapses=0)

    def is_due(self, *, now: datetime | None = None) -> bool:
        now = now or datetime.now(UTC)
        return self.due <= now


def review(card: Card, rating: Rating, *, now: datetime) -> Card:
    """Return the updated Card after a graded answer (FR-30)."""
    from fsrs import Card as FsrsCard  # noqa: PLC0415
    from fsrs import Rating as FsrsRating
    from fsrs import Scheduler

    fc = FsrsCard.from_dict(card.fsrs_json) if card.fsrs_json else FsrsCard(due=card.due)  # type: ignore[arg-type]
    updated, _log = Scheduler().review_card(fc, FsrsRating(int(rating)), review_datetime=now)
    return _from_fsrs(
        card.ku_id,
        dict(updated.to_dict()),
        reps=card.reps + 1,
        lapses=card.lapses + (1 if rating is Rating.AGAIN else 0),
    )


def _from_fsrs(ku_id: str, d: dict[str, Any], *, reps: int, lapses: int) -> Card:
    last_review = _parse(d.get("last_review"))
    return Card(
        ku_id=ku_id,
        due=_parse(d["due"]),
        stability=float(d.get("stability") or 0.0),
        difficulty=float(d.get("difficulty") or 0.0),
        state="new" if last_review is None else _STATE_NAME.get(int(d.get("state", 1)), "learning"),
        last_review=last_review,
        reps=reps,
        lapses=lapses,
        fsrs_json=d,
    )


def _parse(v: Any) -> Any:
    if v is None or isinstance(v, datetime):
        return v
    return datetime.fromisoformat(v)
