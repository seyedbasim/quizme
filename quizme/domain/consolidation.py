"""Consolidation policy — how an LLM's per-pair verdict becomes KU Operations.

Governing invariants:

* **AD-6** — scoped: this module only ever sees one new KU + its retrieval
  neighbours, or one Topic's KUs. It never loads the whole corpus.
* **AD-7** — a ``contradiction`` verdict never mutates a KU; it emits a
  ``flag_contradiction`` op and a Review Queue signal.
* **AD-15** — bias toward under-merging: ``duplicate`` / ``elaboration`` only
  auto-apply above ``merge_confidence_threshold``; below it the new KU is
  created and a low-priority Review item proposes the merge. An un-merged
  duplicate is cheap to fix later; an over-merge loses information.

The LLM call itself lives in ``application/pipeline/consolidate.py``; this module
is pure.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from quizme.domain.ids import new_id
from quizme.domain.ku import Actor, KnowledgeUnit, KUOperation, KUOpType


class Verdict(str, Enum):
    DUPLICATE = "duplicate"
    ELABORATION = "elaboration"
    CONTRADICTION = "contradiction"
    UNRELATED = "unrelated"


@dataclass(frozen=True, slots=True)
class PairJudgement:
    """One LLM verdict for ``(new_ku, existing_ku)`` (FR-12)."""

    existing_ku_id: str
    verdict: Verdict
    confidence: float
    rationale: str


@dataclass(frozen=True, slots=True)
class ConsolidationConfig:
    merge_confidence_threshold: float = 0.80


@dataclass(frozen=True, slots=True)
class ReviewSignal:
    """Emitted alongside ops; the caller turns it into a Review Queue item."""

    kind: str  # "proposed_merge" | "contradiction"
    ku_ids: tuple[str, ...]
    rationale: str


@dataclass(frozen=True, slots=True)
class ConsolidationPlan:
    ops: tuple[KUOperation, ...]
    review_signals: tuple[ReviewSignal, ...]


def plan_operations(
    new_ku: KnowledgeUnit,
    judgements: Sequence[PairJudgement],
    existing: dict[str, KnowledgeUnit],
    config: ConsolidationConfig,
    *,
    now: datetime,
    model: str,
    prompt_version: str,
    prompt_hash: str,
) -> ConsolidationPlan:
    """Turn the LLM's verdicts for one new KU into KU Operations (FR-11..FR-15).

    ``new_ku`` is assumed *not yet* in ``existing``. Exactly one of these happens:

    * a high-confidence ``duplicate`` / ``elaboration`` against the best match
      -> ``merge`` / ``elaborate`` into that survivor;
    * otherwise -> ``create`` the new KU, plus a ``proposed_merge`` review signal
      for any sub-threshold duplicate/elaboration, plus a ``flag_contradiction``
      op + signal for every contradiction.
    """
    ops: list[KUOperation] = []
    signals: list[ReviewSignal] = []

    def _op(op_type: KUOpType, ku_ids_in: tuple[str, ...], payload: dict[str, Any], rationale: str) -> KUOperation:
        return KUOperation(
            op_id=new_id(),
            ts=now,
            actor=Actor.ENGINE,
            type=op_type,
            ku_ids_in=ku_ids_in,
            payload=payload,
            model=model,
            prompt_version=prompt_version,
            prompt_hash=prompt_hash,
            rationale=rationale,
        )

    mergeable = [
        j
        for j in judgements
        if j.verdict in (Verdict.DUPLICATE, Verdict.ELABORATION)
        and j.confidence >= config.merge_confidence_threshold
        and j.existing_ku_id in existing
    ]
    best = max(mergeable, key=lambda j: j.confidence, default=None)

    if best is not None:
        survivor = existing[best.existing_ku_id]
        add_sources = [{"recording_id": s.recording_id, "start": s.start, "end": s.end} for s in new_ku.sources]
        if best.verdict is Verdict.DUPLICATE:
            ops.append(
                _op(
                    KUOpType.MERGE,
                    (best.existing_ku_id, new_ku.id),
                    {
                        "survivor_id": survivor.id,
                        "loser_id": new_ku.id,
                        "canonical": _richer(survivor.canonical, new_ku.canonical),
                        "alt_phrasings": [new_ku.canonical],
                        "topic_ids": sorted({*survivor.topic_ids, *new_ku.topic_ids}),
                        # NOTE: fold() unions sources from both KUs; new_ku must be
                        # persisted (as a create) before this merge, or the caller
                        # passes its sources through here. See consolidate.py TODO.
                    },
                    best.rationale,
                )
            )
        else:  # ELABORATION
            ops.append(
                _op(
                    KUOpType.ELABORATE,
                    (survivor.id,),
                    {
                        "ku_id": survivor.id,
                        "canonical": _richer(survivor.canonical, new_ku.canonical),
                        "topic_ids": sorted(new_ku.topic_ids),
                        "add_sources": add_sources,
                    },
                    best.rationale,
                )
            )
    else:
        ops.append(
            _op(
                KUOpType.CREATE,
                (new_ku.id,),
                {"ku": _ku_dict(new_ku)},
                "no confident match among retrieval neighbours",
            )
        )
        for j in judgements:
            if (
                j.verdict in (Verdict.DUPLICATE, Verdict.ELABORATION)
                and j.confidence < config.merge_confidence_threshold
                and j.existing_ku_id in existing
            ):
                signals.append(ReviewSignal("proposed_merge", (new_ku.id, j.existing_ku_id), j.rationale))

    for j in judgements:
        if j.verdict is Verdict.CONTRADICTION and j.existing_ku_id in existing:
            ops.append(
                _op(
                    KUOpType.FLAG_CONTRADICTION,
                    (new_ku.id, j.existing_ku_id),
                    {"ku_ids": [new_ku.id, j.existing_ku_id]},
                    j.rationale,
                )
            )
            signals.append(ReviewSignal("contradiction", (new_ku.id, j.existing_ku_id), j.rationale))

    return ConsolidationPlan(tuple(ops), tuple(signals))


def _richer(a: str, b: str) -> str:
    """Keep the more complete phrasing. Length is a crude proxy; the per-Topic
    reorg (FR-16) does a better job later."""
    return a if len(a) >= len(b) else b


def _ku_dict(ku: KnowledgeUnit) -> dict[str, Any]:
    return {
        "id": ku.id,
        "canonical": ku.canonical,
        "topic_ids": list(ku.topic_ids),
        "sources": [{"recording_id": s.recording_id, "start": s.start, "end": s.end} for s in ku.sources],
        "alt_phrasings": list(ku.alt_phrasings),
        "created_at": ku.created_at,
        "updated_at": ku.updated_at,
        "status": ku.status.value,
    }
