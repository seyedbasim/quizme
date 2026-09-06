"""Transcriber — Azure AI Speech, batch/fast transcription with the Whisper model
(AD-13). Available in ``southeastasia``; Azure OpenAI's Whisper deployment is not.

Batch transcription: submit a job pointing at the audio blob's SAS URL, poll,
fetch the result JSON (which carries word- and phrase-level offsets -> Segments
with start/end, FR-3).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class _Segment:
    start: float
    end: float
    text: str


@dataclass(slots=True)
class _Result:
    text: str
    segments: list[_Segment]


class AzureSpeechTranscriber:
    def __init__(self, *, speech_key: str, region: str, mode: str = "batch") -> None:
        self._key = speech_key
        self._region = region
        self._mode = mode

    def transcribe(self, *, blob_url: str, language: str) -> _Result:
        raise NotImplementedError(
            "AzureSpeechTranscriber.transcribe: POST to the batch transcription REST API "
            f"(region={self._region}) with contentUrls=[blob SAS url], locale=map(language), "
            "wordLevelTimestampsEnabled=true; poll status; GET results; map phrases -> _Segment. "
            "Raise TranscriptionError on failure."
        )
