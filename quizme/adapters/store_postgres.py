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
import re
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


def _slug(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", label.strip().lower()).strip("-") or "misc"


class PostgresStore:
    def __init__(
        self,
        dsn: str,
        *,
        echo: bool = False,
        blob_account_url: str | None = None,
        credential: Any = None,
    ) -> None:
        self._engine: Engine = create_engine(
            dsn,
            echo=echo,
            pool_size=2,
            max_overflow=3,
            pool_pre_ping=True,
            json_serializer=lambda v: json.dumps(v, default=_json_default),
        )
        self._blob_account_url = blob_account_url
        self._credential = credential
        self._blob_svc: Any = None

    def dispose(self) -> None:
        self._engine.dispose()

    # -- blob (AD-1) -----------------------------------------------------

    def _blobs(self) -> Any:
        if self._blob_svc is None:
            from azure.storage.blob import BlobServiceClient  # noqa: PLC0415

            if not self._blob_account_url:
                raise StorageError("PostgresStore was built without a blob account URL")
            self._blob_svc = BlobServiceClient(self._blob_account_url, credential=self._credential)
        return self._blob_svc

    def put_blob(self, container: str, key: str, data: bytes, *, overwrite: bool = True) -> str:
        client = self._blobs().get_blob_client(container=container, blob=key)
        client.upload_blob(data, overwrite=overwrite)
        return client.url

    def read_blob(self, container: str, key: str) -> bytes:
        return self._blobs().get_blob_client(container=container, blob=key).download_blob().readall()

    def blob_url(self, container: str, key: str) -> str:
        return self._blobs().get_blob_client(container=container, blob=key).url

    # -- topics --------------------------------------------------------

    def get_or_create_topic(self, label: str) -> str:
        slug = _slug(label)
        with self._engine.begin() as conn:
            row = conn.execute(select(s.topic.c.id).where(s.topic.c.slug == slug)).first()
            if row:
                return row[0]
            topic_id = new_id()
            conn.execute(
                pg_insert(s.topic)
                .values(id=topic_id, slug=slug, label=label.strip())
                .on_conflict_do_nothing(index_elements=["slug"])
            )
            row = conn.execute(select(s.topic.c.id).where(s.topic.c.slug == slug)).first()
            return row[0] if row else topic_id

    def topic_labels(self, topic_ids: Sequence[str]) -> dict[str, str]:
        if not topic_ids:
            return {}
        with self._engine.connect() as conn:
            rows = conn.execute(select(s.topic.c.id, s.topic.c.label).where(s.topic.c.id.in_(list(topic_ids))))
            return {r[0]: r[1] for r in rows}

    def get_topic_note(self, topic_id: str) -> dict[str, Any] | None:
        with self._engine.connect() as conn:
            r = conn.execute(select(s.topic_note).where(s.topic_note.c.topic_id == topic_id)).mappings().first()
            return dict(r) if r else None

    def set_topic_note(self, topic_id: str, *, markdown: str, prompt_version: str) -> None:
        stmt = (
            pg_insert(s.topic_note)
            .values(
                topic_id=topic_id,
                markdown=markdown,
                prompt_version=prompt_version,
                regenerated_at=datetime.now(UTC),
            )
            .on_conflict_do_update(
                index_elements=["topic_id"],
                set_={"markdown": markdown, "prompt_version": prompt_version, "regenerated_at": datetime.now(UTC)},
            )
        )
        with self._engine.begin() as conn:
            conn.execute(stmt)

    # -- recordings / transcripts (AD-1) -----------------------------------

    def recording_by_hash(self, sha256: str) -> dict[str, Any] | None:
        with self._engine.connect() as conn:
            r = conn.execute(select(s.recording).where(s.recording.c.sha256 == sha256)).mappings().first()
            return dict(r) if r else None

    def add_recording(
        self, *, recording_id: str, upload_id: str, sha256: str, blob_key: str, filename: str, size: int
    ) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                insert(s.recording).values(
                    id=recording_id,
                    upload_id=upload_id,
                    sha256=sha256,
                    blob_key=blob_key,
                    filename=filename,
                    bytes=size,
                    created_at=datetime.now(UTC),
                )
            )

    def get_recording(self, recording_id: str) -> dict[str, Any] | None:
        with self._engine.connect() as conn:
            r = conn.execute(select(s.recording).where(s.recording.c.id == recording_id)).mappings().first()
            return dict(r) if r else None

    def add_transcript(self, *, transcript_id: str, recording_id: str, blob_key: str, full_text: str) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                insert(s.transcript).values(
                    id=transcript_id,
                    recording_id=recording_id,
                    blob_key=blob_key,
                    full_text=full_text,
                    created_at=datetime.now(UTC),
                )
            )

    def get_transcript_by_recording(self, recording_id: str) -> dict[str, Any] | None:
        with self._engine.connect() as conn:
            r = conn.execute(select(s.transcript).where(s.transcript.c.recording_id == recording_id)).mappings().first()
            return dict(r) if r else None

    def add_segments(self, rows: Sequence[dict[str, Any]]) -> None:
        if rows:
            with self._engine.begin() as conn:
                conn.execute(insert(s.segment), list(rows))

    def get_segments(self, transcript_id: str) -> list[dict[str, Any]]:
        with self._engine.connect() as conn:
            return [
                dict(r)
                for r in conn.execute(
                    select(s.segment).where(s.segment.c.transcript_id == transcript_id).order_by(s.segment.c.start_s)
                ).mappings()
            ]

    # -- run history (FR-37) ---------------------------------------------

    def record_stage_run(self, row: dict[str, Any]) -> None:
        with self._engine.begin() as conn:
            conn.execute(insert(s.stage_run).values(id=new_id(), **row))

    def ingestion_status(self, *, limit: int = 50) -> list[dict[str, Any]]:
        from sqlalchemy import text as _text

        with self._engine.connect() as conn:
            rows = conn.execute(
                _text(
                    "select r.id, r.filename, r.created_at, "
                    " (select count(*) from stage_run sr where sr.recording_id=r.id and sr.status='ok') ok, "
                    " (select count(*) from stage_run sr where sr.recording_id=r.id and sr.status='failed') failed, "
                    " (select max(sr.stage) from stage_run sr where sr.recording_id=r.id and sr.status='ok') last_ok "
                    "from recording r order by r.created_at desc limit :lim"
                ),
                {"lim": limit},
            ).mappings()
            return [dict(x) for x in rows]

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

    def kus_for_topic(self, topic_id: str) -> list[KnowledgeUnit]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                select(s.knowledge_unit).where(
                    s.knowledge_unit.c.status == KUStatus.ACTIVE.value,
                    s.knowledge_unit.c.topic_ids.contains([topic_id]),
                )
            ).mappings()
            return [_row_to_ku(r) for r in rows]

    def contradicted_and_pending_ku_ids(self) -> set[str]:
        """KUs to exclude from quiz selection (FR-15 / FR-24)."""
        with self._engine.connect() as conn:
            open_items = conn.execute(
                select(s.review_item.c.ku_ids).where(
                    s.review_item.c.status == "open",
                    s.review_item.c.kind.in_(["contradiction", "uncertain_extraction", "disputed_grade"]),
                )
            )
            out: set[str] = set()
            for (ids,) in open_items:
                out.update(ids)
            pending = conn.execute(
                select(s.knowledge_unit.c.id).where(s.knowledge_unit.c.status == KUStatus.PENDING_REVIEW.value)
            )
            out.update(r[0] for r in pending)
            return out

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
            "stability": c.stability or None,
            "difficulty": c.difficulty or None,
            "step": c.fsrs_json.get("step"),
            "reps": c.reps,
            "lapses": c.lapses,
            "last_review": c.last_review,
            "state": c.state,
            "fsrs_json": c.fsrs_json,
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

    def list_action_items(self, *, status: str | None = None, origin: str | None = None) -> list[ActionItem]:
        conds = []
        if status:
            conds.append(s.action_item.c.status == status)
        if origin:
            conds.append(s.action_item.c.origin == origin)
        with self._engine.connect() as conn:
            q = select(s.action_item)
            if conds:
                q = q.where(*conds)
            q = q.order_by(s.action_item.c.updated_at.desc())
            return [_row_to_action_item(r) for r in conn.execute(q).mappings()]

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

    def list_review_items(self, *, status: str = "open") -> list[dict[str, Any]]:
        with self._engine.connect() as conn:
            return [
                dict(r)
                for r in conn.execute(
                    select(s.review_item).where(s.review_item.c.status == status).order_by(s.review_item.c.created_at)
                ).mappings()
            ]

    def get_review_item(self, item_id: str) -> dict[str, Any] | None:
        with self._engine.connect() as conn:
            r = conn.execute(select(s.review_item).where(s.review_item.c.id == item_id)).mappings().first()
            return dict(r) if r else None

    def resolve_review_item(self, item_id: str, *, resolution: str) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                s.review_item.update()
                .where(s.review_item.c.id == item_id)
                .values(status="resolved", resolved_at=datetime.now(UTC), resolution=resolution)
            )

    # -- quiz / question / answer / grade (FR-24..31) -----------------

    def add_quiz(self, *, quiz_id: str, quiz_date: Any, ku_ids: Sequence[str]) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                insert(s.quiz).values(
                    id=quiz_id, quiz_date=quiz_date, ku_ids=list(ku_ids), created_at=datetime.now(UTC)
                )
            )

    def get_quiz_by_date(self, quiz_date: Any) -> dict[str, Any] | None:
        with self._engine.connect() as conn:
            r = conn.execute(select(s.quiz).where(s.quiz.c.quiz_date == quiz_date)).mappings().first()
            return dict(r) if r else None

    def add_questions(self, rows: Sequence[dict[str, Any]]) -> None:
        if rows:
            with self._engine.begin() as conn:
                conn.execute(insert(s.question), list(rows))

    def get_question(self, question_id: str) -> dict[str, Any] | None:
        with self._engine.connect() as conn:
            r = conn.execute(select(s.question).where(s.question.c.id == question_id)).mappings().first()
            return dict(r) if r else None

    def quiz_questions(self, quiz_id: str) -> list[dict[str, Any]]:
        with self._engine.connect() as conn:
            return [dict(r) for r in conn.execute(select(s.question).where(s.question.c.quiz_id == quiz_id)).mappings()]

    def record_answer(self, *, question_id: str, text: str) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                pg_insert(s.answer)
                .values(question_id=question_id, text=text, submitted_at=datetime.now(UTC))
                .on_conflict_do_update(
                    index_elements=["question_id"],
                    set_={"text": text, "submitted_at": datetime.now(UTC)},
                )
            )

    def record_grade(self, row: dict[str, Any]) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                pg_insert(s.grade)
                .values(graded_at=datetime.now(UTC), **row)
                .on_conflict_do_update(
                    index_elements=["question_id"],
                    set_={k: v for k, v in {**row, "graded_at": datetime.now(UTC)}.items() if k != "question_id"},
                )
            )

    def get_grade(self, question_id: str) -> dict[str, Any] | None:
        with self._engine.connect() as conn:
            r = conn.execute(select(s.grade).where(s.grade.c.question_id == question_id)).mappings().first()
            return dict(r) if r else None

    def mark_grade_disputed(self, question_id: str) -> None:
        with self._engine.begin() as conn:
            conn.execute(s.grade.update().where(s.grade.c.question_id == question_id).values(disputed=True))

    def recent_grades_for_ku(self, ku_id: str, *, limit: int = 5) -> list[str]:
        """Grade values for a KU's questions, most recent first (FR-41/45)."""
        with self._engine.connect() as conn:
            rows = conn.execute(
                select(s.grade.c.value)
                .select_from(s.grade.join(s.question, s.question.c.id == s.grade.c.question_id))
                .where(s.question.c.ku_id == ku_id, s.grade.c.disputed.is_(False))
                .order_by(s.grade.c.graded_at.desc())
                .limit(limit)
            )
            return [r[0] for r in rows]

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
            "llm_call, grade, answer, question, quiz, review_item, "
            "action_item_event, action_item, card, processed_ledger, stage_run, "
            "topic_note, topic, ku_embedding, knowledge_unit, segment, transcript, "
            "recording, app_setting, ku_operation"
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
        stability=float(r["stability"] or 0.0),
        difficulty=float(r["difficulty"] or 0.0),
        state=r["state"],
        last_review=r["last_review"],
        reps=r["reps"] or 0,
        lapses=r["lapses"] or 0,
        fsrs_json=r["fsrs_json"] or {},
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
