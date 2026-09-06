"""Store — Azure Database for PostgreSQL Flexible Server (+ pgvector) (AD-3, AD-9, AD-17).

* ``ku_operation`` is append-only (a DB trigger enforces it — migration 0001).
  The live KB is ``domain.ku.fold`` over the whole log (AD-3); ``knowledge_unit``
  is a convenience projection refreshed by ``pipeline.project``.
* vectors live in ``ku_embedding`` with an HNSW cosine index; ``nearest_kus``
  is ``ORDER BY embedding <=> :q``.
* ``processed_ledger`` gives every pipeline stage its idempotency check (AD-4).

Connection string comes from the ``database-url`` Key Vault secret via the app
setting; SQLAlchemy engine with a small pool (Flex Consumption + Burstable PG).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import create_engine, func, insert, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Engine

from quizme.adapters.db import schema as s
from quizme.domain.action_items import ActionItem, AIStatus, Origin
from quizme.domain.errors import StorageError
from quizme.domain.ids import new_id
from quizme.domain.ku import (
    Actor,
    KnowledgeUnit,
    KUOperation,
    KUOpType,
    KUStatus,
    SourceRef,
    fold,
)
from quizme.domain.scheduling import Card


def _json_default(o: object) -> str:
    if isinstance(o, datetime):
        return o.isoformat()
    raise TypeError(f"not JSON-serialisable: {type(o)}")


class PostgresStore:
    def __init__(self, dsn: str, *, echo: bool = False) -> None:
        self._engine: Engine = create_engine(
            dsn,
            echo=echo,
            pool_size=2,
            max_overflow=3,
            pool_pre_ping=True,
            json_serializer=lambda v: json.dumps(v, default=_json_default),
        )

    def dispose(self) -> None:
        self._engine.dispose()

    # -- operation log / KB projection (AD-3) ---------------------------------

    def append_ops(self, ops: Sequence[KUOperation]) -> None:
        if not ops:
            return
        rows = [
            {
                "op_id": op.op_id,
                "ts": op.ts,
                "actor": op.actor.value,
                "type": op.type.value,
                "ku_ids_in": list(op.ku_ids_in),
                "ku_id_out": op.ku_id_out,
                "payload": dict(op.payload),
                "model": op.model,
                "prompt_version": op.prompt_version,
                "prompt_hash": op.prompt_hash,
                "rationale": op.rationale,
            }
            for op in ops
        ]
        try:
            with self._engine.begin() as conn:
                conn.execute(insert(s.ku_operation), rows)
        except Exception as exc:  # noqa: BLE001
            raise StorageError(f"append_ops failed: {exc}") from exc

    def _iter_ops(self) -> list[KUOperation]:
        with self._engine.connect() as conn:
            rows = conn.execute(select(s.ku_operation).order_by(s.ku_operation.c.ts, s.ku_operation.c.op_id)).mappings()
            return [
                KUOperation(
                    op_id=r["op_id"],
                    ts=r["ts"],
                    actor=Actor(r["actor"]),
                    type=KUOpType(r["type"]),
                    ku_ids_in=tuple(r["ku_ids_in"]),
                    ku_id_out=r["ku_id_out"],
                    payload=r["payload"],
                    model=r["model"],
                    prompt_version=r["prompt_version"],
                    prompt_hash=r["prompt_hash"],
                    rationale=r["rationale"],
                )
                for r in rows
            ]

    def load_kus(self) -> dict[str, KnowledgeUnit]:
        try:
            return fold(self._iter_ops())
        except Exception as exc:  # noqa: BLE001
            raise StorageError(f"load_kus failed: {exc}") from exc

    def put_ku_embedding(self, ku_id: str, embedding: Sequence[float]) -> None:
        stmt = pg_insert(s.ku_embedding).values(ku_id=ku_id, embedding=list(embedding))
        stmt = stmt.on_conflict_do_update(index_elements=["ku_id"], set_={"embedding": list(embedding)})
        with self._engine.begin() as conn:
            conn.execute(stmt)

    def nearest_kus(self, embedding: Sequence[float], *, k: int) -> list[KnowledgeUnit]:
        """Top-k live KUs by cosine distance (AD-6 bound is applied by the caller
        via ``k``). Reads from the ``knowledge_unit`` projection joined to
        ``ku_embedding``."""
        q = list(embedding)
        with self._engine.connect() as conn:
            rows = conn.execute(
                select(s.knowledge_unit)
                .join(s.ku_embedding, s.ku_embedding.c.ku_id == s.knowledge_unit.c.id)
                .where(s.knowledge_unit.c.status == KUStatus.ACTIVE.value)
                .order_by(s.ku_embedding.c.embedding.cosine_distance(q))
                .limit(k)
            ).mappings()
            return [_row_to_ku(r) for r in rows]

    def upsert_ku_projection(self, kus: Sequence[KnowledgeUnit]) -> None:
        """Refresh the ``knowledge_unit`` table from folded state (pipeline.project)."""
        with self._engine.begin() as conn:
            for ku in kus:
                vals = {
                    "id": ku.id,
                    "canonical": ku.canonical,
                    "alt_phrasings": list(ku.alt_phrasings),
                    "topic_ids": list(ku.topic_ids),
                    "sources": [{"recording_id": x.recording_id, "start": x.start, "end": x.end} for x in ku.sources],
                    "status": ku.status.value,
                    "superseded_by": ku.superseded_by,
                    "created_at": ku.created_at,
                    "updated_at": ku.updated_at,
                }
                stmt = pg_insert(s.knowledge_unit).values(**vals)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["id"],
                    set_={k: vals[k] for k in vals if k != "id"},
                )
                conn.execute(stmt)

    # -- idempotency ledger (AD-4) -----------------------------------------

    def stage_done(self, *, input_hash: str, stage: str, stage_version: str) -> bool:
        with self._engine.connect() as conn:
            return (
                conn.execute(
                    select(func.count())
                    .select_from(s.processed_ledger)
                    .where(
                        s.processed_ledger.c.input_hash == input_hash,
                        s.processed_ledger.c.stage == stage,
                        s.processed_ledger.c.stage_version == stage_version,
                    )
                ).scalar_one()
                > 0
            )

    def mark_stage_done(self, *, input_hash: str, stage: str, stage_version: str) -> None:
        stmt = (
            pg_insert(s.processed_ledger)
            .values(input_hash=input_hash, stage=stage, stage_version=stage_version, done_at=datetime.now(UTC))
            .on_conflict_do_nothing()
        )
        with self._engine.begin() as conn:
            conn.execute(stmt)

    # -- scheduling (AD-9) -------------------------------------------------

    def get_card(self, ku_id: str) -> Card | None:
        with self._engine.connect() as conn:
            r = conn.execute(select(s.card).where(s.card.c.ku_id == ku_id)).mappings().first()
            return _row_to_card(r) if r else None

    def upsert_card(self, c: Card) -> None:
        vals = {
            "ku_id": c.ku_id,
            "due": c.due,
            "stability": c.stability,
            "difficulty": c.difficulty,
            "step": c.step,
            "reps": c.reps,
            "lapses": c.lapses,
            "last_review": c.last_review,
            "state": c.state,
        }
        stmt = (
            pg_insert(s.card)
            .values(**vals)
            .on_conflict_do_update(index_elements=["ku_id"], set_={k: vals[k] for k in vals if k != "ku_id"})
        )
        with self._engine.begin() as conn:
            conn.execute(stmt)

    def all_cards(self) -> list[Card]:
        with self._engine.connect() as conn:
            return [_row_to_card(r) for r in conn.execute(select(s.card)).mappings()]

    # -- action items (AD-12) --------------------------------------------

    def get_action_item(self, dedup_key: str) -> ActionItem | None:
        with self._engine.connect() as conn:
            r = conn.execute(select(s.action_item).where(s.action_item.c.dedup_key == dedup_key)).mappings().first()
            return _row_to_action_item(r) if r else None

    def upsert_action_item(self, item: ActionItem) -> None:
        vals = {
            "id": item.id,
            "origin": item.origin.value,
            "status": item.status.value,
            "dedup_key": item.dedup_key,
            "trigger_text": item.trigger_text,
            "sources": [{"recording_id": x.recording_id, "start": x.start, "end": x.end} for x in item.sources],
            "trigger_count": item.trigger_count,
            "ku_id": item.ku_id,
            "topic_id": item.topic_id,
            "revisit_at": item.revisit_at,
            "created_at": item.created_at,
            "updated_at": item.updated_at,
            "resolved_at": item.resolved_at,
            "resolution": item.resolution,
        }
        stmt = (
            pg_insert(s.action_item)
            .values(**vals)
            .on_conflict_do_update(
                index_elements=["dedup_key"], set_={k: vals[k] for k in vals if k not in ("id", "dedup_key")}
            )
        )
        with self._engine.begin() as conn:
            conn.execute(stmt)

    # -- review queue (FR-21) ------------------------------------------

    def add_review_item(self, *, kind: str, ku_ids: Sequence[str], context: dict) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                insert(s.review_item).values(
                    id=new_id(),
                    kind=kind,
                    ku_ids=list(ku_ids),
                    context=context,
                    status="open",
                    created_at=datetime.now(UTC),
                )
            )

    # -- spend (FR-38) -----------------------------------------------

    def record_llm_call(self, row: dict) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                insert(s.llm_call).values(
                    id=new_id(),
                    ts=row.get("ts") or datetime.now(UTC),
                    stage=row["stage"],
                    prompt_version=row["prompt_version"],
                    prompt_hash=row["prompt_hash"],
                    model=row["model"],
                    input_tokens=row["input_tokens"],
                    output_tokens=row["output_tokens"],
                    latency_ms=row["latency_ms"],
                    est_cost_usd=row["est_cost_usd"],
                )
            )

    def month_spend_usd(self, *, year: int, month: int) -> float:
        with self._engine.connect() as conn:
            total = conn.execute(
                select(func.coalesce(func.sum(s.llm_call.c.est_cost_usd), 0)).where(
                    func.extract("year", s.llm_call.c.ts) == year,
                    func.extract("month", s.llm_call.c.ts) == month,
                )
            ).scalar_one()
            return float(total)

    # -- maintenance ---------------------------------------------------

    def wipe_all(self) -> None:
        """Test helper — TRUNCATE every table the Store owns (TRUNCATE bypasses the
        per-row append-only trigger on ``ku_operation``). NEVER call in prod."""
        from sqlalchemy import text

        tables = (
            "llm_call, review_item, action_item, card, processed_ledger, stage_run, "
            "ku_embedding, knowledge_unit, segment, transcript, recording, app_setting, "
            "ku_operation"
        )
        with self._engine.begin() as conn:
            conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


# --------------------------------------------------------------------------- mappers


def _row_to_ku(r: Any) -> KnowledgeUnit:
    return KnowledgeUnit(
        id=r["id"],
        canonical=r["canonical"],
        topic_ids=tuple(r["topic_ids"]),
        alt_phrasings=tuple(r["alt_phrasings"]),
        sources=tuple(SourceRef(**x) for x in r["sources"]),
        status=KUStatus(r["status"]),
        superseded_by=r["superseded_by"],
        created_at=r["created_at"],
        updated_at=r["updated_at"],
    )


def _row_to_card(r: Any) -> Card:
    return Card(
        ku_id=r["ku_id"],
        due=r["due"],
        stability=r["stability"],
        difficulty=r["difficulty"],
        step=r["step"],
        reps=r["reps"],
        lapses=r["lapses"],
        last_review=r["last_review"],
        state=r["state"],
    )


def _row_to_action_item(r: Any) -> ActionItem:
    return ActionItem(
        id=r["id"],
        origin=Origin(r["origin"]),
        status=AIStatus(r["status"]),
        dedup_key=r["dedup_key"],
        trigger_text=r["trigger_text"],
        sources=tuple(SourceRef(**x) for x in r["sources"]),
        trigger_count=r["trigger_count"],
        created_at=r["created_at"],
        updated_at=r["updated_at"],
        ku_id=r["ku_id"],
        topic_id=r["topic_id"],
        revisit_at=r["revisit_at"],
        resolved_at=r["resolved_at"],
        resolution=r["resolution"],
    )
