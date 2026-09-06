"""Transcriber — Azure AI Speech *fast transcription* (AD-13).

Synchronous REST call: POST the audio bytes + a definition JSON, get back
``combinedPhrases`` and per-phrase offsets. Available in ``southeastasia``;
Azure OpenAI's Whisper deployment is not.

The audio is pulled from Blob using the same credential (Managed Identity in
Azure, or a dev token).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import httpx

from quizme.domain.errors import TranscriptionError

_API_VERSION = "2024-11-15"
_LOCALE = {"en": "en-US"}


@dataclass(slots=True)
class SegmentImpl:
    start: float
    end: float
    text: str


@dataclass(slots=True)
class TranscriptResultImpl:
    text: str
    segments: list[SegmentImpl]


class AzureSpeechTranscriber:
    def __init__(
        self,
        *,
        region: str,
        api_key: str | None = None,
        credential: Any = None,
        blob_credential: Any = None,
    ) -> None:
        self._region = region
        self._api_key = api_key
        self._credential = credential
        self._blob_credential = blob_credential or credential
        self._base = f"https://{region}.api.cognitive.microsoft.com/speechtotext/transcriptions:transcribe"

    def transcribe(self, *, blob_url: str, language: str) -> TranscriptResultImpl:
        audio = self._download(blob_url)
        locale = _LOCALE.get(language, language)
        definition = {
            "locales": [locale],
            "profanityFilterMode": "None",
        }
        files = {
            "audio": ("audio", audio, "application/octet-stream"),
            "definition": (None, json.dumps(definition), "application/json"),
        }
        try:
            resp = httpx.post(
                self._base,
                params={"api-version": _API_VERSION},
                headers=self._auth_headers(),
                files=files,  # type: ignore[arg-type]
                timeout=600.0,
            )
            resp.raise_for_status()
            body = resp.json()
        except Exception as exc:  # noqa: BLE001
            raise TranscriptionError(f"fast transcription failed: {exc}") from exc

        phrases = body.get("phrases", [])
        segments = [
            SegmentImpl(
                start=p["offsetMilliseconds"] / 1000.0,
                end=(p["offsetMilliseconds"] + p["durationMilliseconds"]) / 1000.0,
                text=p["text"],
            )
            for p in phrases
        ]
        combined = body.get("combinedPhrases", [{}])
        text = combined[0].get("text", "") if combined else ""
        return TranscriptResultImpl(text=text, segments=segments)

    # ---------------------------------------------------------------- internals

    def _auth_headers(self) -> dict[str, str]:
        if self._api_key:
            return {"Ocp-Apim-Subscription-Key": self._api_key}
        from azure.identity import get_bearer_token_provider  # noqa: PLC0415

        provider = get_bearer_token_provider(self._credential, "https://cognitiveservices.azure.com/.default")
        return {"Authorization": f"Bearer {provider()}"}

    def _download(self, blob_url: str) -> bytes:
        from azure.storage.blob import BlobClient  # noqa: PLC0415

        try:
            if self._blob_credential is not None:
                client = BlobClient.from_blob_url(blob_url, credential=self._blob_credential)
            else:
                client = BlobClient.from_blob_url(blob_url)
            return client.download_blob().readall()
        except Exception as exc:  # noqa: BLE001
            raise TranscriptionError(f"could not read audio blob: {exc}") from exc
