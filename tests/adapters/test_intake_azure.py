"""Integration test for AzureRecordingIntake — the ingestion front door (AD-16).

Run with QUIZME_TEST_DATABASE_URL + QUIZME_TEST_BLOB_URL + QUIZME_TEST_QUEUE_URL
and an identity (az login) holding Storage Blob/Queue Data Contributor.
"""

from __future__ import annotations

import base64
import json
import os
import uuid

import pytest

_DSN = os.environ.get("QUIZME_TEST_DATABASE_URL")
_BLOB = os.environ.get("QUIZME_TEST_BLOB_URL")
_QUEUE = os.environ.get("QUIZME_TEST_QUEUE_URL")
pytestmark = pytest.mark.skipif(
    not (_DSN and _BLOB and _QUEUE), reason="set QUIZME_TEST_DATABASE_URL/_BLOB_URL/_QUEUE_URL"
)


@pytest.fixture
def store():
    from quizme.adapters.store_postgres import PostgresStore

    st = PostgresStore(_DSN)
    st.wipe_all()
    yield st
    st.wipe_all()
    st.dispose()


def _drain_queue():
    from azure.identity import DefaultAzureCredential
    from azure.storage.queue import QueueClient

    qc = QueueClient(_QUEUE, queue_name="ingest", credential=DefaultAzureCredential())
    msgs = []
    for m in qc.receive_messages(max_messages=32):
        msgs.append(json.loads(base64.b64decode(m.content)))
        qc.delete_message(m)
    return msgs


def test_upload_dedup_and_enqueue(store) -> None:
    from quizme.adapters.intake_azure import AzureRecordingIntake
    from quizme.domain.errors import DuplicateRecording

    _drain_queue()
    from azure.identity import DefaultAzureCredential

    intake = AzureRecordingIntake(
        blob_account_url=_BLOB, queue_account_url=_QUEUE, store=store, credential=DefaultAzureCredential()
    )
    content = f"fake-audio-{uuid.uuid4()}".encode()

    accepted = intake.accept_upload(filename="memo.m4a", content=content)
    assert accepted.recording_id
    row = store.get_recording(accepted.recording_id)
    assert row is not None and row["sha256"] == accepted.sha256 and row["filename"] == "memo.m4a"

    msgs = _drain_queue()
    assert {"recording_id": accepted.recording_id} in msgs

    with pytest.raises(DuplicateRecording):
        intake.accept_upload(filename="memo-again.m4a", content=content)
