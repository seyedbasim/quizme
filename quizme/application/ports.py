"""Ports — the interfaces the application layer depends on (AD-11).

Adapters in ``quizme.adapters`` implement these. Every method that hits an
external service may raise a :class:`quizme.domain.errors.AdapterError` subclass.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from quizme.domain.action_items import ActionItem
from quizme.domain.ku import KnowledgeUnit, KUOperation
from quizme.domain.quiz import Grade, GradeValue
from quizme.domain.scheduling import Card


@runtime_checkable
class Clock(Protocol):
    def now(self) -> datetime: ...


# --------------------------------------------------------------------- transcription


@runtime_checkable
class Transcriber(Protocol):
    """Azure AI Speech (AD-13). Returns segments with timestamps (FR-3)."""

    def transcribe(self, *, blob_url: str, language: str) -> TranscriptResult: ...


class TranscriptResult(Protocol):
    text: str
    segments: Sequence[TranscriptSegment]


class TranscriptSegment(Protocol):
    start: float
    end: float
    text: str


# ---------------------------------------------------------------------------- LLM


@runtime_checkable
class LLM(Protocol):
    """Foundry chat deployment (AD-8, AD-13). ``stage`` selects the per-stage
    deployment override and is recorded on the ``llm_call`` row for spend
    accounting (FR-38)."""

    def complete_json(
        self,
        *,
        stage: str,
        prompt_version: str,
        system: str,
        user: str,
        schema: dict[str, Any],
        temperature: float = 0.0,
    ) -> LLMResult: ...


class LLMResult(Protocol):
    data: dict[str, Any]
    model: str
    input_tokens: int
    output_tokens: int
    est_cost_usd: float


@runtime_checkable
class Embedder(Protocol):
    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


# -------------------------------------------------------------------------- intake


@runtime_checkable
class RecordingIntake(Protocol):
    """Upload handler + Blob + Queue (AD-16). Used by the web process only."""

    def accept_upload(self, *, filename: str, content: bytes) -> AcceptedRecording:
        """Store to Blob, create the Recording row, enqueue. Idempotent on the
        content hash (FR-1) — a duplicate raises
        :class:`quizme.domain.errors.DuplicateRecording`."""
        ...

    def reenqueue(self, recording_id: str) -> None:
        """Put a parked Recording back on the ingest queue (FR-36)."""
        ...


class AcceptedRecording(Protocol):
    recording_id: str
    sha256: str
    blob_url: str


# --------------------------------------------------------------------------- store


Row = dict[str, Any]


@runtime_checkable
class Store(Protocol):
    """Postgres (+ pgvector) + Blob (AD-3, AD-9, AD-17). One coarse interface for
    v1; split per aggregate as it grows. Read helpers return plain ``dict`` rows."""

    # -- blob (AD-1) --
    def put_blob(self, container: str, key: str, data: bytes, *, overwrite: bool = True) -> str: ...
    def read_blob(self, container: str, key: str) -> bytes: ...
    def blob_url(self, container: str, key: str) -> str: ...

    # -- recordings / transcripts / segments (AD-1) --
    def recording_by_hash(self, sha256: str) -> Row | None: ...
    def add_recording(
        self, *, recording_id: str, upload_id: str, sha256: str, blob_key: str, filename: str, size: int
    ) -> None: ...
    def get_recording(self, recording_id: str) -> Row | None: ...
    def add_transcript(self, *, transcript_id: str, recording_id: str, blob_key: str, full_text: str) -> None: ...
    def get_transcript_by_recording(self, recording_id: str) -> Row | None: ...
    def add_segments(self, rows: Sequence[Row]) -> None: ...
    def get_segments(self, transcript_id: str) -> list[Row]: ...

    # -- topics / notes (AD-2) --
    def get_or_create_topic(self, label: str) -> str: ...
    def topic_labels(self, topic_ids: Sequence[str]) -> dict[str, str]: ...
    def get_topic_note(self, topic_id: str) -> Row | None: ...
    def set_topic_note(self, topic_id: str, *, markdown: str, prompt_version: str) -> None: ...

    # -- operation log / KB projection (AD-3) --
    def append_ops(self, ops: Sequence[KUOperation]) -> None: ...
    def load_kus(self) -> dict[str, KnowledgeUnit]: ...
    def upsert_ku_projection(self, kus: Sequence[KnowledgeUnit]) -> None: ...
    def nearest_kus(self, embedding: Sequence[float], *, k: int) -> list[KnowledgeUnit]: ...
    def kus_for_topic(self, topic_id: str) -> list[KnowledgeUnit]: ...
    def put_ku_embedding(self, ku_id: str, embedding: Sequence[float]) -> None: ...
    def contradicted_and_pending_ku_ids(self) -> set[str]: ...

    # -- idempotency ledger + run history (AD-4, FR-37) --
    def stage_done(self, *, input_hash: str, stage: str, stage_version: str) -> bool: ...
    def mark_stage_done(self, *, input_hash: str, stage: str, stage_version: str) -> None: ...
    def record_stage_run(self, row: Row) -> None: ...
    def ingestion_status(self, *, limit: int = 50) -> list[Row]: ...

    # -- scheduling (AD-9) --
    def get_card(self, ku_id: str) -> Card | None: ...
    def upsert_card(self, card: Card) -> None: ...
    def all_cards(self) -> list[Card]: ...

    # -- action items (AD-12) --
    def get_action_item(self, dedup_key: str) -> ActionItem | None: ...
    def upsert_action_item(self, item: ActionItem) -> None: ...
    def list_action_items(self, *, status: str | None = None, origin: str | None = None) -> list[ActionItem]: ...

    # -- review queue (FR-21) --
    def add_review_item(self, *, kind: str, ku_ids: Sequence[str], context: Row) -> None: ...
    def list_review_items(self, *, status: str = "open") -> list[Row]: ...
    def get_review_item(self, item_id: str) -> Row | None: ...
    def resolve_review_item(self, item_id: str, *, resolution: str) -> None: ...

    # -- quiz / question / answer / grade (FR-24..31) --
    def add_quiz(self, *, quiz_id: str, quiz_date: Any, ku_ids: Sequence[str]) -> None: ...
    def get_quiz_by_date(self, quiz_date: Any) -> Row | None: ...
    def add_questions(self, rows: Sequence[Row]) -> None: ...
    def get_question(self, question_id: str) -> Row | None: ...
    def quiz_questions(self, quiz_id: str) -> list[Row]: ...
    def record_answer(self, *, question_id: str, text: str) -> None: ...
    def record_grade(self, row: Row) -> None: ...
    def get_grade(self, question_id: str) -> Row | None: ...
    def mark_grade_disputed(self, question_id: str) -> None: ...
    def recent_grades_for_ku(self, ku_id: str, *, limit: int = 5) -> list[str]: ...

    # -- spend (FR-38) --
    def record_llm_call(self, row: Row) -> None: ...
    def month_spend_usd(self, *, year: int, month: int) -> float: ...

    # -- settings (FR-52) --
    def get_setting(self, key: str) -> Any: ...
    def set_setting(self, key: str, value: Any) -> None: ...


# ------------------------------------------------------------------------ delivery


@runtime_checkable
class Delivery(Protocol):
    """Telegram bot, webhook mode (AD-10). Carries Questions/Answers only."""

    def send_message(self, text: str) -> None: ...
    def send_question(self, *, question_id: str, prompt: str) -> None: ...
    def verify_webhook(self, *, secret_header: str, chat_id: int) -> bool: ...
    def enrol_chat(self, chat_id: int) -> None: ...


# --------------------------------------------------------------------------- misc


@runtime_checkable
class SpendMeter(Protocol):
    """FR-38 / FR-53 / AD-19."""

    def month_to_date_usd(self) -> float: ...
    def projected_month_end_usd(self) -> float: ...
    def is_throttled(self) -> bool: ...


class Grader(Protocol):
    def grade(self, *, answer_text: str, model_answer: str, ku_canonical: str) -> tuple[GradeValue, str]: ...


__all__ = [
    "AcceptedRecording",
    "Clock",
    "Delivery",
    "Embedder",
    "Grade",
    "Grader",
    "LLM",
    "LLMResult",
    "RecordingIntake",
    "SpendMeter",
    "Store",
    "Transcriber",
    "TranscriptResult",
    "TranscriptSegment",
]
