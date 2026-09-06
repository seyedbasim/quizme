"""The queue worker — drains ``ingest`` and runs the pipeline (AD-16).

Storage Queue delivers *at least once* (Consistency Conventions → "Queue
handling"), so ``handle_message`` must be idempotent on ``recording_id``: each
stage checks the processed-ledger before doing work (AD-4). A poison message
dead-letters after N dequeues.

Runs as the queue-triggered function in ``functions/``.
"""

from __future__ import annotations

import logging

from quizme.application.deps import Deps
from quizme.application.pipeline import consolidate, extract, followups, notes, project, transcribe
from quizme.application.pipeline import filter as filter_stage

log = logging.getLogger("quizme.worker")

# Ordered pipeline. followups runs after extract off the same Segments.
_STAGES = [transcribe, filter_stage, extract, followups, consolidate, project, notes]


def handle_message(recording_id: str, deps: Deps) -> None:
    """Process one Recording end to end. Safe to call repeatedly (AD-4)."""
    if deps.spend.is_throttled():
        # AD-19 / FR-53 — hold new ingestion; the message stays on the queue
        # (raise so it is retried after visibility timeout) or is re-enqueued
        # with a delay by the function host.
        log.warning("spend throttled — deferring recording %s", recording_id)
        raise _Deferred(recording_id)

    for stage in _STAGES:
        input_hash = _stage_input_hash(recording_id, stage.STAGE)
        if deps.store.stage_done(input_hash=input_hash, stage=stage.STAGE, stage_version=stage.STAGE_VERSION):
            log.info("skip %s for %s (already done)", stage.STAGE, recording_id)
            continue

        result = stage.run(recording_id, deps)  # each stage marks itself done on success
        log.info("stage %s recording %s ok=%s detail=%s", stage.STAGE, recording_id, result.ok, result.detail)
        if not result.ok:
            raise RuntimeError(f"stage {stage.STAGE} failed for {recording_id}")


class _Deferred(Exception):
    """Signals the function host to leave the message for a later, un-throttled run."""


def _stage_input_hash(recording_id: str, stage: str) -> str:
    # Placeholder: real impl hashes the stage's actual input (transcript bytes,
    # segment set, etc.) not just the id — see AD-4.
    return f"{recording_id}:{stage}"
