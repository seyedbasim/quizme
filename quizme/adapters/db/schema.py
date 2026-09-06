"""SQLAlchemy Core tables mirroring Alembic migration ``0001_initial``.

Only the tables the Store adapter reads/writes are fully defined; the rest exist
in the DB but aren't needed here yet.
"""

from __future__ import annotations

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    BigInteger,
    Column,
    DateTime,
    Float,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    Text,
)

metadata = MetaData()

_TS = DateTime(timezone=True)

recording = Table(
    "recording",
    metadata,
    Column("id", String, primary_key=True),
    Column("upload_id", String, nullable=False),
    Column("sha256", String(64), nullable=False, unique=True),
    Column("blob_key", String, nullable=False),
    Column("filename", String, nullable=False),
    Column("bytes", BigInteger, nullable=False),
    Column("created_at", _TS, nullable=False),
)

transcript = Table(
    "transcript",
    metadata,
    Column("id", String, primary_key=True),
    Column("recording_id", String, nullable=False, unique=True),
    Column("blob_key", String, nullable=False),
    Column("full_text", Text, nullable=False),
    Column("created_at", _TS, nullable=False),
)

segment = Table(
    "segment",
    metadata,
    Column("id", String, primary_key=True),
    Column("transcript_id", String, nullable=False),
    Column("start_s", Float, nullable=False),
    Column("end_s", Float, nullable=False),
    Column("text", Text, nullable=False),
    Column("label", String, nullable=False),
    Column("confidence", Float, nullable=False),
    Column("prompt_version", String, nullable=False),
)

ku_operation = Table(
    "ku_operation",
    metadata,
    Column("op_id", String, primary_key=True),
    Column("ts", _TS, nullable=False),
    Column("actor", String, nullable=False),
    Column("type", String, nullable=False),
    Column("ku_ids_in", JSON, nullable=False),
    Column("ku_id_out", String),
    Column("payload", JSON, nullable=False),
    Column("model", String),
    Column("prompt_version", String),
    Column("prompt_hash", String),
    Column("rationale", Text),
)

knowledge_unit = Table(
    "knowledge_unit",
    metadata,
    Column("id", String, primary_key=True),
    Column("canonical", Text, nullable=False),
    Column("alt_phrasings", JSON, nullable=False),
    Column("topic_ids", JSON, nullable=False),
    Column("sources", JSON, nullable=False),
    Column("status", String, nullable=False),
    Column("superseded_by", String),
    Column("created_at", _TS, nullable=False),
    Column("updated_at", _TS, nullable=False),
)

ku_embedding = Table(
    "ku_embedding",
    metadata,
    Column("ku_id", String, primary_key=True),
    Column("embedding", Vector(1536)),
)

card = Table(
    "card",
    metadata,
    Column("ku_id", String, primary_key=True),
    Column("due", _TS, nullable=False),
    Column("stability", Float, nullable=False),
    Column("difficulty", Float, nullable=False),
    Column("step", Integer, nullable=False),
    Column("reps", Integer, nullable=False),
    Column("lapses", Integer, nullable=False),
    Column("last_review", _TS),
    Column("state", String, nullable=False),
)

review_item = Table(
    "review_item",
    metadata,
    Column("id", String, primary_key=True),
    Column("kind", String, nullable=False),
    Column("ku_ids", JSON, nullable=False),
    Column("context", JSON, nullable=False),
    Column("status", String, nullable=False, server_default="open"),
    Column("created_at", _TS, nullable=False),
    Column("resolved_at", _TS),
    Column("resolution", String),
)

action_item = Table(
    "action_item",
    metadata,
    Column("id", String, primary_key=True),
    Column("origin", String, nullable=False),
    Column("status", String, nullable=False),
    Column("dedup_key", String, nullable=False, unique=True),
    Column("trigger_text", Text, nullable=False),
    Column("sources", JSON, nullable=False),
    Column("trigger_count", Integer, nullable=False, server_default="1"),
    Column("ku_id", String),
    Column("topic_id", String),
    Column("revisit_at", _TS),
    Column("created_at", _TS, nullable=False),
    Column("updated_at", _TS, nullable=False),
    Column("resolved_at", _TS),
    Column("resolution", String),
)

processed_ledger = Table(
    "processed_ledger",
    metadata,
    Column("input_hash", String, primary_key=True),
    Column("stage", String, primary_key=True),
    Column("stage_version", String, primary_key=True),
    Column("done_at", _TS, nullable=False),
)

stage_run = Table(
    "stage_run",
    metadata,
    Column("id", String, primary_key=True),
    Column("recording_id", String, nullable=False),
    Column("stage", String, nullable=False),
    Column("status", String, nullable=False),
    Column("attempts", Integer, nullable=False, server_default="1"),
    Column("traceback", Text),
    Column("run_id", String, nullable=False),
    Column("started_at", _TS, nullable=False),
    Column("finished_at", _TS),
)

llm_call = Table(
    "llm_call",
    metadata,
    Column("id", String, primary_key=True),
    Column("ts", _TS, nullable=False),
    Column("stage", String, nullable=False),
    Column("prompt_version", String, nullable=False),
    Column("prompt_hash", String, nullable=False),
    Column("model", String, nullable=False),
    Column("input_tokens", Integer, nullable=False),
    Column("output_tokens", Integer, nullable=False),
    Column("latency_ms", Integer, nullable=False),
    Column("est_cost_usd", Numeric(10, 5), nullable=False),
)

app_setting = Table(
    "app_setting",
    metadata,
    Column("key", String, primary_key=True),
    Column("value", JSON, nullable=False),
    Column("updated_at", _TS, nullable=False),
)
