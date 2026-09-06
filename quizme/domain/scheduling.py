"""Spaced-repetition scheduling — a thin wrapper over FSRS (AD-9).

The Card is scheduling state, not knowledge: it lives in its own store keyed by
``ku_id`` and is only ever written by the quiz/grade flow. Quiz generation and
grading read KUs read-only. Deleting all Cards must not affect the KB.

We wrap the ``fsrs`` package so the rest of the codebase never imports it directly
and so the AD-18 local fallback has one seam to reimplement.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import IntEnum
from typing import Any


class Rating(IntEnum):
    """Maps a Quizme Grade onto the FSRS 1..4 scale."""

    AGAIN = 1  # Grade.MISSED
    HARD = 2  # Grade.PARTIAL
    GOOD = 3  # Grade.CORRECT
    EASY = 4  # reserved; not currently produced by the grader


@dataclass(frozen=True, slots=True)
class Card:
    """Serialisable FSRS state for one KU. Field names mirror ``fsrs.Card``."""

    ku_id: str
    due: datetime
    stability: float
    difficulty: float
    step: int
    reps: int
    lapses: int
    last_review: datetime | None
    state: str  # "new" | "learning" | "review" | "relearning"

    @classmethod
    def new(cls, ku_id: str, *, now: datetime) -> Card:
        return cls(
            ku_id=ku_id,
            due=now,
            stability=0.0,
            difficulty=0.0,
            step=0,
            reps=0,
            lapses=0,
            last_review=None,
            state="new",
        )

    def is_due(self, *, now: datetime | None = None) -> bool:
        now = now or datetime.now(UTC)
        return self.due <= now


def review(card: Card, rating: Rating, *, now: datetime) -> Card:
    """Return the updated Card after a graded answer (FR-30).

    Implemented against the ``fsrs`` package. Kept import-local so the domain
    package has no hard import-time dependency on it during scaffolding.
    """
    from fsrs import Card as FsrsCard  # noqa: PLC0415
    from fsrs import Rating as FsrsRating
    from fsrs import Scheduler

    scheduler = Scheduler()
    fsrs_card = _to_fsrs(card, FsrsCard)
    updated, _log = scheduler.review_card(fsrs_card, FsrsRating(int(rating)), review_datetime=now)
    return _from_fsrs(card.ku_id, updated)


def _to_fsrs(card: Card, fsrs_card_cls: type) -> Any:  # pragma: no cover - integration
    raise NotImplementedError("map Card <-> fsrs.Card once the fsrs API version is pinned (Stack: fsrs 6.3.x)")


def _from_fsrs(ku_id: str, fsrs_card: Any) -> Card:  # pragma: no cover - integration
    raise NotImplementedError("map fsrs.Card -> Card")
