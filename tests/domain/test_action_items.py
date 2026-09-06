"""AD-12: upsert on the dedup key. Repeated triggers bump trigger_count and
union sources; they never create duplicates."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from quizme.domain.action_items import (
    AIStatus,
    Origin,
    followup_key,
    resolve,
    revisit_key,
    snooze,
    upsert,
)
from quizme.domain.ku import SourceRef

NOW = datetime(2026, 9, 6, tzinfo=UTC)


def test_revisit_key_is_per_ku() -> None:
    assert revisit_key("ku1") == revisit_key("ku1")
    assert revisit_key("ku1") != revisit_key("ku2")


def test_followup_key_same_intent_same_key() -> None:
    a = followup_key("topic-tcp", "check the RFC 6298 minimum RTO")
    b = followup_key("topic-tcp", "Check the RFC 6298 minimum RTO.")  # punctuation/case
    assert a == b


def test_repeated_followup_upserts_not_duplicates() -> None:
    key = followup_key("t", "look up the paper")
    item = upsert(
        None,
        origin=Origin.FOLLOW_UP,
        dedup_key=key,
        trigger_text="I should look up the paper",
        now=NOW,
        sources=(SourceRef("r1", 1.0, 3.0),),
        topic_id="t",
    )
    assert item.trigger_count == 1

    item = upsert(
        item,
        origin=Origin.FOLLOW_UP,
        dedup_key=key,
        trigger_text="need to read that paper",
        now=NOW + timedelta(days=1),
        sources=(SourceRef("r2", 5.0, 7.0),),
        topic_id="t",
    )
    assert item.trigger_count == 2
    assert {s.recording_id for s in item.sources} == {"r1", "r2"}


def test_dismissed_not_resurrected_within_cooldown() -> None:
    key = revisit_key("ku1")
    item = upsert(None, origin=Origin.REVISIT, dedup_key=key, trigger_text="missed", now=NOW, ku_id="ku1")
    item = resolve(item, now=NOW + timedelta(days=1), how="dismissed")
    assert item.status is AIStatus.DISMISSED

    # same trigger 3 days later -> still dismissed, but count rises
    item = upsert(
        item,
        origin=Origin.REVISIT,
        dedup_key=key,
        trigger_text="missed again",
        now=NOW + timedelta(days=4),
        ku_id="ku1",
        resurrect_cooldown_days=14,
    )
    assert item.status is AIStatus.DISMISSED
    assert item.trigger_count == 2

    # 20 days after dismissal -> reopened
    item = upsert(
        item,
        origin=Origin.REVISIT,
        dedup_key=key,
        trigger_text="missed once more",
        now=NOW + timedelta(days=25),
        ku_id="ku1",
        resurrect_cooldown_days=14,
    )
    assert item.status is AIStatus.OPEN


def test_snoozed_reopens_when_due() -> None:
    key = revisit_key("ku2")
    item = upsert(None, origin=Origin.REVISIT, dedup_key=key, trigger_text="x", now=NOW, ku_id="ku2")
    item = snooze(item, until=NOW + timedelta(days=7), now=NOW)
    assert item.status is AIStatus.SNOOZED

    item = upsert(
        item, origin=Origin.REVISIT, dedup_key=key, trigger_text="x", now=NOW + timedelta(days=8), ku_id="ku2"
    )
    assert item.status is AIStatus.OPEN
