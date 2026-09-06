"""Small adapters: the system clock and the LLM-backed grader."""

from __future__ import annotations

from datetime import UTC, datetime

from quizme.application.config import LLMConfig
from quizme.application.ports import LLM
from quizme.domain.errors import LLMError
from quizme.domain.quiz import GradeValue


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


_GRADE_SCHEMA = {
    "type": "object",
    "properties": {
        "value": {"enum": ["correct", "partial", "missed"]},
        "rationale": {"type": "string"},
    },
    "required": ["value", "rationale"],
    "additionalProperties": False,
}

_GRADE_SYSTEM = (
    "Grade the user's free-text answer against the model answer and the knowledge "
    "unit, by meaning not wording. 'correct' = captures the substance even if brief "
    "or reworded. 'partial' = core idea partly there, a load-bearing part missing or "
    "wrong. 'missed' = wrong, empty, 'I don't know', or unrelated. Do not inflate the "
    "grade to be kind. In 'rationale' name what was right and what was missing in one "
    "or two sentences. Output JSON matching the schema."
)


class LLMGrader:
    """Implements ports.Grader using the LLM adapter and prompt ``grade.v1`` (FR-29)."""

    PROMPT_VERSION = "grade.v1"

    def __init__(self, llm: LLM) -> None:
        self._llm = llm

    def grade(self, *, answer_text: str, model_answer: str, ku_canonical: str) -> tuple[GradeValue, str]:
        user = f"knowledge unit: {ku_canonical}\nmodel answer:   {model_answer}\nuser answer:    {answer_text}"
        result = self._llm.complete_json(
            stage="grade",
            prompt_version=self.PROMPT_VERSION,
            system=_GRADE_SYSTEM,
            user=user,
            schema=_GRADE_SCHEMA,
        )
        try:
            return GradeValue(result.data["value"]), result.data["rationale"]
        except (KeyError, ValueError) as exc:
            raise LLMError(f"grader returned unusable output: {result.data}") from exc


def is_reasoning_default(cfg: LLMConfig) -> bool:
    """True if the default deployment is a reasoning model (temperature fixed)."""
    return cfg.default_deployment.startswith(("o1", "o3", "o4")) or "gpt-5" in cfg.default_deployment
