"""Store — Azure Database for PostgreSQL Flexible Server (+ pgvector) and Blob
(AD-3, AD-9, AD-17).

The one adapter that touches the most surface. Split into per-aggregate stores as
it grows; kept as one class in the scaffold to match ``ports.Store``.

* op-log: ``ku_operation`` is append-only (no UPDATE/DELETE). ``knowledge_unit`` is
  a materialised projection kept in sync by ``pipeline.project`` — the log is the
  source of truth (AD-3).
* vectors: ``ku_embedding(ku_id, embedding vector(N))`` with an HNSW index.
* idempotency: ``processed_ledger(input_hash, stage, stage_version)`` (AD-4).
* scheduling: ``card`` keyed by ``ku_id`` (AD-9).
* spend: ``llm_call`` rows roll up into ``spend_month`` (FR-38).

Prefer Entra token auth to Postgres (no password in Key Vault).
"""

from __future__ import annotations

from collections.abc import Sequence

from quizme.domain.action_items import ActionItem
from quizme.domain.ku import KnowledgeUnit, KUOperation
from quizme.domain.scheduling import Card


class PostgresStore:
    def __init__(self, *, dsn: str, blob_account_url: str, credential: object) -> None:
        self._dsn = dsn
        self._blob_account_url = blob_account_url
        self._credential = credential
        # engine = create_engine(dsn); register pgvector

    # -- op log / KB projection -------------------------------------------------
    def append_ops(self, ops: Sequence[KUOperation]) -> None:
        raise NotImplementedError("INSERT into ku_operation (append-only)")

    def load_kus(self) -> dict[str, KnowledgeUnit]:
        raise NotImplementedError("read ku_operation ordered by ts -> domain.ku.fold(...)")

    def nearest_kus(self, embedding: Sequence[float], *, k: int) -> list[KnowledgeUnit]:
        raise NotImplementedError("SELECT ... ORDER BY embedding <=> :q LIMIT :k (pgvector)")

    def put_ku_embedding(self, ku_id: str, embedding: Sequence[float]) -> None:
        raise NotImplementedError("UPSERT ku_embedding")

    # -- idempotency ----------------------------------------------------------
    def stage_done(self, *, input_hash: str, stage: str, stage_version: str) -> bool:
        raise NotImplementedError("SELECT 1 FROM processed_ledger WHERE ...")

    def mark_stage_done(self, *, input_hash: str, stage: str, stage_version: str) -> None:
        raise NotImplementedError("INSERT INTO processed_ledger ON CONFLICT DO NOTHING")

    # -- scheduling ---------------------------------------------------------
    def get_card(self, ku_id: str) -> Card | None:
        raise NotImplementedError

    def upsert_card(self, card: Card) -> None:
        raise NotImplementedError

    def all_cards(self) -> list[Card]:
        raise NotImplementedError

    # -- action items -----------------------------------------------------
    def get_action_item(self, dedup_key: str) -> ActionItem | None:
        raise NotImplementedError

    def upsert_action_item(self, item: ActionItem) -> None:
        raise NotImplementedError("INSERT ... ON CONFLICT (dedup_key) DO UPDATE (AD-12)")

    # -- review queue -----------------------------------------------------
    def add_review_item(self, *, kind: str, ku_ids: Sequence[str], context: dict) -> None:
        raise NotImplementedError

    # -- spend ----------------------------------------------------------
    def record_llm_call(self, row: dict) -> None:
        raise NotImplementedError

    def month_spend_usd(self, *, year: int, month: int) -> float:
        raise NotImplementedError("SELECT coalesce(sum(est_cost_usd),0) FROM llm_call WHERE ...")
