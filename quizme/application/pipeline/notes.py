"""Stage 6 — regenerate Topic Notes for changed Topics (FR-18).

A Topic Note is always regenerated from that Topic's live KUs and is never an
input to any other stage (AD-2). Idempotent: a Topic is skipped when its note is
newer than every KU in it and was made with the current prompt version.

Prompt: ``topic_note.v1``.
"""

from __future__ import annotations

from typing import Any

from quizme.application.deps import Deps
from quizme.application.prompts import load

STAGE = "notes"
STAGE_VERSION = "2026-09-06.1"


def run(recording_id: str, deps: Deps) -> dict[str, Any]:
    prompt = load("topic_note.v1")
    live = [ku for ku in deps.store.load_kus().values() if ku.quiz_eligible]
    by_topic: dict[str, list[Any]] = {}
    for ku in live:
        for tid in ku.topic_ids:
            by_topic.setdefault(tid, []).append(ku)

    labels = deps.store.topic_labels(list(by_topic))
    regenerated = skipped = 0

    for topic_id, kus in by_topic.items():
        note = deps.store.get_topic_note(topic_id)
        newest_ku = max(ku.updated_at for ku in kus)
        if note and note["prompt_version"] == prompt.version and note["regenerated_at"] >= newest_ku:
            skipped += 1
            continue

        units = "\n".join(
            f"- [{ku.id}] {ku.canonical}" + (f"  (also: {'; '.join(ku.alt_phrasings)})" if ku.alt_phrasings else "")
            for ku in kus
        )
        result = deps.llm.complete_json(
            stage="notes",
            prompt_version=prompt.version,
            system=prompt.system,
            user=prompt.render(topic_label=labels.get(topic_id, topic_id), units=units),
            schema=prompt.schema,
        )
        deps.store.set_topic_note(topic_id, markdown=result.data["markdown"], prompt_version=prompt.version)
        regenerated += 1

    return {"topics": len(by_topic), "regenerated": regenerated, "skipped": skipped}
