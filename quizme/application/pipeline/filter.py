"""Stage 2 — relevance filtering / segmentation (FR-5..7).

Sends the timestamped transcript to the LLM (prompt ``filter.v1``), which returns
segments labelled ``study`` / ``noise`` with a confidence, and writes ``segment``
rows. Boundary cases fall toward ``study`` and are flagged (FR-7).

v1 sends the whole transcript in one call; chunking long recordings is a TODO.
"""

from __future__ import annotations

import json
from typing import Any

from quizme.application.deps import Deps
from quizme.application.prompts import load
from quizme.domain.errors import QuizmeError
from quizme.domain.ids import new_id

STAGE = "filter"
STAGE_VERSION = "2026-09-06.1"


def run(recording_id: str, deps: Deps) -> dict[str, Any]:
    tr = deps.store.get_transcript_by_recording(recording_id)
    if tr is None:
        raise QuizmeError(f"no transcript for {recording_id}")
    raw = json.loads(deps.store.read_blob("transcripts", f"{recording_id}.json"))
    phrases: list[dict[str, Any]] = raw["phrases"]
    if not phrases:
        return {"segments": 0, "study": 0}

    block = "\n".join(f"[{p['start']:.1f}-{p['end']:.1f}] {p['text']}" for p in phrases)
    prompt = load("filter.v1")
    result = deps.llm.complete_json(
        stage="filter",
        prompt_version=prompt.version,
        system=prompt.system,
        user=prompt.render(transcript=block),
        schema=prompt.schema,
    )

    rows = []
    for g in result.data["segments"]:
        rows.append(
            {
                "id": new_id(),
                "transcript_id": tr["id"],
                "start_s": float(g["start"]),
                "end_s": float(g["end"]),
                "text": _slice(phrases, float(g["start"]), float(g["end"])),
                "label": g["label"],
                "confidence": float(g["confidence"]),
                "prompt_version": prompt.version,
            }
        )
    deps.store.add_segments(rows)
    study = sum(1 for r in rows if r["label"] == "study")
    return {"segments": len(rows), "study": study, "noise": len(rows) - study}


def _slice(phrases: list[dict[str, Any]], start: float, end: float) -> str:
    """Join the phrases whose midpoint falls inside [start, end]."""
    picked = [p["text"] for p in phrases if start <= (p["start"] + p["end"]) / 2 <= end]
    return " ".join(picked).strip() or "".join(p["text"] for p in phrases if p["start"] < end and p["end"] > start)
