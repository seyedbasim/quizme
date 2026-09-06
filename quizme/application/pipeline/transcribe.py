"""Stage 1 — transcription (FR-3).

Reads the immutable audio blob, calls the Transcriber (Azure AI Speech), stores
the Transcript (full text in Postgres, phrase timings in Blob) linked to the
Recording. All immutable (AD-1).
"""

from __future__ import annotations

import json
from typing import Any

from quizme.application.deps import Deps
from quizme.domain.errors import TranscriptionError
from quizme.domain.ids import new_id

STAGE = "transcribe"
STAGE_VERSION = "2026-09-06.1"


def run(recording_id: str, deps: Deps) -> dict[str, Any]:
    rec = deps.store.get_recording(recording_id)
    if rec is None:
        raise TranscriptionError(f"no recording {recording_id}")

    blob_url = deps.store.blob_url("recordings", rec["sha256"])
    result = deps.transcriber.transcribe(blob_url=blob_url, language=deps.config.ingest.language)

    phrases = [{"start": seg.start, "end": seg.end, "text": seg.text} for seg in result.segments]
    payload = json.dumps({"text": result.text, "phrases": phrases}).encode()
    key = f"{recording_id}.json"
    deps.store.put_blob("transcripts", key, payload)

    deps.store.add_transcript(
        transcript_id=new_id(),
        recording_id=recording_id,
        blob_key=f"transcripts/{key}",
        full_text=result.text,
    )
    return {"chars": len(result.text), "phrases": len(phrases)}
