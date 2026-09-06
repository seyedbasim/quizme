"""Ports — the interfaces the application layer depends on (AD-11).

Adapters in ``quizme.adapters`` implement these. Every method that hits an
external service may raise a :class:`quizme.domain.errors.AdapterError` subclass.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol, runtime_checkable

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
        schema: dict,
        temperature: float = 0.0,
    ) -> LLMResult: ...


class LLMResult(Protocol):
    data: dict
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


class AcceptedRecording(Protocol):
    recording_id: str
    sha256: str
    blob_url: str


# --------------------------------------------------------------------------- store


@runtime_checkable
class Store(Protocol):
    """Postgres (+ pgvector) + Blob (AD-3, AD-9, AD-17). One coarse interface for
    the scaffold; split per aggregate as it grows."""

    # -- operation log / KB projection (AD-3) --
    def append_ops(self, ops: Sequence[KUOperation]) -> None: ...
    def load_kus(self) -> dict[str, KnowledgeUnit]: ...
    def nearest_kus(self, embedding: Sequence[float], *, k: int) -> list[KnowledgeUnit]: ...
    def put_ku_embedding(self, ku_id: str, embedding: Sequence[float]) -> None: ...

    # -- idempotency ledger (AD-4) --
    def stage_done(self, *, input_hash: str, stage: str, stage_version: str) -> bool: ...
    def mark_stage_done(self, *, input_hash: str, stage: str, stage_version: str) -> None: ...

    # -- scheduling (AD-9) --
    def get_card(self, ku_id: str) -> Card | None: ...
    def upsert_card(self, card: Card) -> None: ...
    def all_cards(self) -> list[Card]: ...

    # -- action items (AD-12) --
    def get_action_item(self, dedup_key: str) -> ActionItem | None: ...
    def upsert_action_item(self, item: ActionItem) -> None: ...

    # -- review queue (FR-21) --
    def add_review_item(self, *, kind: str, ku_ids: Sequence[str], context: dict) -> None: ...

    # -- spend (FR-38) --
    def record_llm_call(self, row: dict) -> None: ...
    def month_spend_usd(self, *, year: int, month: int) -> float: ...


# ------------------------------------------------------------------------ delivery


@runtime_checkable
class Delivery(Protocol):
    """Telegram bot, webhook mode (AD-10). Carries Questions/Answers only."""

    def send_message(self, text: str) -> None: ...
    def send_question(self, *, question_id: str, prompt: str) -> None: ...


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
