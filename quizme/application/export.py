"""Portable export — the credit-lapse / re-host hedge (AD-18, PRD §6.1).

Produces a bundle that can rebuild the knowledge base anywhere:

* a Postgres logical dump (standard SQL; ``pgvector`` columns as float arrays);
* a Blob manifest (object key -> sha256, size) for the audio + transcripts;
* the resolved config.

No Azure-proprietary types anywhere in it. The op-log alone (+ Recordings +
Transcripts) is sufficient to re-derive everything (AD-1, FR-20).
"""

from __future__ import annotations

from quizme.application.deps import Deps


def export_bundle(deps: Deps, *, dest_dir: str) -> str:
    raise NotImplementedError(
        "export_bundle: pg_dump --format=plain (or SQLAlchemy row dump) of every table; "
        "list Blob container -> manifest.json; write resolved config; tar it; return path."
    )
