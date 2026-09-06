"""Typed error hierarchy.

Domain raises these; adapters translate vendor/SDK errors into them at the
boundary (architecture-spine → Consistency Conventions, "Error shape").
"""

from __future__ import annotations


class QuizmeError(Exception):
    """Base for every error Quizme raises deliberately."""


class ConfigError(QuizmeError):
    """Malformed or missing configuration."""


class ValidationError(QuizmeError):
    """A domain invariant was violated by caller input."""


class AdapterError(QuizmeError):
    """An adapter failed to talk to its backing service."""


class StorageError(AdapterError):
    """The Store adapter (Postgres / Blob) failed."""


class TranscriptionError(AdapterError):
    """The Transcriber adapter (Azure AI Speech) failed."""


class LLMError(AdapterError):
    """The LLM adapter (Foundry) failed or returned an unusable response."""


class DuplicateRecording(QuizmeError):
    """An upload's content hash matches a Recording we already have (FR-1)."""

    def __init__(self, recording_id: str, sha256: str) -> None:
        super().__init__(f"recording {recording_id} already has content {sha256[:12]}")
        self.recording_id = recording_id
        self.sha256 = sha256


class BudgetThrottled(QuizmeError):
    """Paid work is being held because projected spend is near the cap (AD-19, FR-53)."""
