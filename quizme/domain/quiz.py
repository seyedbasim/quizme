"""Quiz domain types (FR-24..FR-31). Behaviour lives in application/quiz.py."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum


class QuestionType(str, Enum):
    SHORT_ANSWER = "short_answer"
    CLOZE = "cloze"
    FREE_RECALL = "free_recall"


class GradeValue(str, Enum):
    CORRECT = "correct"
    PARTIAL = "partial"
    MISSED = "missed"


@dataclass(frozen=True, slots=True)
class Question:
    id: str
    quiz_id: str
    ku_id: str
    phrasing_used: str  # canonical or one of the alt_phrasings it derived from
    type: QuestionType
    prompt: str  # what the user sees
    model_answer: str
    prompt_version: str


@dataclass(frozen=True, slots=True)
class Answer:
    question_id: str
    text: str
    submitted_at: datetime


@dataclass(frozen=True, slots=True)
class Grade:
    question_id: str
    value: GradeValue
    rationale: str
    model: str
    prompt_version: str
    graded_at: datetime
    disputed: bool = False


@dataclass(frozen=True, slots=True)
class Quiz:
    id: str
    quiz_date: date
    ku_ids: tuple[str, ...]
    created_at: datetime
