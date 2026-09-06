"""Stage 3 — atomic knowledge extraction (FR-8..10), then consolidation.

From ``study`` segments, the LLM (prompt ``extract.v1``) produces atomic
KnowledgeUnits — one claim each, a stand-alone canonical phrasing, >=1 SourceRef,
candidate Topic labels. High-confidence units go to the Consolidation Engine
(:mod:`quizme.application.pipeline.consolidate`); low-confidence units are created
as ``PENDING_REVIEW`` with a Review Queue item (FR-10).
"""

from __future__ import annotations

from typing import Any

from quizme.application.deps import Deps
from quizme.application.pipeline import consolidate
from quizme.application.prompts import load
from quizme.domain.errors import QuizmeError
from quizme.domain.ids import new_id
from quizme.domain.ku import KnowledgeUnit, KUStatus, SourceRef

STAGE = "extract"
STAGE_VERSION = "2026-09-06.1"

# a segment at/above this filter confidence is treated as solid `study` content
_STUDY_CONF = 0.4
# an extracted unit below this confidence is routed to review (FR-10)
_UNIT_CONF = 0.6


def run(recording_id: str, deps: Deps) -> dict[str, Any]:
    tr = deps.store.get_transcript_by_recording(recording_id)
    if tr is None:
        raise QuizmeError(f"no transcript for {recording_id}")
    segments = [
        s
        for s in deps.store.get_segments(tr["id"])
        if s["label"] == "study" or s["confidence"] < _STUDY_CONF  # FR-7: keep borderline
    ]

    prompt = load("extract.v1")
    now = deps.clock.now()
    solid: list[KnowledgeUnit] = []
    pending = 0

    for seg in segments:
        result = deps.llm.complete_json(
            stage="extract",
            prompt_version=prompt.version,
            system=prompt.system,
            user=prompt.render(segment_text=seg["text"]),
            schema=prompt.schema,
        )
        for u in result.data["units"]:
            topic_ids = tuple(deps.store.get_or_create_topic(t) for t in u["topics"])
            src = SourceRef(recording_id, float(u["source"]["start"]), float(u["source"]["end"]))
            ku = KnowledgeUnit(
                id=new_id(),
                canonical=u["canonical"].strip(),
                topic_ids=topic_ids,
                sources=(src,),
                alt_phrasings=tuple(u.get("alt_phrasings", ())),
                created_at=now,
                updated_at=now,
                status=KUStatus.ACTIVE,
            )
            if float(u["confidence"]) >= _UNIT_CONF:
                solid.append(ku)
            else:
                consolidate.create_pending(ku, deps, reason=f"extraction confidence {u['confidence']}")
                pending += 1

    stats = consolidate.consolidate_batch(solid, deps)
    return {"segments": len(segments), "extracted": len(solid), "pending_review": pending, **stats}
