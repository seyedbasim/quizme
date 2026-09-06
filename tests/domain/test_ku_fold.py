"""fold() is the AD-3 projection: replaying ops from empty yields the live KU set."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from quizme.domain.ids import new_id
from quizme.domain.ku import (
    Actor,
    KnowledgeUnit,
    KUOperation,
    KUOpType,
    KUStatus,
    SourceRef,
    fold,
    live,
)

T0 = datetime(2026, 9, 1, tzinfo=UTC)


def _ku_dict(ku: KnowledgeUnit) -> dict:
    return {
        "id": ku.id,
        "canonical": ku.canonical,
        "topic_ids": list(ku.topic_ids),
        "sources": [{"recording_id": s.recording_id, "start": s.start, "end": s.end} for s in ku.sources],
        "alt_phrasings": list(ku.alt_phrasings),
        "created_at": ku.created_at,
        "updated_at": ku.updated_at,
        "status": ku.status.value,
    }


def _create(ku: KnowledgeUnit, ts: datetime) -> KUOperation:
    return KUOperation(
        op_id=new_id(),
        ts=ts,
        actor=Actor.ENGINE,
        type=KUOpType.CREATE,
        ku_ids_in=(ku.id,),
        payload={"ku": _ku_dict(ku)},
    )


def _mk(canonical: str, *, rec: str, topics: tuple[str, ...] = ("t",)) -> KnowledgeUnit:
    return KnowledgeUnit(
        id=new_id(),
        canonical=canonical,
        topic_ids=topics,
        sources=(SourceRef(rec, 0.0, 5.0),),
        created_at=T0,
        updated_at=T0,
    )


def test_create_then_edit_then_archive() -> None:
    ku = _mk("The sky is green", rec="r1")
    ops = [
        _create(ku, T0),
        KUOperation(
            op_id=new_id(),
            ts=T0 + timedelta(days=1),
            actor=Actor.USER,
            type=KUOpType.EDIT,
            ku_ids_in=(ku.id,),
            payload={"ku_id": ku.id, "canonical": "The sky is blue"},
        ),
    ]
    kus = fold(ops)
    assert kus[ku.id].canonical == "The sky is blue"
    assert kus[ku.id].status is KUStatus.ACTIVE

    ops.append(
        KUOperation(
            op_id=new_id(),
            ts=T0 + timedelta(days=2),
            actor=Actor.USER,
            type=KUOpType.ARCHIVE,
            ku_ids_in=(ku.id,),
            payload={"ku_id": ku.id},
        )
    )
    kus = fold(ops)
    assert kus[ku.id].status is KUStatus.TOMBSTONED
    assert live(kus) == []


def test_merge_unions_sources_and_tombstones_loser() -> None:
    a = _mk("HTTP 429 means too many requests", rec="r1")
    b = KnowledgeUnit(
        id=new_id(),
        canonical="429 is the rate-limit status code",
        topic_ids=("http",),
        sources=(SourceRef("r2", 10.0, 14.0),),
        created_at=T0,
        updated_at=T0,
    )
    ops = [
        _create(a, T0),
        _create(b, T0 + timedelta(minutes=1)),
        KUOperation(
            op_id=new_id(),
            ts=T0 + timedelta(minutes=2),
            actor=Actor.ENGINE,
            type=KUOpType.MERGE,
            ku_ids_in=(a.id, b.id),
            payload={
                "survivor_id": a.id,
                "loser_id": b.id,
                "canonical": a.canonical,
                "alt_phrasings": [b.canonical],
                "topic_ids": ["http"],
            },
        ),
    ]
    kus = fold(ops)
    survivor = kus[a.id]
    assert kus[b.id].status is KUStatus.TOMBSTONED
    assert kus[b.id].superseded_by == a.id
    # AD-5: provenance union — both recordings retained
    assert {s.recording_id for s in survivor.sources} == {"r1", "r2"}
    assert b.canonical in survivor.alt_phrasings
    assert "http" in survivor.topic_ids


def test_fold_is_deterministic_replay() -> None:
    ku = _mk("x", rec="r1")
    ops = [_create(ku, T0)]
    assert fold(ops) == fold(list(ops))
