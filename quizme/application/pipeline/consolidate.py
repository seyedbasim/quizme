"""Stage 4 — the Consolidation Engine (FR-11..FR-16).

For each new KU: embed it, retrieve the ``retrieval_neighbours`` nearest existing
KUs (AD-6 bound), ask the LLM for a per-pair verdict (FR-12), then run the pure
policy in :mod:`quizme.domain.consolidation` to turn verdicts into KU Operations
(AD-15). Append the ops to the log (AD-3); raise Review Queue items for contradictions
and sub-threshold proposed merges (AD-7).

Prompt: ``quizme/prompts/consolidate.v1.md``.
"""

from __future__ import annotations

from collections.abc import Sequence

from quizme.application.deps import Deps
from quizme.application.pipeline import StageResult
from quizme.domain.ku import KnowledgeUnit

STAGE = "consolidate"
STAGE_VERSION = "2026-09-06.1"
PROMPT_VERSION = "consolidate.v1"


def run(recording_id: str, deps: Deps, new_kus: Sequence[KnowledgeUnit] | None = None) -> StageResult:
    raise NotImplementedError(
        "consolidate: for each new KU -> deps.embedder.embed([ku.canonical]); "
        "deps.store.nearest_kus(emb, k=config.llm.consolidation.retrieval_neighbours); "
        "deps.llm.complete_json(stage='consolidate', ...) -> [PairJudgement]; "
        "domain.consolidation.plan_operations(...); deps.store.append_ops(plan.ops); "
        "for signal in plan.review_signals -> deps.store.add_review_item(...). "
        "NOTE: persist a `create` op for new_ku BEFORE any merge op that unions its "
        "sources, so fold() can resolve the loser id (see domain/consolidation.py)."
    )
