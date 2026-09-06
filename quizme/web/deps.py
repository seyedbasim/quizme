"""FastAPI dependency: the composed :class:`Deps` bundle (built once)."""

from __future__ import annotations

from functools import lru_cache

from quizme.application.deps import Deps


@lru_cache(maxsize=1)
def get_deps() -> Deps:
    from quizme.composition import build_deps

    return build_deps()
