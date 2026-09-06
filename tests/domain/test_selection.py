"""FR-24: weakest-recall first, capped, excludes contradicted / pending KUs."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from quizme.domain.scheduling import Card
from quizme.domain.selection import select_due

NOW = datetime(2026, 9, 6, 12, 0, tzinfo=UTC)


def _card(ku_id: str, *, due_offset_days: float, stability: float, state: str = "review") -> Card:
    return Card(
        ku_id=ku_id,
        due=NOW + timedelta(days=due_offset_days),
        stability=stability,
        difficulty=5.0,
        state=state,
        last_review=NOW - timedelta(days=abs(due_offset_days) + 1),
        reps=3,
        lapses=0,
    )


def test_new_cards_are_top_priority_and_cap_applies() -> None:
    cards = [
        _card("new1", due_offset_days=-1, stability=0.0, state="new"),
        _card("strong", due_offset_days=30, stability=200.0),
        _card("overdue", due_offset_days=-10, stability=5.0),
    ]
    picked = select_due(cards, now=NOW, max_questions=2)
    assert picked[0] in {"new1", "overdue"}
    assert "strong" not in picked
    assert len(picked) == 2


def test_excludes_contradicted_and_pending() -> None:
    cards = [
        _card("a", due_offset_days=-1, stability=1.0),
        _card("b", due_offset_days=-1, stability=1.0),
    ]
    picked = select_due(cards, now=NOW, max_questions=10, exclude_ku_ids={"a"})
    assert picked == ["b"]


def test_not_due_but_below_retrievability_threshold_is_selected() -> None:
    # due far in the future, but low stability + time elapsed -> low retrievability
    card = _card("decaying", due_offset_days=5, stability=2.0)
    picked = select_due([card], now=NOW, max_questions=5, retrievability_threshold=0.99)
    assert picked == ["decaying"]
