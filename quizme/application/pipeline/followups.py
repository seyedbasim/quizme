"""Stage 3b — follow-up intent detection (FR-40).

Scans ``study`` segments (prompt ``followups.v1``) for the user saying they need
to check / verify / research something later. Each becomes a ``follow_up`` Action
Item via ``upsert`` on ``followup_key`` (AD-12, FR-42). Sub-threshold detections
go to the Review Queue (FR-40).
"""

from __future__ import annotations

from typing import Any

from quizme.application.deps import Deps
from quizme.application.prompts import load
from quizme.domain.action_items import Origin, followup_key, upsert
from quizme.domain.errors import QuizmeError
from quizme.domain.ku import SourceRef

STAGE = "followups"
STAGE_VERSION = "2026-09-06.1"


def run(recording_id: str, deps: Deps) -> dict[str, Any]:
    tr = deps.store.get_transcript_by_recording(recording_id)
    if tr is None:
        raise QuizmeError(f"no transcript for {recording_id}")
    segments = [s for s in deps.store.get_segments(tr["id"]) if s["label"] == "study"]
    if not segments:
        return {"followups": 0, "to_review": 0}

    prompt = load("followups.v1")
    threshold = deps.config.review.followup_confidence_threshold
    now = deps.clock.now()
    created = to_review = 0

    for seg in segments:
        result = deps.llm.complete_json(
            stage="followups",
            prompt_version=prompt.version,
            system=prompt.system,
            user=prompt.render(segment_text=seg["text"]),
            schema=prompt.schema,
        )
        for f in result.data["followups"]:
            src = SourceRef(recording_id, float(f["source"]["start"]), float(f["source"]["end"]))
            topic_label = f.get("topic")
            topic_id = deps.store.get_or_create_topic(topic_label) if topic_label else None

            if float(f["confidence"]) < threshold:
                deps.store.add_review_item(
                    kind="uncertain_followup",
                    ku_ids=[],
                    context={"intent": f["intent"], "quote": f["quote"], "confidence": f["confidence"]},
                )
                to_review += 1
                continue

            key = followup_key(topic_id, f["intent"])
            item = upsert(
                deps.store.get_action_item(key),
                origin=Origin.FOLLOW_UP,
                dedup_key=key,
                trigger_text=f["quote"],
                now=now,
                sources=(src,),
                topic_id=topic_id,
            )
            deps.store.upsert_action_item(item)
            created += 1

    return {"followups": created, "to_review": to_review}
