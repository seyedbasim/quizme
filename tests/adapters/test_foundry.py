"""Integration tests for the Foundry LLM + Embedder adapters.

Run with:
  QUIZME_TEST_AOAI_ENDPOINT=https://aoai-quizme-96616d.openai.azure.com
  QUIZME_TEST_AOAI_KEY=<key>
"""

from __future__ import annotations

import os

import pytest

from quizme.application.config import EmbeddingsConfig, LLMConfig

_EP = os.environ.get("QUIZME_TEST_AOAI_ENDPOINT")
_KEY = os.environ.get("QUIZME_TEST_AOAI_KEY")
pytestmark = pytest.mark.skipif(not (_EP and _KEY), reason="set QUIZME_TEST_AOAI_ENDPOINT + _KEY")


class _Sink:
    def __init__(self) -> None:
        self.rows: list[dict] = []

    def record_llm_call(self, row: dict) -> None:
        self.rows.append(row)


def _llm_cfg() -> LLMConfig:
    return LLMConfig(endpoint=_EP, default_deployment="chat", api_version="2025-01-01-preview")


def test_llm_structured_output_and_spend_row() -> None:
    from quizme.adapters.llm_foundry import FoundryLLM

    sink = _Sink()
    llm = FoundryLLM(config=_llm_cfg(), sink=sink, api_key=_KEY)
    schema = {
        "type": "object",
        "properties": {"colour": {"type": "string"}, "count": {"type": "integer"}},
        "required": ["colour", "count"],
        "additionalProperties": False,
    }
    result = llm.complete_json(
        stage="test",
        prompt_version="t.v1",
        system="You output JSON matching the schema.",
        user="The bag holds 3 red apples. What colour and how many?",
        schema=schema,
    )
    assert result.data["colour"].lower() == "red"
    assert result.data["count"] == 3
    assert result.input_tokens > 0 and result.output_tokens > 0
    assert len(sink.rows) == 1
    assert sink.rows[0]["stage"] == "test" and sink.rows[0]["est_cost_usd"] >= 0


def test_embedder_dims() -> None:
    from quizme.adapters.embedder_foundry import FoundryEmbedder

    emb = FoundryEmbedder(
        embeddings=EmbeddingsConfig(deployment="embed", dimensions=1536),
        llm=_llm_cfg(),
        api_key=_KEY,
    )
    vs = emb.embed(["the mitochondrion is the powerhouse of the cell", "TCP uses a three-way handshake"])
    assert len(vs) == 2 and all(len(v) == 1536 for v in vs)
