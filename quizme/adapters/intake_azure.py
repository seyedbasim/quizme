"""RecordingIntake — upload handler + Blob + Queue (AD-16).

Acceptance boundary (all must succeed before the web request returns):
1. compute sha256; if a Recording with that hash exists → raise
   :class:`DuplicateRecording` (FR-1);
2. upload the bytes to Blob at ``recordings/<sha256>`` with ``overwrite=False``
   (immutable — AD-1);
3. INSERT the ``recording`` row;
4. enqueue ``{"recording_id": ...}`` on the ``ingest`` queue.

After step 4 the file survives a worker outage.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any

from quizme.domain.errors import AdapterError, DuplicateRecording
from quizme.domain.ids import new_id, sha256_hex

_CONTAINER = "recordings"
_QUEUE = "ingest"


@dataclass(slots=True)
class AcceptedRecordingImpl:
    recording_id: str
    sha256: str
    blob_url: str


class AzureRecordingIntake:
    def __init__(
        self,
        *,
        blob_account_url: str,
        queue_account_url: str,
        store: Any,
        credential: Any,
    ) -> None:
        from azure.storage.blob import BlobServiceClient  # noqa: PLC0415
        from azure.storage.queue import QueueClient  # noqa: PLC0415

        self._store = store
        self._blob_svc = BlobServiceClient(blob_account_url, credential=credential)
        self._queue = QueueClient(queue_account_url, queue_name=_QUEUE, credential=credential)

    def accept_upload(self, *, filename: str, content: bytes) -> AcceptedRecordingImpl:
        from azure.core.exceptions import ResourceExistsError  # noqa: PLC0415

        sha = sha256_hex(content)
        blob_key = f"{_CONTAINER}/{sha}"
        existing = self._store.recording_by_hash(sha)
        if existing:
            raise DuplicateRecording(existing["id"], sha)

        blob = self._blob_svc.get_blob_client(container=_CONTAINER, blob=sha)
        try:
            blob.upload_blob(content, overwrite=False)
        except ResourceExistsError:
            # blob is there but no row — a prior crash between steps 2 and 3.
            # Fall through: (re)create the row and enqueue, keyed by the same hash.
            pass
        except Exception as exc:  # noqa: BLE001
            raise AdapterError(f"blob upload failed: {exc}") from exc

        recording_id = new_id()
        try:
            self._store.add_recording(
                recording_id=recording_id,
                upload_id=new_id(),
                sha256=sha,
                blob_key=blob_key,
                filename=filename,
                size=len(content),
            )
        except Exception as exc:  # noqa: BLE001
            # unique(sha256) violation → someone else won the race
            again = self._store.recording_by_hash(sha)
            if again:
                raise DuplicateRecording(again["id"], sha) from exc
            raise AdapterError(f"recording insert failed: {exc}") from exc

        try:
            body = base64.b64encode(json.dumps({"recording_id": recording_id}).encode()).decode()
            self._queue.send_message(body)
        except Exception as exc:  # noqa: BLE001
            raise AdapterError(f"queue enqueue failed: {exc}") from exc

        return AcceptedRecordingImpl(recording_id, sha, blob.url)

    def reenqueue(self, recording_id: str) -> None:
        body = base64.b64encode(json.dumps({"recording_id": recording_id}).encode()).decode()
        try:
            self._queue.send_message(body)
        except Exception as exc:  # noqa: BLE001
            raise AdapterError(f"reenqueue failed: {exc}") from exc
