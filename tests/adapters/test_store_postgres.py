"""Integration tests for PostgresStore.

Runs only when ``QUIZME_TEST_DATABASE_URL`` points at a disposable Postgres with
the ``0001`` migration applied and ``pgvector`` enabled. ``wipe_all()`` TRUNCATEs
every table, so never point this at data you care about.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

import pytest

from quizme.domain.action_items import AIStatus, Origin, revisit_key, upsert
from quizme.domain.ids import new_id
from quizme.domain.ku import Actor, KnowledgeUnit, KUOperation, KUOpType, KUStatus, SourceRef, ku_payload
from quizme.domain.scheduling import Card

_DSN = os.environ.get("QUIZME_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not _DSN, reason="set QUIZME_TEST_DATABASE_URL to run store integration tests")

NOW = datetime(2026, 9, 6, 12, 0, tzinfo=UTC)


@pytest.fixture
def store():
    from quizme.adapters.store_postgres import PostgresStore

    st = PostgresStore(_DSN)
    st.wipe_all()
    yield st
    st.wipe_all()
    st.dispose()


def _ku(canonical: str, rec: str = "r1") -> KnowledgeUnit:
    return KnowledgeUnit(
        id=new_id(),
        canonical=canonical,
        topic_ids=("net",),
        sources=(SourceRef(rec, 0.0, 4.0),),
        created_at=NOW,
        updated_at=NOW,
    )


def _create_op(ku: KnowledgeUnit) -> KUOperation:
    return KUOperation(
        op_id=new_id(),
        ts=NOW,
        actor=Actor.ENGINE,
        type=KUOpType.CREATE,
        ku_ids_in=(ku.id,),
        payload={"ku": ku_payload(ku)},
        model="m",
        prompt_version="v1",
        prompt_hash="h",
    )


def test_oplog_roundtrip_and_fold(store) -> None:
    a, b = _ku("TTL is decremented per hop"), _ku("HTTP 429 = too many requests", "r2")
    store.append_ops([_create_op(a), _create_op(b)])
    store.append_ops(
        [
            KUOperation(
                op_id=new_id(),
                ts=NOW + timedelta(minutes=1),
                actor=Actor.USER,
                type=KUOpType.EDIT,
                ku_ids_in=(a.id,),
                payload={"ku_id": a.id, "canonical": "IP TTL drops by 1 at each router"},
            )
        ]
    )
    kus = store.load_kus()
    assert kus[a.id].canonical == "IP TTL drops by 1 at each router"
    assert kus[b.id].status is KUStatus.ACTIVE
    assert isinstance(kus[a.id].created_at, datetime)


def test_oplog_is_append_only(store) -> None:
    from sqlalchemy import text

    a = _ku("x")
    store.append_ops([_create_op(a)])
    with pytest.raises(Exception, match="append-only"), store._engine.begin() as conn:  # noqa: SLF001
        conn.execute(text("UPDATE ku_operation SET rationale = 'tamper'"))


def test_embedding_knn(store) -> None:
    a, b, c = _ku("cats are mammals"), _ku("dogs are mammals"), _ku("TCP is a transport protocol")
    store.append_ops([_create_op(a), _create_op(b), _create_op(c)])
    store.upsert_ku_projection([a, b, c])
    store.put_ku_embedding(a.id, [1.0, 0.0] + [0.0] * 1534)
    store.put_ku_embedding(b.id, [0.9, 0.1] + [0.0] * 1534)
    store.put_ku_embedding(c.id, [0.0, 1.0] + [0.0] * 1534)
    near = store.nearest_kus([1.0, 0.0] + [0.0] * 1534, k=2)
    assert {k.id for k in near} == {a.id, b.id}


def test_processed_ledger_idempotency(store) -> None:
    assert store.stage_done(input_hash="h1", stage="extract", stage_version="v1") is False
    store.mark_stage_done(input_hash="h1", stage="extract", stage_version="v1")
    store.mark_stage_done(input_hash="h1", stage="extract", stage_version="v1")  # no-op
    assert store.stage_done(input_hash="h1", stage="extract", stage_version="v1") is True
    assert store.stage_done(input_hash="h1", stage="extract", stage_version="v2") is False


def test_card_roundtrip(store) -> None:
    c = Card.new("ku-1", now=NOW)
    store.upsert_card(c)
    got = store.get_card("ku-1")
    assert got is not None and got.state == "new"
    store.upsert_card(Card.new("ku-2", now=NOW))
    assert len(store.all_cards()) == 2


def test_action_item_upsert_dedup(store) -> None:
    key = revisit_key("ku-9")
    it = upsert(None, origin=Origin.REVISIT, dedup_key=key, trigger_text="missed", now=NOW, ku_id="ku-9")
    store.upsert_action_item(it)
    it2 = upsert(
        store.get_action_item(key),
        origin=Origin.REVISIT,
        dedup_key=key,
        trigger_text="missed again",
        now=NOW + timedelta(days=1),
        ku_id="ku-9",
    )
    store.upsert_action_item(it2)
    final = store.get_action_item(key)
    assert final is not None and final.trigger_count == 2 and final.status is AIStatus.OPEN


def test_spend_rollup(store) -> None:
    for cost in (0.01, 0.02, 0.03):
        store.record_llm_call(
            {
                "stage": "extract",
                "prompt_version": "v1",
                "prompt_hash": "h",
                "model": "gpt-5-mini",
                "input_tokens": 100,
                "output_tokens": 20,
                "latency_ms": 500,
                "est_cost_usd": cost,
            }
        )
    assert round(store.month_spend_usd(year=NOW.year, month=NOW.month), 2) == 0.06
    assert store.month_spend_usd(year=2000, month=1) == 0.0
