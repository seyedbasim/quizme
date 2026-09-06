"""RecordingIntake — upload handler + Blob + Queue (AD-16).

Acceptance boundary (must all succeed before the web request returns):
1. stream bytes to Blob at ``recordings/<sha256>`` (immutable — AD-1);
2. compute sha256, INSERT the ``recording`` row (or detect the duplicate -> raise
   :class:`DuplicateRecording`, FR-1);
3. enqueue one ``ingest`` message ``{"recording_id": ...}``.

After step 3 the file is safe even if the worker is down.
"""

from __future__ import annotations

from dataclasses import dataclass

from quizme.domain.errors import AdapterError


@dataclass(slots=True)
class _Accepted:
    recording_id: str
    sha256: str
    blob_url: str


class AzureRecordingIntake:
    def __init__(self, *, blob_account_url: str, queue_account_url: str, store: object, credential: object) -> None:
        self._blob_account_url = blob_account_url
        self._queue_account_url = queue_account_url
        self._store = store
        self._credential = credential

    def accept_upload(self, *, filename: str, content: bytes) -> _Accepted:
        raise NotImplementedError(
            "AzureRecordingIntake.accept_upload: BlobServiceClient(credential=DefaultAzureCredential()); "
            "upload_blob(overwrite=False) keyed by sha256; INSERT recording ON CONFLICT (sha256) -> "
            "raise DuplicateRecording; QueueClient.send_message(json). Wrap SDK errors in AdapterError."
        )

    @staticmethod
    def _fail(exc: Exception) -> AdapterError:  # pragma: no cover
        return AdapterError(str(exc))
