"""Stage 3 — atomic knowledge extraction (FR-8..FR-10).

From ``study`` Segments, produce KnowledgeUnits: one claim each, a stand-alone
canonical phrasing, >=1 SourceRef, >=1 candidate Topic. Segments with no factual
content yield zero KUs. Low-confidence extractions go to the Review Queue (FR-10),
not straight into the KB.

Emits ``(new_kus, )``; the follow-up scan is a sibling stage
(:mod:`quizme.application.pipeline.followups`) driven off the same Segments.

Prompt: ``quizme/prompts/extract.v1.md``.
"""

from __future__ import annotations

from quizme.application.deps import Deps
from quizme.application.pipeline import StageResult

STAGE = "extract"
STAGE_VERSION = "2026-09-06.1"
PROMPT_VERSION = "extract.v1"


def run(recording_id: str, deps: Deps) -> StageResult:
    raise NotImplementedError(
        "extract: for each study Segment call deps.llm.complete_json(stage='extract', ...); "
        "build KnowledgeUnit objects (domain.ku.KnowledgeUnit) with SourceRef spans; "
        "hand off to consolidate.run; route low-confidence KUs to the Review Queue (FR-10)."
    )
