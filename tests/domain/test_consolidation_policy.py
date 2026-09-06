"""AD-15: bias toward under-merging. High-confidence duplicate -> merge;
low-confidence -> create + review signal; contradiction -> flag, never merge."""

from __future__ import annotations

from datetime import UTC, datetime

from quizme.domain.consolidation import (
    ConsolidationConfig,
    PairJudgement,
    Verdict,
    plan_operations,
)
from quizme.domain.ids import new_id
from quizme.domain.ku import KnowledgeUnit, KUOpType, SourceRef

NOW = datetime(2026, 9, 6, tzinfo=UTC)
CFG = ConsolidationConfig(merge_confidence_threshold=0.8)


def _ku(canonical: str, rec: str = "r9") -> KnowledgeUnit:
    return KnowledgeUnit(
        id=new_id(),
        canonical=canonical,
        topic_ids=("t",),
        sources=(SourceRef(rec, 0.0, 3.0),),
        created_at=NOW,
        updated_at=NOW,
    )


def _plan(new, judgements, existing):
    return plan_operations(
        new,
        judgements,
        existing,
        CFG,
        now=NOW,
        model="m",
        prompt_version="consolidate.v1",
        prompt_hash="h",
    )


def test_high_confidence_duplicate_merges() -> None:
    existing_ku = _ku("A packet's TTL is decremented by each router")
    new = _ku("Every hop decrements the IP TTL")
    j = [PairJudgement(existing_ku.id, Verdict.DUPLICATE, 0.93, "same claim")]

    plan = _plan(new, j, {existing_ku.id: existing_ku})

    assert [op.type for op in plan.ops] == [KUOpType.MERGE]
    assert plan.ops[0].payload["survivor_id"] == existing_ku.id
    assert plan.review_signals == ()


def test_low_confidence_duplicate_creates_and_proposes_merge() -> None:
    existing_ku = _ku("A packet's TTL is decremented by each router")
    new = _ku("Every hop decrements the IP TTL")
    j = [PairJudgement(existing_ku.id, Verdict.DUPLICATE, 0.62, "probably same")]

    plan = _plan(new, j, {existing_ku.id: existing_ku})

    assert [op.type for op in plan.ops] == [KUOpType.CREATE]
    assert len(plan.review_signals) == 1
    assert plan.review_signals[0].kind == "proposed_merge"


def test_contradiction_flags_never_merges() -> None:
    existing_ku = _ku("The TCP minimum RTO is 200ms")
    new = _ku("The TCP minimum RTO is 1 second")
    j = [PairJudgement(existing_ku.id, Verdict.CONTRADICTION, 0.97, "different values")]

    plan = _plan(new, j, {existing_ku.id: existing_ku})

    types = [op.type for op in plan.ops]
    assert KUOpType.CREATE in types
    assert KUOpType.FLAG_CONTRADICTION in types
    assert KUOpType.MERGE not in types
    assert any(s.kind == "contradiction" for s in plan.review_signals)


def test_all_unrelated_just_creates() -> None:
    other = _ku("BGP uses TCP port 179")
    new = _ku("OSPF is a link-state protocol")
    j = [PairJudgement(other.id, Verdict.UNRELATED, 0.9, "different")]

    plan = _plan(new, j, {other.id: other})

    assert [op.type for op in plan.ops] == [KUOpType.CREATE]
    assert plan.review_signals == ()
