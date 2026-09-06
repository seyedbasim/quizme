"""The queue worker — drains ``ingest`` and runs the pipeline (AD-16).

Storage Queue delivers *at least once*, so ``handle_message`` is idempotent on
``recording_id``: :func:`quizme.application.pipeline.execute` checks the
processed-ledger before doing work (AD-4). A poison message dead-letters after N
dequeues (handled by the function host).

Runs as the queue-triggered function in ``functions/``.
"""

from __future__ import annotations

import logging

from quizme.application.deps import Deps
from quizme.application.pipeline import execute, extract, followups, notes, project, transcribe
from quizme.application.pipeline import filter as filter_stage

log = logging.getLogger("quizme.worker")

# `consolidate` is a helper invoked by `extract`, not a top-level stage.
_STAGES = [transcribe, filter_stage, extract, followups, project, notes]


class Deferred(Exception):
    """Signals the function host to leave the message for a later, un-throttled run."""


def handle_message(recording_id: str, deps: Deps) -> None:
    """Process one Recording end to end. Safe to call repeatedly (AD-4)."""
    if deps.spend.is_throttled():
        # AD-19 / FR-53 — hold new ingestion; keep the daily quiz running.
        log.warning("spend throttled — deferring recording %s", recording_id)
        raise Deferred(recording_id)

    for stage in _STAGES:
        result = execute(stage, recording_id, deps)
        log.info(
            "stage=%s recording=%s skipped=%s detail=%s",
            result.stage,
            recording_id,
            result.skipped,
            result.detail,
        )
