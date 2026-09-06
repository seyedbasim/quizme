"""The ingestion pipeline — pipes-and-filters, each stage idempotent (AD-4).

Order (architecture-spine → Ingestion pipeline diagram):

    transcribe -> filter -> extract -> (followups) -> consolidate -> project -> notes

Each stage exposes ``run(recording_id, deps) -> StageResult`` and a
``STAGE_VERSION`` string. Bumping ``STAGE_VERSION`` (prompt/model/logic change) is
the only way to force reprocessing (AD-4). ``deps`` is the composed
:class:`quizme.application.deps.Deps` bundle.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class StageResult:
    stage: str
    recording_id: str
    ok: bool
    skipped: bool = False  # idempotency no-op
    detail: dict[str, Any] = field(default_factory=dict)
