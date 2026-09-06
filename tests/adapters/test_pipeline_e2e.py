"""End-to-end pipeline test: filter -> extract -> followups -> project -> notes,
against live Azure (Postgres + gpt-5-mini + embeddings). Transcribe is skipped
(no audio); the transcript is seeded directly.

Run with QUIZME_TEST_DATABASE_URL + QUIZME_TEST_AOAI_ENDPOINT + QUIZME_TEST_AOAI_KEY
+ QUIZME_TEST_BLOB_URL (needs az login with Storage Blob Data Contributor).
Costs a few cents in model calls.
"""

from __future__ import annotations

import json
import os

import pytest

from quizme.application.config import Config
from quizme.domain.ids import new_id

_DSN = os.environ.get("QUIZME_TEST_DATABASE_URL")
_EP = os.environ.get("QUIZME_TEST_AOAI_ENDPOINT")
_KEY = os.environ.get("QUIZME_TEST_AOAI_KEY")
_BLOB = os.environ.get("QUIZME_TEST_BLOB_URL")
pytestmark = pytest.mark.skipif(not (_DSN and _EP and _KEY and _BLOB), reason="needs live Azure env vars")

# a short study monologue: two solid claims + one 'check later'
_PHRASES = [
    {"start": 0.0, "end": 6.0, "text": "Okay so I'm looking at TCP retransmission timeouts today."},
    {
        "start": 6.0,
        "end": 14.0,
        "text": "The minimum RTO in RFC 6298 is one second, and the initial RTO before any measurement is also one second.",
    },
    {
        "start": 14.0,
        "end": 22.0,
        "text": "RTT is smoothed with an exponentially weighted moving average, the SRTT, using alpha of one eighth.",
    },
    {
        "start": 22.0,
        "end": 30.0,
        "text": "RTTVAR uses a beta of one quarter. TODO: I need to double-check the exact RTTVAR "
        "update formula in RFC 6298 and read the section on Karn's algorithm before the exam.",
    },
    {"start": 30.0, "end": 35.0, "text": "Anyway that's enough for now, going to grab a coffee."},
]


@pytest.fixture
def deps():
    from azure.identity import DefaultAzureCredential

    from quizme.adapters.embedder_foundry import FoundryEmbedder
    from quizme.adapters.llm_foundry import FoundryLLM
    from quizme.adapters.misc import LLMGrader, SystemClock
    from quizme.adapters.store_postgres import PostgresStore
    from quizme.application.deps import Deps

    cfg = Config()
    cfg.llm.endpoint = _EP
    cfg.llm.default_deployment = "gpt-5-mini"
    cfg.embeddings.deployment = "embed"

    store = PostgresStore(_DSN, blob_account_url=_BLOB, credential=DefaultAzureCredential())
    store.wipe_all()
    llm = FoundryLLM(config=cfg.llm, sink=store, api_key=_KEY)
    d = Deps(
        config=cfg,
        clock=SystemClock(),
        store=store,
        llm=llm,
        transcriber=None,  # type: ignore[arg-type]
        embedder=FoundryEmbedder(embeddings=cfg.embeddings, llm=cfg.llm, api_key=_KEY),
        intake=None,  # type: ignore[arg-type]
        delivery=None,  # type: ignore[arg-type]
        grader=LLMGrader(llm),
        spend=None,  # type: ignore[arg-type]
    )
    yield d
    store.wipe_all()
    store.dispose()


def test_pipeline_filter_to_notes(deps) -> None:
    from quizme.application.pipeline import execute, extract, followups, notes, project
    from quizme.application.pipeline import filter as filter_stage

    rid = new_id()
    sha = "0" * 64
    deps.store.add_recording(
        recording_id=rid,
        upload_id=new_id(),
        sha256=sha,
        blob_key=f"recordings/{sha}",
        filename="memo.m4a",
        size=1,
    )
    full = " ".join(p["text"] for p in _PHRASES)
    deps.store.put_blob("transcripts", f"{rid}.json", json.dumps({"text": full, "phrases": _PHRASES}).encode())
    deps.store.add_transcript(
        transcript_id=new_id(), recording_id=rid, blob_key=f"transcripts/{rid}.json", full_text=full
    )

    for stage in (filter_stage, extract, followups, project, notes):
        r = execute(stage, rid, deps)
        assert r.ok, r

    tr = deps.store.get_transcript_by_recording(rid)
    segs = deps.store.get_segments(tr["id"])
    assert segs and any(s["label"] == "study" for s in segs)

    # gpt-5-mini is non-deterministic — assert the pipeline produced usable KUs,
    # not exact wording.
    kus = [k for k in deps.store.load_kus().values() if k.quiz_eligible]
    assert len(kus) >= 1, [k.canonical for k in kus]
    blob = " ".join(k.canonical.lower() for k in kus)
    assert "rto" in blob or "timeout" in blob or "second" in blob or "srtt" in blob

    cards = deps.store.all_cards()
    assert len(cards) == len(kus)

    # the 'double-check RFC 6298 / read Karn's algorithm' line -> a follow-up,
    # either as an open Action Item or (if low confidence) a Review Queue item.
    from sqlalchemy import text

    with deps.store._engine.connect() as conn:  # noqa: SLF001
        ai = conn.execute(text("select count(*) from action_item where origin='follow_up'")).scalar()
        rq = conn.execute(text("select count(*) from review_item where kind='uncertain_followup'")).scalar()
    assert (ai or 0) + (rq or 0) >= 1, "expected a follow-up to be detected"

    # topic note generated for at least one topic
    topics = {t for k in kus for t in k.topic_ids}
    assert any(deps.store.get_topic_note(t) for t in topics)
