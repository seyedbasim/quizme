"""Stage 1 — transcription (FR-3).

Reads the immutable audio blob, calls the Transcriber (Azure AI Speech), stores
the Transcript immutably (AD-1) linked to the Recording.
"""

from __future__ import annotations

from quizme.application.deps import Deps
from quizme.application.pipeline import StageResult

STAGE = "transcribe"
STAGE_VERSION = "2026-09-06.1"


def run(recording_id: str, deps: Deps) -> StageResult:
    raise NotImplementedError(
        "transcribe: load blob_url for recording, "
        "deps.transcriber.transcribe(blob_url=..., language=deps.config.ingest.language), "
        "persist Transcript + Segments (with start/end), mark_stage_done (AD-4)."
    )
