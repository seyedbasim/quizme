"""Embedder — a Foundry text-embedding deployment (AD-13).

Same auth story as :mod:`quizme.adapters.llm_foundry` (Managed Identity, or an
API key for local dev). Vectors are stored in Postgres ``pgvector`` by the Store.
"""

from __future__ import annotations

from collections.abc import Sequence

from quizme.application.config import EmbeddingsConfig, LLMConfig
from quizme.domain.errors import LLMError


class FoundryEmbedder:
    def __init__(
        self,
        *,
        embeddings: EmbeddingsConfig,
        llm: LLMConfig,
        api_key: str | None = None,
    ) -> None:
        from quizme.adapters.llm_foundry import _make_client  # noqa: PLC0415

        self._deployment = embeddings.deployment
        self._dims = embeddings.dimensions
        # Embeddings may live on a different resource than chat (e.g. chat on an
        # AI Foundry resource, embeddings on the original Azure OpenAI one).
        client_cfg = llm.model_copy(
            update={
                "endpoint": embeddings.endpoint or llm.endpoint,
                "api_version": embeddings.api_version or llm.api_version,
            }
        )
        self._client = _make_client(client_cfg, api_key)

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            resp = self._client.embeddings.create(model=self._deployment, input=list(texts))
        except Exception as exc:  # noqa: BLE001
            raise LLMError(f"embeddings failed: {exc}") from exc
        vectors = [d.embedding for d in resp.data]
        for v in vectors:
            if len(v) != self._dims:
                raise LLMError(f"embedding dim {len(v)} != configured {self._dims}")
        return vectors
