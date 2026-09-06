"""Daily quiz flow (FR-24..FR-31).

Runs in the web process: the timer builds + pushes the quiz; the Telegram webhook
delivers questions one at a time and grades answers.

* select KUs (domain.selection.select_due), excluding open contradictions and
  pending-review KUs (FR-15 / FR-24);
* generate one Question per KU (FR-25) — prompt ``question.v1``;
* deliver one at a time over Telegram (FR-26);
* grade each Answer semantically (FR-29) — prompt ``grade.v1`` — update the Card
  via domain.scheduling.review (FR-30);
* a ``missed`` (or partial-streak) grade upserts a Revisit Action Item (FR-41);
* two consecutive ``correct`` on a KU auto-resolve its Revisit item (FR-45).
"""

from __future__ import annotations

from datetime import date

from quizme.application.deps import Deps
from quizme.domain.quiz import GradeValue

PROMPT_QUESTION = "question.v1"
PROMPT_GRADE = "grade.v1"


def build_daily_quiz(deps: Deps, *, for_date: date | None = None) -> str:
    raise NotImplementedError(
        "build_daily_quiz: kus = domain.selection.select_due(store.all_cards(), "
        "now=clock.now(), max_questions=config.quiz.max_questions_per_day, "
        "exclude_ku_ids=store.contradicted_and_pending_ku_ids(), "
        "retrievability_threshold=config.quiz.retrievability_threshold); "
        "generate Questions; persist Quiz; deps.delivery.send_message(notification incl. "
        "open action-item count, FR-27/FR-43). Returns the quiz id."
    )


def deliver_next_question(deps: Deps, quiz_id: str) -> None:
    raise NotImplementedError("deliver_next_question: FR-26 one-at-a-time over Telegram")


def grade_answer(deps: Deps, *, question_id: str, answer_text: str) -> GradeValue:
    raise NotImplementedError(
        "grade_answer: value, rationale = deps.grader.grade(answer_text=..., model_answer=..., "
        "ku_canonical=...); persist Grade; if not disputed -> card = domain.scheduling.review("
        "store.get_card(ku_id), rating_from(value), now=clock.now()); store.upsert_card(card); "
        "handle Revisit item (FR-41) / auto-resolve (FR-45)."
    )


def dispute_grade(deps: Deps, *, question_id: str) -> None:
    raise NotImplementedError("dispute_grade: mark Grade disputed, add Review item, DO NOT touch the Card (FR-31).")
