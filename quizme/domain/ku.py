"""Knowledge Units and the append-only operation log that projects them.

Invariants enforced here:

* **AD-2** — the KnowledgeUnit is the only source of truth; Topic Notes are derived.
* **AD-3** — the knowledge base is ``fold(operation_log)``; no KU is mutated except
  through a recorded :class:`KUOperation`. Superseded KUs are tombstoned, never dropped.
* **AD-5** — provenance is union-only: a merge/elaboration unions ``sources``, never
  drops one. A KU with zero sources must be archived.

``fold`` is pure and deterministic: replaying the same ops from empty yields the same
live set (FR-17).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum
from typing import Any

from quizme.domain.errors import ValidationError


class KUStatus(str, Enum):
    ACTIVE = "active"
    PENDING_REVIEW = "pending_review"  # FR-10 / FR-15 — not quiz-eligible yet
    TOMBSTONED = "tombstoned"  # superseded by a merge, or archived


@dataclass(frozen=True, slots=True)
class SourceRef:
    """A span of one Recording that supports a claim (FR-8)."""

    recording_id: str
    start: float  # seconds from recording start
    end: float

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise ValidationError(f"source span end {self.end} < start {self.start}")


@dataclass(frozen=True, slots=True)
class KnowledgeUnit:
    id: str
    canonical: str
    topic_ids: tuple[str, ...]
    sources: tuple[SourceRef, ...]
    created_at: datetime
    updated_at: datetime
    alt_phrasings: tuple[str, ...] = ()
    status: KUStatus = KUStatus.ACTIVE
    superseded_by: str | None = None  # set when TOMBSTONED via merge

    def __post_init__(self) -> None:
        if not self.canonical.strip():
            raise ValidationError("KU canonical phrasing is empty")
        if self.status is not KUStatus.TOMBSTONED and not self.sources:
            raise ValidationError(f"KU {self.id} has no sources and is not archived (AD-5)")

    @property
    def quiz_eligible(self) -> bool:
        return self.status is KUStatus.ACTIVE


class KUOpType(str, Enum):
    CREATE = "create"
    MERGE = "merge"  # two KUs -> one; loser tombstoned (FR-13)
    ELABORATE = "elaborate"  # survivor's claim replaced with a fuller form (FR-14)
    FLAG_CONTRADICTION = "flag_contradiction"  # no KU change; raises a Review item (FR-15)
    SPLIT = "split"  # one KU -> several (FR-16 / FR-34)
    ARCHIVE = "archive"  # FR-34
    EDIT = "edit"  # user edits canonical / phrasings (FR-33)
    RETOPIC = "retopic"  # change topic_ids only


class Actor(str, Enum):
    ENGINE = "engine"
    USER = "user"
    AUTO = "auto"  # FR-45 loop-closing


@dataclass(frozen=True, slots=True)
class KUOperation:
    """One recorded change. The log is append-only: no UPDATE, no DELETE.

    ``payload`` shape by ``type``:

    * ``create``     -> ``{"ku": <KnowledgeUnit-as-dict>}``
    * ``merge``      -> ``{"survivor_id": str, "loser_id": str,
                            "canonical": str, "alt_phrasings": [str], "topic_ids": [str]}``
    * ``elaborate``  -> ``{"ku_id": str, "canonical": str, "topic_ids": [str],
                            "add_sources": [SourceRef-as-dict]}``
    * ``edit``       -> ``{"ku_id": str, "canonical"?: str, "alt_phrasings"?: [str]}``
    * ``retopic``    -> ``{"ku_id": str, "topic_ids": [str]}``
    * ``archive``    -> ``{"ku_id": str}``
    * ``split``      -> ``{"parent_id": str, "children": [<KnowledgeUnit-as-dict>]}``
    * ``flag_contradiction`` -> ``{"ku_ids": [str, str]}``  (no KU mutation)
    """

    op_id: str
    ts: datetime
    actor: Actor
    type: KUOpType
    ku_ids_in: tuple[str, ...]
    payload: Mapping[str, Any]
    ku_id_out: str | None = None
    model: str | None = None
    prompt_version: str | None = None
    prompt_hash: str | None = None
    rationale: str | None = None


# --------------------------------------------------------------------------- fold


def _dt(v: datetime | str) -> datetime:
    """Payload timestamps are stored as ISO-8601 strings (Consistency
    Conventions); accept a ``datetime`` too so in-memory tests can pass one."""
    return v if isinstance(v, datetime) else datetime.fromisoformat(v)


def _ku_from_payload(d: Mapping[str, Any]) -> KnowledgeUnit:
    return KnowledgeUnit(
        id=d["id"],
        canonical=d["canonical"],
        topic_ids=tuple(d.get("topic_ids", ())),
        sources=tuple(SourceRef(**s) for s in d.get("sources", ())),
        alt_phrasings=tuple(d.get("alt_phrasings", ())),
        created_at=_dt(d["created_at"]),
        updated_at=_dt(d["updated_at"]),
        status=KUStatus(d.get("status", KUStatus.ACTIVE)),
        superseded_by=d.get("superseded_by"),
    )


def _union_sources(*groups: Sequence[SourceRef]) -> tuple[SourceRef, ...]:
    seen: dict[tuple[str, float, float], SourceRef] = {}
    for group in groups:
        for s in group:
            seen.setdefault((s.recording_id, s.start, s.end), s)
    return tuple(seen.values())


def fold(ops: Iterable[KUOperation]) -> dict[str, KnowledgeUnit]:
    """Project the operation log into the current KU set (AD-3).

    Returns every KU keyed by id, including tombstoned ones (callers filter on
    ``status`` / ``quiz_eligible``). Order of ``ops`` is assumed chronological.
    """
    kus: dict[str, KnowledgeUnit] = {}

    for op in ops:
        match op.type:
            case KUOpType.CREATE:
                ku = _ku_from_payload(op.payload["ku"])
                kus[ku.id] = ku

            case KUOpType.EDIT:
                p = op.payload
                cur = kus[p["ku_id"]]
                kus[cur.id] = replace(
                    cur,
                    canonical=p.get("canonical", cur.canonical),
                    alt_phrasings=tuple(p.get("alt_phrasings", cur.alt_phrasings)),
                    updated_at=op.ts,
                )

            case KUOpType.RETOPIC:
                p = op.payload
                cur = kus[p["ku_id"]]
                kus[cur.id] = replace(cur, topic_ids=tuple(p["topic_ids"]), updated_at=op.ts)

            case KUOpType.ELABORATE:
                p = op.payload
                cur = kus[p["ku_id"]]
                add = tuple(SourceRef(**s) for s in p.get("add_sources", ()))
                kus[cur.id] = replace(
                    cur,
                    canonical=p.get("canonical", cur.canonical),
                    topic_ids=tuple(sorted({*cur.topic_ids, *p.get("topic_ids", ())})),
                    sources=_union_sources(cur.sources, add),
                    updated_at=op.ts,
                )

            case KUOpType.MERGE:
                p = op.payload
                survivor, loser = kus[p["survivor_id"]], kus[p["loser_id"]]
                merged_alts = tuple(
                    dict.fromkeys((*survivor.alt_phrasings, *p.get("alt_phrasings", ()), loser.canonical))
                )
                kus[survivor.id] = replace(
                    survivor,
                    canonical=p.get("canonical", survivor.canonical),
                    alt_phrasings=merged_alts,
                    topic_ids=tuple(sorted({*survivor.topic_ids, *loser.topic_ids, *p.get("topic_ids", ())})),
                    sources=_union_sources(survivor.sources, loser.sources),  # AD-5
                    updated_at=op.ts,
                )
                kus[loser.id] = replace(loser, status=KUStatus.TOMBSTONED, superseded_by=survivor.id, updated_at=op.ts)

            case KUOpType.ARCHIVE:
                cur = kus[op.payload["ku_id"]]
                kus[cur.id] = replace(cur, status=KUStatus.TOMBSTONED, updated_at=op.ts)

            case KUOpType.SPLIT:
                p = op.payload
                parent = kus[p["parent_id"]]
                kus[parent.id] = replace(parent, status=KUStatus.TOMBSTONED, updated_at=op.ts)
                for child_d in p["children"]:
                    child = _ku_from_payload(child_d)
                    kus[child.id] = child

            case KUOpType.FLAG_CONTRADICTION:
                # No KU mutation — the Review Queue item is created by the caller.
                # FR-15 default suppression is applied at quiz-selection time, not here.
                pass

    return kus


def live(kus: Mapping[str, KnowledgeUnit]) -> list[KnowledgeUnit]:
    """The non-tombstoned KUs, for browsing / Topic Note regeneration."""
    return [k for k in kus.values() if k.status is not KUStatus.TOMBSTONED]
