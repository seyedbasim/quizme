"""Telegram webhook (AD-10).

Excluded from Easy Auth (host.json / authsettingsV2); authenticated here by the
secret token header + the single allowed chat id. Carries Questions/Answers only.

* a text message = the answer to the first ungraded question of today's quiz →
  grade it (FR-29), then deliver the next (FR-26);
* a callback ``dispute:<question_id>`` → dispute that grade (FR-31).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, Request, Response

from quizme.application import quiz
from quizme.web.deps import get_deps

router = APIRouter(prefix="/telegram", tags=["telegram"])


@router.post("/webhook")
async def webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> Response:
    deps = get_deps()
    update: dict[str, Any] = await request.json()

    chat_id = _chat_id(update)
    if chat_id is None or not deps.delivery.verify_webhook(
        secret_header=x_telegram_bot_api_secret_token or "", chat_id=chat_id
    ):
        return Response(status_code=403)

    if "callback_query" in update:
        data = update["callback_query"].get("data", "")
        if data.startswith("dispute:"):
            quiz.dispute_grade(deps, question_id=data.split(":", 1)[1])
        return Response(status_code=200)

    text = (update.get("message") or {}).get("text", "").strip()
    if not text:
        return Response(status_code=200)

    today = deps.clock.now().date()
    q = deps.store.get_quiz_by_date(today)
    if not q:
        deps.delivery.send_message("No quiz today — nothing to answer.")
        return Response(status_code=200)

    pending = next(
        (qq for qq in deps.store.quiz_questions(str(q["id"])) if deps.store.get_grade(qq["id"]) is None),
        None,
    )
    if pending is None:
        deps.delivery.send_message("Today's quiz is already complete. 🎉")
        return Response(status_code=200)

    quiz.grade_answer(deps, question_id=pending["id"], answer_text=text)
    quiz.deliver_next_question(deps, str(q["id"]))
    return Response(status_code=200)


def _chat_id(update: dict[str, Any]) -> int | None:
    for path in (("message", "chat", "id"), ("callback_query", "message", "chat", "id")):
        node: Any = update
        for key in path:
            node = node.get(key) if isinstance(node, dict) else None
        if isinstance(node, int):
            return node
    return None
