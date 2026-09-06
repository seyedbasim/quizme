"""Stage 2 — relevance filtering / segmentation (FR-5..FR-7).

Partitions the Transcript into Segments, each labelled ``study`` or ``noise`` with
a confidence. Every part of the transcript belongs to exactly one Segment (no
gaps/overlap). ``noise`` Segments are retained for audit (FR-6). Boundary cases
fall toward ``study`` and are flagged (FR-7).

Prompt: ``quizme/prompts/filter.v1.md``.
"""

from __future__ import annotations

from quizme.application.deps import Deps
from quizme.application.pipeline import StageResult

STAGE = "filter"
STAGE_VERSION = "2026-09-06.1"
PROMPT_VERSION = "filter.v1"


def run(recording_id: str, deps: Deps) -> StageResult:
    raise NotImplementedError(
        "filter: load Transcript, call deps.llm.complete_json(stage='filter', ...) "
        "over transcript chunks, persist Segments with label+confidence+prompt_version, "
        "route sub-threshold segments to the 'uncertain' view (FR-7)."
    )
