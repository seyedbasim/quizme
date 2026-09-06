"""Review Queue service (FR-21..FR-23).

One list of everything needing a human decision: contradictions (FR-15), uncertain
extractions (FR-10), uncertain follow-ups (FR-40), disputed grades (FR-31),
proposed sub-threshold merges (AD-15). Resolving an item records a user-attributed
KUOperation (or grade correction) — AD-3 — and never row-deletes a KU (tombstone).
"""

from __future__ import annotations

from typing import Any

from quizme.application.deps import Deps

ITEM_KINDS = (
    "contradiction",
    "uncertain_extraction",
    "uncertain_followup",
    "disputed_grade",
    "proposed_merge",
    "possibly_addressed_followup",  # FR-45 second half (v1.1)
)


def list_open(deps: Deps) -> list[dict[str, Any]]:
    raise NotImplementedError("list_open: return open review items with inline context (FR-21)")


def resolve(deps: Deps, *, item_id: str, resolution: str, payload: dict[str, Any]) -> None:
    raise NotImplementedError(
        "resolve: dispatch on item.kind; for 'contradiction' -> user picks keep-A / keep-B / "
        "edited-merge -> append a user-actor KUOperation (merge/archive/edit); "
        "for 'disputed_grade' -> overturn Grade then apply the corrected FSRS update; "
        "for 'proposed_merge' -> merge or dismiss. Record attribution (FR-22)."
    )
