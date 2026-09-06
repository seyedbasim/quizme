"""AD-18 local re-host fallback stubs — Ollama / whisper.cpp / SQLite + sqlite-vec.

Not wired into the Azure deployment. Kept as one module so the seams the local
path needs are visible and never accidentally designed out. Install with the
``local`` extra: ``uv sync --extra local``.

Each class implements the same port as its Azure sibling.
"""

from __future__ import annotations

from collections.abc import Sequence


class OllamaLLM:
    """LLM port -> a local Ollama OpenAI-compatible endpoint (localhost:11434/v1)."""

    def complete_json(self, **kwargs: object) -> object:
        raise NotImplementedError("openai.OpenAI(base_url='http://localhost:11434/v1')")


class WhisperCppTranscriber:
    """Transcriber port -> faster-whisper / whisper.cpp locally."""

    def transcribe(self, *, blob_url: str, language: str) -> object:
        raise NotImplementedError("faster_whisper.WhisperModel('large-v3').transcribe(path)")


class SqliteStore:
    """Store port -> SQLite + sqlite-vec. Same op-log schema, portable dump."""

    def __getattr__(self, name: str) -> object:
        raise NotImplementedError(f"SqliteStore.{name}: mirror PostgresStore against sqlite + sqlite-vec")


class LocalEmbedder:
    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        raise NotImplementedError("sentence_transformers.SentenceTransformer('BAAI/bge-small-en-v1.5')")
