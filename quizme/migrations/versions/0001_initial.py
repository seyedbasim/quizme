"""initial schema — core tables

Revision ID: 0001
Revises:
Create Date: 2026-09-06

Covers the entities in the architecture-spine ERD. Deliberately conservative:
JSON columns where the shape is still settling, refine in later migrations.
The op-log (``ku_operation``) is append-only — enforced by a trigger, not just
convention (AD-3).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "recording",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("upload_id", sa.String, nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False, unique=True),  # dedup key (FR-1)
        sa.Column("blob_key", sa.String, nullable=False),
        sa.Column("filename", sa.String, nullable=False),
        sa.Column("bytes", sa.BigInteger, nullable=False),
        sa.Column("created_at", _TS, nullable=False),
    )

    op.create_table(
        "transcript",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("recording_id", sa.String, sa.ForeignKey("recording.id"), nullable=False, unique=True),
        sa.Column("blob_key", sa.String, nullable=False),
        sa.Column("full_text", sa.Text, nullable=False),
        sa.Column("created_at", _TS, nullable=False),
    )

    op.create_table(
        "segment",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("transcript_id", sa.String, sa.ForeignKey("transcript.id"), nullable=False),
        sa.Column("start_s", sa.Float, nullable=False),
        sa.Column("end_s", sa.Float, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("label", sa.String, nullable=False),  # study | noise
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("prompt_version", sa.String, nullable=False),
    )

    op.create_table(
        "ku_operation",  # append-only (AD-3)
        sa.Column("op_id", sa.String, primary_key=True),
        sa.Column("ts", _TS, nullable=False),
        sa.Column("actor", sa.String, nullable=False),  # engine | user | auto
        sa.Column("type", sa.String, nullable=False),
        sa.Column("ku_ids_in", sa.JSON, nullable=False),
        sa.Column("ku_id_out", sa.String, nullable=True),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column("model", sa.String, nullable=True),
        sa.Column("prompt_version", sa.String, nullable=True),
        sa.Column("prompt_hash", sa.String, nullable=True),
        sa.Column("rationale", sa.Text, nullable=True),
    )
    op.create_index("ix_ku_operation_ts", "ku_operation", ["ts"])
    op.execute(
        """
        CREATE OR REPLACE FUNCTION quizme_block_oplog_mutation() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'ku_operation is append-only (AD-3)'; END;
        $$ LANGUAGE plpgsql;
        CREATE TRIGGER ku_operation_immutable
          BEFORE UPDATE OR DELETE ON ku_operation
          FOR EACH ROW EXECUTE FUNCTION quizme_block_oplog_mutation();
        """
    )

    op.create_table(
        "knowledge_unit",  # materialised projection of the op-log
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("canonical", sa.Text, nullable=False),
        sa.Column("alt_phrasings", sa.JSON, nullable=False),
        sa.Column("topic_ids", sa.JSON, nullable=False),
        sa.Column("sources", sa.JSON, nullable=False),
        sa.Column("status", sa.String, nullable=False),
        sa.Column("superseded_by", sa.String, nullable=True),
        sa.Column("created_at", _TS, nullable=False),
        sa.Column("updated_at", _TS, nullable=False),
    )

    op.execute(
        "CREATE TABLE ku_embedding (ku_id text PRIMARY KEY REFERENCES knowledge_unit(id), embedding vector(1536))"
    )
    op.execute("CREATE INDEX ix_ku_embedding_hnsw ON ku_embedding USING hnsw (embedding vector_cosine_ops)")

    op.create_table(
        "topic",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("slug", sa.String, nullable=False, unique=True),
        sa.Column("label", sa.String, nullable=False),
    )
    op.create_table(
        "topic_note",
        sa.Column("topic_id", sa.String, sa.ForeignKey("topic.id"), primary_key=True),
        sa.Column("markdown", sa.Text, nullable=False),
        sa.Column("prompt_version", sa.String, nullable=False),
        sa.Column("regenerated_at", _TS, nullable=False),
    )

    op.create_table(
        "card",  # FSRS scheduling state (AD-9) — separate store, keyed by ku_id
        sa.Column("ku_id", sa.String, primary_key=True),
        sa.Column("due", _TS, nullable=False),
        sa.Column("stability", sa.Float, nullable=False),
        sa.Column("difficulty", sa.Float, nullable=False),
        sa.Column("step", sa.Integer, nullable=False),
        sa.Column("reps", sa.Integer, nullable=False),
        sa.Column("lapses", sa.Integer, nullable=False),
        sa.Column("last_review", _TS, nullable=True),
        sa.Column("state", sa.String, nullable=False),
    )

    op.create_table(
        "quiz",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("quiz_date", sa.Date, nullable=False, unique=True),
        sa.Column("ku_ids", sa.JSON, nullable=False),
        sa.Column("created_at", _TS, nullable=False),
    )
    op.create_table(
        "question",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("quiz_id", sa.String, sa.ForeignKey("quiz.id"), nullable=False),
        sa.Column("ku_id", sa.String, nullable=False),
        sa.Column("type", sa.String, nullable=False),
        sa.Column("prompt", sa.Text, nullable=False),
        sa.Column("model_answer", sa.Text, nullable=False),
        sa.Column("phrasing_used", sa.Text, nullable=False),
        sa.Column("prompt_version", sa.String, nullable=False),
    )
    op.create_table(
        "answer",
        sa.Column("question_id", sa.String, sa.ForeignKey("question.id"), primary_key=True),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("submitted_at", _TS, nullable=False),
    )
    op.create_table(
        "grade",
        sa.Column("question_id", sa.String, sa.ForeignKey("question.id"), primary_key=True),
        sa.Column("value", sa.String, nullable=False),
        sa.Column("rationale", sa.Text, nullable=False),
        sa.Column("model", sa.String, nullable=False),
        sa.Column("prompt_version", sa.String, nullable=False),
        sa.Column("graded_at", _TS, nullable=False),
        sa.Column("disputed", sa.Boolean, nullable=False, server_default=sa.false()),
    )

    op.create_table(
        "review_item",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("kind", sa.String, nullable=False),
        sa.Column("ku_ids", sa.JSON, nullable=False),
        sa.Column("context", sa.JSON, nullable=False),
        sa.Column("status", sa.String, nullable=False, server_default="open"),
        sa.Column("created_at", _TS, nullable=False),
        sa.Column("resolved_at", _TS, nullable=True),
        sa.Column("resolution", sa.String, nullable=True),
    )

    op.create_table(
        "action_item",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("origin", sa.String, nullable=False),
        sa.Column("status", sa.String, nullable=False),
        sa.Column("dedup_key", sa.String, nullable=False, unique=True),  # AD-12
        sa.Column("trigger_text", sa.Text, nullable=False),
        sa.Column("sources", sa.JSON, nullable=False),
        sa.Column("trigger_count", sa.Integer, nullable=False, server_default="1"),
        sa.Column("ku_id", sa.String, nullable=True),
        sa.Column("topic_id", sa.String, nullable=True),
        sa.Column("revisit_at", _TS, nullable=True),
        sa.Column("created_at", _TS, nullable=False),
        sa.Column("updated_at", _TS, nullable=False),
        sa.Column("resolved_at", _TS, nullable=True),
        sa.Column("resolution", sa.String, nullable=True),
    )
    op.create_table(
        "action_item_event",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("action_item_id", sa.String, sa.ForeignKey("action_item.id"), nullable=False),
        sa.Column("ts", _TS, nullable=False),
        sa.Column("from_status", sa.String, nullable=True),
        sa.Column("to_status", sa.String, nullable=False),
    )

    op.create_table(
        "processed_ledger",  # idempotency (AD-4)
        sa.Column("input_hash", sa.String, primary_key=True),
        sa.Column("stage", sa.String, primary_key=True),
        sa.Column("stage_version", sa.String, primary_key=True),
        sa.Column("done_at", _TS, nullable=False),
    )

    op.create_table(
        "stage_run",  # run history / errors (FR-37)
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("recording_id", sa.String, nullable=False),
        sa.Column("stage", sa.String, nullable=False),
        sa.Column("status", sa.String, nullable=False),  # ok | failed | parked
        sa.Column("attempts", sa.Integer, nullable=False, server_default="1"),
        sa.Column("traceback", sa.Text, nullable=True),
        sa.Column("run_id", sa.String, nullable=False),
        sa.Column("started_at", _TS, nullable=False),
        sa.Column("finished_at", _TS, nullable=True),
    )

    op.create_table(
        "llm_call",  # spend accounting (FR-38)
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("ts", _TS, nullable=False),
        sa.Column("stage", sa.String, nullable=False),
        sa.Column("prompt_version", sa.String, nullable=False),
        sa.Column("prompt_hash", sa.String, nullable=False),
        sa.Column("model", sa.String, nullable=False),
        sa.Column("input_tokens", sa.Integer, nullable=False),
        sa.Column("output_tokens", sa.Integer, nullable=False),
        sa.Column("latency_ms", sa.Integer, nullable=False),
        sa.Column("est_cost_usd", sa.Numeric(10, 5), nullable=False),
    )
    op.create_index("ix_llm_call_ts", "llm_call", ["ts"])

    op.create_table(
        "app_setting",  # FR-52
        sa.Column("key", sa.String, primary_key=True),
        sa.Column("value", sa.JSON, nullable=False),
        sa.Column("updated_at", _TS, nullable=False),
    )


def downgrade() -> None:
    for table in [
        "app_setting",
        "llm_call",
        "stage_run",
        "processed_ledger",
        "action_item_event",
        "action_item",
        "review_item",
        "grade",
        "answer",
        "question",
        "quiz",
        "card",
        "topic_note",
        "topic",
    ]:
        op.drop_table(table)
    op.execute("DROP TABLE IF EXISTS ku_embedding")
    op.drop_table("knowledge_unit")
    op.execute("DROP TRIGGER IF EXISTS ku_operation_immutable ON ku_operation")
    op.execute("DROP FUNCTION IF EXISTS quizme_block_oplog_mutation")
    op.drop_table("ku_operation")
    op.drop_table("segment")
    op.drop_table("transcript")
    op.drop_table("recording")
