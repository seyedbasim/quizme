"""Stage 4 — the Consolidation Engine (FR-11..FR-16). Called by ``extract.run``.

For each new KU: embed it, retrieve the nearest committed KUs (AD-6 bound `k`),
ask the LLM for a per-pair verdict (prompt ``consolidate.v1``), run the pure
policy in :mod:`quizme.domain.consolidation` (AD-15), append the ops (AD-3), raise
Review Queue items for contradictions and sub-threshold merges (AD-7).

**v1 simplification:** each new KU is consolidated only against the *already
committed* KB, not against the other KUs from the same recording. Two same-batch
duplicates both land; the per-Topic reorg (FR-16) cleans up. Consistent with
AD-15 (under-merging is safe).
"""

from __future__ import annotations

import json
from datetime import datetime

from quizme.application.deps import Deps
from quizme.application.prompts import load
from quizme.domain.consolidation import (
    ConsolidationConfig,
    PairJudgement,
    Verdict,
    plan_operations,
)
from quizme.domain.ids import new_id, text_hash
from quizme.domain.ku import Actor, KnowledgeUnit, KUOperation, KUOpType, KUStatus, ku_payload

STAGE = "consolidate"
STAGE_VERSION = "2026-09-06.1"


def consolidate_batch(new_kus: list[KnowledgeUnit], deps: Deps) -> dict[str, int]:
    if not new_kus:
        return {"created": 0, "merged": 0, "contradictions": 0}

    prompt = load("consolidate.v1")
    tuning = deps.config.llm.consolidation
    cfg = ConsolidationConfig(merge_confidence_threshold=tuning.merge_confidence_threshold)
    now: datetime = deps.clock.now()

    committed = {i: ku for i, ku in deps.store.load_kus().items() if ku.status is KUStatus.ACTIVE}
    embeddings = deps.embedder.embed([ku.canonical for ku in new_kus])

    created = merged = contradictions = 0
    pending_embeddings: list[tuple[str, list[float]]] = []
    for ku, emb in zip(new_kus, embeddings, strict=True):
        neighbours = [n for n in deps.store.nearest_kus(emb, k=tuning.retrieval_neighbours) if n.id != ku.id]

        judgements: list[PairJudgement] = []
        if neighbours:
            result = deps.llm.complete_json(
                stage="consolidate",
                prompt_version=prompt.version,
                system=prompt.system,
                user=prompt.render(
                    new_unit=json.dumps({"canonical": ku.canonical, "topics": list(ku.topic_ids)}),
                    neighbours=json.dumps([{"existing_ku_id": n.id, "canonical": n.canonical} for n in neighbours]),
                ),
                schema=prompt.schema,
            )
            judgements = [
                PairJudgement(
                    existing_ku_id=j["existing_ku_id"],
                    verdict=Verdict(j["verdict"]),
                    confidence=float(j["confidence"]),
                    rationale=j["rationale"],
                )
                for j in result.data["judgements"]
                if j["existing_ku_id"] in committed
            ]

        plan = plan_operations(
            ku,
            judgements,
            committed,
            cfg,
            now=now,
            model=deps.config.llm.default_deployment,
            prompt_version=prompt.version,
            prompt_hash=text_hash(ku.canonical),
        )
        deps.store.append_ops(plan.ops)

        op_types = {op.type for op in plan.ops}
        if KUOpType.MERGE in op_types:
            merged += 1
        elif KUOpType.CREATE in op_types:
            created += 1
            pending_embeddings.append((ku.id, list(emb)))
        if KUOpType.FLAG_CONTRADICTION in op_types:
            contradictions += 1

        for sig in plan.review_signals:
            deps.store.add_review_item(kind=sig.kind, ku_ids=list(sig.ku_ids), context={"rationale": sig.rationale})

    # project so the FK from ku_embedding -> knowledge_unit is satisfied, then
    # store the vectors for KUs that survived as live rows.
    folded = deps.store.load_kus()
    deps.store.upsert_ku_projection(list(folded.values()))
    for ku_id, emb in pending_embeddings:
        if ku_id in folded and folded[ku_id].status is KUStatus.ACTIVE:
            deps.store.put_ku_embedding(ku_id, emb)

    return {"created": created, "merged": merged, "contradictions": contradictions}


def create_pending(ku: KnowledgeUnit, deps: Deps, *, reason: str) -> None:
    """Low-confidence extraction (FR-10): create as PENDING_REVIEW + a review item.
    Not consolidated until confirmed."""
    now = deps.clock.now()
    pending = KnowledgeUnit(
        id=ku.id,
        canonical=ku.canonical,
        topic_ids=ku.topic_ids,
        sources=ku.sources,
        alt_phrasings=ku.alt_phrasings,
        created_at=now,
        updated_at=now,
        status=KUStatus.PENDING_REVIEW,
    )
    deps.store.append_ops(
        [
            KUOperation(
                op_id=new_id(),
                ts=now,
                actor=Actor.ENGINE,
                type=KUOpType.CREATE,
                ku_ids_in=(pending.id,),
                payload={"ku": ku_payload(pending)},
                model=deps.config.llm.default_deployment,
                prompt_version="extract.v1",
                rationale=reason,
            )
        ]
    )
    deps.store.add_review_item(kind="uncertain_extraction", ku_ids=[pending.id], context={"reason": reason})
