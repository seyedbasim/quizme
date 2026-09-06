"""Typed configuration (architecture-spine → Consistency Conventions, "Config").

Non-secret defaults come from ``config.toml``; ``config.local.toml`` overrides for
local dev. Secrets are NOT here — adapters read them from Key Vault / env (AD-17).
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from quizme.domain.errors import ConfigError


class IngestConfig(BaseModel):
    allowed_formats: list[str] = ["m4a", "mp3", "wav"]
    max_file_mb: int = 200
    language: str = "en"


class ConsolidationTuning(BaseModel):
    merge_confidence_threshold: float = 0.80
    retrieval_neighbours: int = 6


class LLMConfig(BaseModel):
    endpoint: str = ""
    api_version: str = "2025-01-01-preview"
    default_deployment: str = "gpt-4.1"
    deployment_type: str = "regional"  # AD-13: never "global"
    temperature: float = 0.0
    stages: dict[str, str] = Field(default_factory=dict)
    consolidation: ConsolidationTuning = ConsolidationTuning()

    def deployment_for(self, stage: str) -> str:
        return self.stages.get(stage, self.default_deployment)


class TranscriptionConfig(BaseModel):
    mode: str = "batch"
    model: str = "whisper"


class EmbeddingsConfig(BaseModel):
    deployment: str = "text-embedding-3-small"
    dimensions: int = 1536


class QuizConfig(BaseModel):
    send_time_local: str = "07:30"
    max_questions_per_day: int = 10
    retrievability_threshold: float = 0.90
    partial_streak_for_revisit: int = 2


class BudgetConfig(BaseModel):
    monthly_credit_usd: int = 150
    warn_at_pct: int = 60
    throttle_at_pct: int = 80


class ReviewConfig(BaseModel):
    suppress_contradicted_kus_from_quiz: bool = True
    followup_confidence_threshold: float = 0.65


class AppConfig(BaseModel):
    region: str = "southeastasia"
    timezone: str = "Asia/Singapore"


class Config(BaseModel):
    app: AppConfig = AppConfig()
    ingest: IngestConfig = IngestConfig()
    llm: LLMConfig = LLMConfig()
    transcription: TranscriptionConfig = TranscriptionConfig()
    embeddings: EmbeddingsConfig = EmbeddingsConfig()
    quiz: QuizConfig = QuizConfig()
    budget: BudgetConfig = BudgetConfig()
    review: ReviewConfig = ReviewConfig()


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def load(path: str | os.PathLike[str] | None = None) -> Config:
    path = Path(path or os.environ.get("QUIZME_CONFIG", "config.toml"))
    if not path.exists():
        raise ConfigError(f"config file not found: {path}")
    data = tomllib.loads(path.read_text())

    local = path.with_name("config.local.toml")
    if local.exists():
        data = _deep_merge(data, tomllib.loads(local.read_text()))

    try:
        return Config.model_validate(data)
    except Exception as exc:  # noqa: BLE001 - re-raise as our type
        raise ConfigError(f"invalid config: {exc}") from exc
