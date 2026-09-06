"""Stage 6 — regenerate Topic Notes for changed Topics (FR-18).

A Topic Note is *always* regenerated from that Topic's live KUs and is never an
input to any other stage (AD-2). Idempotent given unchanged KUs + prompt version.

Prompt: ``quizme/prompts/topic_note.v1.md``.
"""

from __future__ import annotations

from collections.abc import Sequence

from quizme.application.deps import Deps
from quizme.application.pipeline import StageResult

STAGE = "notes"
STAGE_VERSION = "2026-09-06.1"
PROMPT_VERSION = "topic_note.v1"


def run(recording_id: str, deps: Deps, changed_topic_ids: Sequence[str] | None = None) -> StageResult:
    raise NotImplementedError(
        "notes: for each changed topic -> load its live KUs, "
        "deps.llm.complete_json(stage='notes', ...), store the regenerated markdown "
        "Topic Note with a link list of its Sources (FR-18)."
    )
