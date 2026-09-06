"""Daily quiz flow (FR-24..FR-31).

Timer builds + pushes the quiz; the Telegram webhook delivers questions one at a
time and grades answers.

* select KUs (``domain.selection.select_due``), excluding open contradictions and
  pending-review KUs (FR-15 / FR-24);
* one Question per KU, rotating type (FR-25) — prompt ``question.v1``;
* deliver one at a time over Telegram (FR-26);
* grade each Answer semantically (FR-29) — the ``Grader`` port — update the Card
  via ``domain.scheduling.review`` (FR-30);
* a ``missed`` (or partial-streak) grade upserts a Revisit Action Item (FR-41);
* two consecutive ``correct`` auto-resolve the Revisit item (FR-45).
"""

from __future__ import annotations

import itertools
from datetime import date

from quizme.application import action_items
from quizme.application.deps import Deps
from quizme.application.prompts import load
from quizme.domain.errors import QuizmeError
from quizme.domain.ids import new_id
from quizme.domain.quiz import GradeValue
from quizme.domain.scheduling import Card, Rating, review

PROMPT_QUESTION = "question.v1"
_RATING = {GradeValue.CORRECT: Rating.GOOD, GradeValue.PARTIAL: Rating.HARD, GradeValue.MISSED: Rating.AGAIN}
_TYPES = ["short_answer", "cloze", "free_recall"]


def build_daily_quiz(deps: Deps, *, for_date: date | None = None) -> str:
    today = for_date or deps.clock.now().date()
    existing = deps.store.get_quiz_by_date(today)
    if existing:
        return str(existing["id"])

    now = deps.clock.now()
    exclude = deps.store.contradicted_and_pending_ku_ids()
    from quizme.domain.selection import select_due

    ku_ids = select_due(
        deps.store.all_cards(),
        now=now,
        max_questions=deps.config.quiz.max_questions_per_day,
        exclude_ku_ids=exclude,
        retrievability_threshold=deps.config.quiz.retrievability_threshold,
    )
    quiz_id = new_id()
    deps.store.add_quiz(quiz_id=quiz_id, quiz_date=today, ku_ids=ku_ids)

    open_todos = len(deps.store.list_action_items(status="open"))
    if not ku_ids:
        deps.delivery.send_message(f"No reviews due today. {open_todos} open to-dos.")
        return quiz_id

    kus = deps.store.load_kus()
    prompt = load(PROMPT_QUESTION)
    rows = []
    for ku_id, rtype in zip(ku_ids, itertools.cycle(_TYPES), strict=False):
        ku = kus.get(ku_id)
        if ku is None:
            continue
        result = deps.llm.complete_json(
            stage="question",
            prompt_version=prompt.version,
            system=prompt.system,
            user=prompt.render(
                canonical=ku.canonical,
                alt_phrasings="; ".join(ku.alt_phrasings) or "-",
                topics=", ".join(ku.topic_ids),
                requested_type=rtype,
            ),
            schema=prompt.schema,
        )
        rows.append(
            {
                "id": new_id(),
                "quiz_id": quiz_id,
                "ku_id": ku_id,
                "type": result.data["type"],
                "prompt": result.data["prompt"],
                "model_answer": result.data["model_answer"],
                "phrasing_used": result.data["phrasing_used"],
                "prompt_version": prompt.version,
            }
        )
    deps.store.add_questions(rows)
    deps.delivery.send_message(f"Today's quiz — {len(rows)} questions. {open_todos} open to-dos.")
    deliver_next_question(deps, quiz_id)
    return quiz_id


def deliver_next_question(deps: Deps, quiz_id: str) -> str | None:
    for q in deps.store.quiz_questions(quiz_id):
        if deps.store.get_grade(q["id"]) is None:
            deps.delivery.send_question(question_id=q["id"], prompt=q["prompt"])
            return str(q["id"])
    deps.delivery.send_message("Quiz complete for today. 🎉")
    return None


def grade_answer(deps: Deps, *, question_id: str, answer_text: str) -> GradeValue:
    q = deps.store.get_question(question_id)
    if q is None:
        raise QuizmeError(f"no question {question_id}")
    if deps.store.get_grade(question_id) is not None:
        raise QuizmeError("question already graded")

    deps.store.record_answer(question_id=question_id, text=answer_text)
    ku = deps.store.load_kus().get(q["ku_id"])
    ku_canonical = ku.canonical if ku else q["model_answer"]
    value, rationale = deps.grader.grade(
        answer_text=answer_text, model_answer=q["model_answer"], ku_canonical=ku_canonical
    )
    deps.store.record_grade(
        {
            "question_id": question_id,
            "value": value.value,
            "rationale": rationale,
            "model": deps.config.llm.default_deployment,
            "prompt_version": "grade.v1",
            "disputed": False,
        }
    )

    now = deps.clock.now()
    card = deps.store.get_card(q["ku_id"]) or Card.new(q["ku_id"], now=now)
    deps.store.upsert_card(review(card, _RATING[value], now=now))

    recent = deps.store.recent_grades_for_ku(q["ku_id"])  # most-recent-first, includes this grade
    topic_id = ku.topic_ids[0] if ku and ku.topic_ids else None
    streak = deps.config.quiz.partial_streak_for_revisit
    if value is GradeValue.MISSED or _leading_run(recent, "partial") >= streak:
        action_items.raise_revisit(
            deps, ku_id=q["ku_id"], topic_id=topic_id, ku_canonical=ku_canonical, model_answer=q["model_answer"]
        )
    if _leading_run(recent, "correct") >= 2:
        action_items.auto_resolve_revisit(deps, ku_id=q["ku_id"])

    deps.delivery.send_message(f"{value.value.upper()} — {rationale}\n\nModel answer: {q['model_answer']}")
    return value


def dispute_grade(deps: Deps, *, question_id: str) -> None:
    grade = deps.store.get_grade(question_id)
    if grade is None:
        raise QuizmeError("nothing to dispute")
    deps.store.mark_grade_disputed(question_id)
    q = deps.store.get_question(question_id)
    deps.store.add_review_item(
        kind="disputed_grade",
        ku_ids=[q["ku_id"]] if q else [],
        context={"question_id": question_id, "original_value": grade["value"]},
    )
    deps.delivery.send_message("Grade disputed — it won't count and is queued for review (FR-31).")


def _leading_run(values: list[str], want: str) -> int:
    n = 0
    for v in values:
        if v == want:
            n += 1
        else:
            break
    return n
