"""Stage 5 — project the operation log into the live KB (FR-17).

Thin: ``domain.ku.fold`` does the work. This stage refreshes any materialised
projection (a ``knowledge_unit`` table kept in sync for fast browsing) and records
which Topics changed so ``notes.run`` knows what to regenerate.
"""

from __future__ import annotations

from quizme.application.deps import Deps
from quizme.application.pipeline import StageResult

STAGE = "project"
STAGE_VERSION = "2026-09-06.1"


def run(recording_id: str, deps: Deps) -> StageResult:
    raise NotImplementedError(
        "project: kus = domain.ku.fold(store.iter_ops()); upsert the materialised "
        "knowledge_unit rows; return the set of changed topic_ids in detail."
    )
