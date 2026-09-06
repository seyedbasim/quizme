"""The ingestion pipeline — pipes-and-filters, each stage idempotent (AD-4).

Order (architecture-spine → Ingestion pipeline diagram):

    transcribe -> filter -> extract (+consolidate) -> followups -> project -> notes

Each stage module exposes ``STAGE``, ``STAGE_VERSION`` and
``run(recording_id, deps) -> dict`` (returns a detail dict, raises on failure).
:func:`execute` wraps a stage with the idempotency ledger + a ``stage_run`` row.
Bumping ``STAGE_VERSION`` (prompt/model/logic change) is the only way to force
reprocessing (AD-4).
"""

from __future__ import annotations

import logging
import traceback
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import ModuleType
from typing import Any

from quizme.application.deps import Deps
from quizme.domain.ids import new_id, text_hash

log = logging.getLogger("quizme.pipeline")


@dataclass(slots=True)
class StageResult:
    stage: str
    recording_id: str
    ok: bool
    skipped: bool = False
    detail: dict[str, Any] = field(default_factory=dict)


def stage_input_hash(recording_id: str, stage: str) -> str:
    """v1: per-recording-per-stage. Combined with ``STAGE_VERSION`` in the ledger
    this gives 'skip if already done, redo when the stage logic changes' (AD-4).
    A finer hash (transcript bytes, segment set) is a later refinement."""
    return text_hash(f"{recording_id}::{stage}")


def execute(module: ModuleType, recording_id: str, deps: Deps) -> StageResult:
    stage: str = module.STAGE
    version: str = module.STAGE_VERSION
    ihash = stage_input_hash(recording_id, stage)

    if deps.store.stage_done(input_hash=ihash, stage=stage, stage_version=version):
        return StageResult(stage, recording_id, ok=True, skipped=True)

    run_id = new_id()
    started = datetime.now(UTC)
    try:
        detail = module.run(recording_id, deps)
    except Exception:
        deps.store.record_stage_run(
            {
                "recording_id": recording_id,
                "stage": stage,
                "status": "failed",
                "traceback": traceback.format_exc()[-4000:],
                "run_id": run_id,
                "started_at": started,
                "finished_at": datetime.now(UTC),
            }
        )
        log.exception("stage %s failed for %s", stage, recording_id)
        raise

    deps.store.mark_stage_done(input_hash=ihash, stage=stage, stage_version=version)
    deps.store.record_stage_run(
        {
            "recording_id": recording_id,
            "stage": stage,
            "status": "ok",
            "traceback": None,
            "run_id": run_id,
            "started_at": started,
            "finished_at": datetime.now(UTC),
        }
    )
    return StageResult(stage, recording_id, ok=True, detail=detail or {})
