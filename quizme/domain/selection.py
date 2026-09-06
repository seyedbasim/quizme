"""Daily quiz selection — pure (FR-24).

Given the Cards and a set of KU ids to exclude (open contradictions, KUs still
pending review — FR-15 / FR-24), pick at most ``max_questions`` KUs, most-at-risk
first.
"""

from __future__ import annotations

import math
from collections.abc import Collection, Iterable
from datetime import datetime

from quizme.domain.scheduling import Card

# FSRS decay constant (FSRS-6 default); retrievability = (1 + FACTOR * t/S) ** DECAY
_DECAY = -0.5
_FACTOR = 19.0 / 81.0


def retrievability(card: Card, *, now: datetime) -> float:
    """Predicted probability of recall right now. New cards -> 0.0 (max priority)."""
    if card.state == "new" or card.stability <= 0:
        return 0.0
    elapsed_days = max((now - (card.last_review or card.due)).total_seconds() / 86400.0, 0.0)
    return float((1.0 + _FACTOR * elapsed_days / card.stability) ** _DECAY)


def select_due(
    cards: Iterable[Card],
    *,
    now: datetime,
    max_questions: int,
    exclude_ku_ids: Collection[str] = (),
    retrievability_threshold: float = 0.9,
) -> list[str]:
    """Return the KU ids to quiz today, weakest-recall first.

    A Card is a candidate if it is due *or* its predicted retrievability has
    dropped below ``retrievability_threshold``, and its KU is not excluded.
    """
    exclude = set(exclude_ku_ids)
    scored: list[tuple[float, Card]] = []
    for card in cards:
        if card.ku_id in exclude:
            continue
        r = retrievability(card, now=now)
        if card.is_due(now=now) or r < retrievability_threshold:
            scored.append((r, card))

    scored.sort(key=lambda pair: (pair[0], pair[1].due))
    return [card.ku_id for _r, card in scored[: max(max_questions, 0)]]


def strength_bucket(card: Card, *, now: datetime) -> str:
    """For the retention view (FR-32)."""
    if card.is_due(now=now) and card.state != "new":
        return "overdue"
    r = retrievability(card, now=now)
    if r >= 0.9:
        return "strong"
    if math.isnan(r) or r < 0.7:
        return "weak"
    return "ok"
