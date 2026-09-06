"""Stage 3b — follow-up intent detection (FR-40).

Scans ``study`` Segments for the user saying they need to check / verify /
research something later. Each becomes a ``follow_up`` Action Item via
``upsert`` on ``followup_key(topic_id, intent_text)`` (AD-12, FR-42). Sub-threshold
detections go to the Review Queue instead of the open list (FR-40).

Prompt: ``quizme/prompts/followups.v1.md``.
"""

from __future__ import annotations

from quizme.application.deps import Deps
from quizme.application.pipeline import StageResult

STAGE = "followups"
STAGE_VERSION = "2026-09-06.1"
PROMPT_VERSION = "followups.v1"


def run(recording_id: str, deps: Deps) -> StageResult:
    raise NotImplementedError(
        "followups: call deps.llm.complete_json(stage='followups', ...) over study Segments; "
        "for each detected intent above deps.config.review.followup_confidence_threshold, "
        "domain.action_items.upsert(existing=store.get_action_item(followup_key(...)), ...); "
        "below threshold -> store.add_review_item(kind='uncertain_followup', ...)."
    )
