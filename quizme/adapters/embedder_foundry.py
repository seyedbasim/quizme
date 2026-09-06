"""Embedder — a Foundry text-embedding deployment (AD-13). Vectors land in
Postgres ``pgvector`` via the Store. Local model is the AD-18 fallback.
"""

from __future__ import annotations

from collections.abc import Sequence

from quizme.application.config import EmbeddingsConfig


class FoundryEmbedder:
    def __init__(self, *, config: EmbeddingsConfig, endpoint: str, credential: object) -> None:
        self._config = config
        self._endpoint = endpoint
        self._credential = credential

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        raise NotImplementedError(
            "FoundryEmbedder.embed: client.embeddings.create(model=config.deployment, input=texts); "
            f"assert each vector has {self._config.dimensions} dims; return."
        )
