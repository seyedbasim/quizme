"""The dependency bundle passed to pipeline stages and flows.

Composed once at the process entrypoint (functions/, web/) from concrete adapters;
the application layer only ever sees the port protocols.
"""

from __future__ import annotations

from dataclasses import dataclass

from quizme.application.config import Config
from quizme.application.ports import (
    LLM,
    Clock,
    Delivery,
    Embedder,
    Grader,
    RecordingIntake,
    SpendMeter,
    Store,
    Transcriber,
)


@dataclass(slots=True)
class Deps:
    config: Config
    clock: Clock
    store: Store
    llm: LLM
    transcriber: Transcriber
    embedder: Embedder
    intake: RecordingIntake
    delivery: Delivery
    grader: Grader
    spend: SpendMeter
