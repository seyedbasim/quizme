"""Telegram webhook (AD-10).

Excluded from Easy Auth (path excluded in authsettingsV2); authenticated here by
the secret token header + the allowed chat id. Carries Questions/Answers only.

* a text message = the answer to the first ungraded question of today's quiz →
  grade it (FR-29), then deliver the next (FR-26);
* a callback ``dispute:<question_id>`` → dispute that grade (FR-31).

Always returns 200 to a *verified* request even if processing fails — a non-2xx
makes Telegram retry indefinitely and eventually disable the webhook. Errors are
logged (App Insights) and surfaced to the user in chat.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Header, Request, Response

from quizme.application import quiz
from quizme.web.deps import get_deps

router = APIRouter(prefix="/telegram", tags=["telegram"])
log = logging.getLogger("quizme.telegram")


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

    try:
        deps.delivery.enrol_chat(chat_id)
        _handle(deps, update)
    except Exception:
        log.exception("telegram webhook processing failed")
        try:
            deps.delivery.send_message("⚠️ Something went wrong handling that — logged for review.")
        except Exception:
            log.exception("could not notify user of webhook failure")
    return Response(status_code=200)


def _handle(deps: Any, update: dict[str, Any]) -> None:
    if "callback_query" in update:
        data = update["callback_query"].get("data", "")
        if data.startswith("dispute:"):
            quiz.dispute_grade(deps, question_id=data.split(":", 1)[1])
        return

    text = (update.get("message") or {}).get("text", "").strip()
    if not text:
        return
    if text.startswith("/start"):
        deps.delivery.send_message("Hi! You're set up. The daily quiz will arrive here each morning.")
        return

    q = deps.store.get_quiz_by_date(deps.clock.now().date())
    if not q:
        deps.delivery.send_message("No quiz today — nothing to answer.")
        return

    pending = next(
        (qq for qq in deps.store.quiz_questions(str(q["id"])) if deps.store.get_grade(qq["id"]) is None),
        None,
    )
    if pending is None:
        deps.delivery.send_message("Today's quiz is already complete. 🎉")
        return

    quiz.grade_answer(deps, question_id=pending["id"], answer_text=text)
    quiz.deliver_next_question(deps, str(q["id"]))


def _chat_id(update: dict[str, Any]) -> int | None:
    for path in (("message", "chat", "id"), ("callback_query", "message", "chat", "id")):
        node: Any = update
        for key in path:
            node = node.get(key) if isinstance(node, dict) else None
        if isinstance(node, int):
            return node
    return None
