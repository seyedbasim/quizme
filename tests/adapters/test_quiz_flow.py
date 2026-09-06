"""Quiz flow integration test (FR-24..31, 41) against live Azure (Postgres +
gpt-5-mini). Delivery is faked; everything else is real.

Env: QUIZME_TEST_DATABASE_URL + QUIZME_TEST_AOAI_ENDPOINT + QUIZME_TEST_AOAI_KEY.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime

import pytest

from quizme.application.config import Config
from quizme.domain.ids import new_id
from quizme.domain.ku import Actor, KnowledgeUnit, KUOperation, KUOpType, SourceRef, ku_payload
from quizme.domain.scheduling import Card

_DSN = os.environ.get("QUIZME_TEST_DATABASE_URL")
_EP = os.environ.get("QUIZME_TEST_AOAI_ENDPOINT")
_KEY = os.environ.get("QUIZME_TEST_AOAI_KEY")
pytestmark = pytest.mark.skipif(not (_DSN and _EP and _KEY), reason="needs live Azure env vars")

NOW = datetime(2026, 9, 6, 8, 0, tzinfo=UTC)


class _Delivery:
    def __init__(self) -> None:
        self.messages: list[str] = []
        self.questions: list[tuple[str, str]] = []

    def send_message(self, text: str) -> None:
        self.messages.append(text)

    def send_question(self, *, question_id: str, prompt: str) -> None:
        self.questions.append((question_id, prompt))


class _Spend:
    def month_to_date_usd(self) -> float:
        return 0.0

    def projected_month_end_usd(self) -> float:
        return 0.0

    def is_throttled(self) -> bool:
        return False


@pytest.fixture
def deps():
    from quizme.adapters.embedder_foundry import FoundryEmbedder
    from quizme.adapters.llm_foundry import FoundryLLM
    from quizme.adapters.misc import LLMGrader
    from quizme.adapters.store_postgres import PostgresStore
    from quizme.application.deps import Deps

    cfg = Config()
    cfg.llm.endpoint = _EP
    cfg.llm.default_deployment = "gpt-5-mini"
    cfg.embeddings.deployment = "embed"
    cfg.quiz.max_questions_per_day = 3

    store = PostgresStore(_DSN)
    store.wipe_all()
    llm = FoundryLLM(config=cfg.llm, sink=store, api_key=_KEY)

    class _Clock:
        def now(self):
            return datetime.now(UTC)

    d = Deps(
        config=cfg,
        clock=_Clock(),
        store=store,
        llm=llm,
        transcriber=None,
        embedder=FoundryEmbedder(embeddings=cfg.embeddings, llm=cfg.llm, api_key=_KEY),
        intake=None,
        delivery=_Delivery(),
        grader=LLMGrader(llm),
        spend=_Spend(),
    )  # type: ignore[arg-type]
    yield d
    store.wipe_all()
    store.dispose()


def _seed_ku(deps, canonical: str, topic: str) -> str:
    tid = deps.store.get_or_create_topic(topic)
    ku = KnowledgeUnit(
        id=new_id(),
        canonical=canonical,
        topic_ids=(tid,),
        sources=(SourceRef("r1", 0.0, 5.0),),
        created_at=NOW,
        updated_at=NOW,
    )
    deps.store.append_ops(
        [
            KUOperation(
                op_id=new_id(),
                ts=NOW,
                actor=Actor.ENGINE,
                type=KUOpType.CREATE,
                ku_ids_in=(ku.id,),
                payload={"ku": ku_payload(ku)},
            )
        ]
    )
    deps.store.upsert_ku_projection([ku])
    deps.store.upsert_card(Card.new(ku.id, now=NOW))  # due NOW -> selectable
    return ku.id


def test_build_grade_dispute(deps) -> None:
    from quizme.application import quiz

    ku_a = _seed_ku(deps, "The TCP minimum retransmission timeout is one second.", "tcp")
    _seed_ku(deps, "HTTP status 429 means the client has sent too many requests.", "http")

    quiz_id = quiz.build_daily_quiz(deps)
    questions = deps.store.quiz_questions(quiz_id)
    assert 1 <= len(questions) <= 3
    assert deps.delivery.questions, "first question should have been delivered"

    # answer the first correctly
    q1 = deps.store.get_question(deps.delivery.questions[0][0])
    from quizme.domain.quiz import GradeValue

    good = "one second" if "timeout" in q1["prompt"].lower() or ku_a == q1["ku_id"] else "429"
    v = quiz.grade_answer(deps, question_id=q1["id"], answer_text=good)
    assert v in (GradeValue.CORRECT, GradeValue.PARTIAL)
    card = deps.store.get_card(q1["ku_id"])
    assert card is not None and card.reps == 1 and card.last_review is not None

    # answer another one wrong -> revisit action item (FR-41)
    remaining = [q for q in questions if q["id"] != q1["id"]]
    if remaining:
        q2 = remaining[0]
        quiz.grade_answer(deps, question_id=q2["id"], answer_text="no idea, I forget")
        from quizme.domain.action_items import revisit_key

        item = deps.store.get_action_item(revisit_key(q2["ku_id"]))
        assert item is not None and item.origin.value == "revisit"

        # dispute that grade -> review item, disputed flag
        quiz.dispute_grade(deps, question_id=q2["id"])
        assert deps.store.get_grade(q2["id"])["disputed"] is True
        assert any(r["kind"] == "disputed_grade" for r in deps.store.list_review_items())

    # idempotent: re-build returns the same quiz
    assert quiz.build_daily_quiz(deps) == quiz_id
