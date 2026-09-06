"""Azure Functions host — the serverless composition root (AD-16, AD-17, AD-19).

Three functions, all scale-to-zero on Flex Consumption:

* the FastAPI app (UI + JSON API + Telegram webhook) via ASGI  — FR-46..52
* ``daily_quiz``   — timer: build + push the quiz, project spend (FR-24, FR-38)
* ``ingest_worker`` — queue trigger on ``ingest``: run the pipeline (FR-1..18)

Concrete adapters are constructed by ``quizme.composition.build_deps`` (this is
the ONE place); everything below sees port protocols only.
"""

from __future__ import annotations

import json
import logging

import azure.functions as func

from quizme.application.queue_worker import Deferred, handle_message
from quizme.web.app import app as fastapi_app

log = logging.getLogger("quizme.functions")

# The FastAPI app is served at the site root; Easy Auth gates it at the edge, so
# the function itself is anonymous.
app = func.AsgiFunctionApp(app=fastapi_app, http_auth_level=func.AuthLevel.ANONYMOUS)


def _deps():  # -> quizme.application.deps.Deps
    from quizme.composition import build_deps

    return build_deps()


@app.function_name("daily_quiz")
@app.timer_trigger(schedule="0 30 23 * * *", arg_name="timer", run_on_startup=False)  # 07:30 SGT
def daily_quiz(timer: func.TimerRequest) -> None:
    from quizme.application.quiz import build_daily_quiz

    build_daily_quiz(_deps())


@app.function_name("ingest_worker")
@app.queue_trigger(arg_name="msg", queue_name="ingest", connection="AZURE_QUEUE_CONNECTION")
def ingest_worker(msg: func.QueueMessage) -> None:
    recording_id = json.loads(msg.get_body())["recording_id"]
    try:
        handle_message(recording_id, _deps())
    except Deferred:
        # spend-throttled — re-raise so the host redelivers after the visibility
        # timeout (AD-19 / FR-53); the message is not lost.
        log.warning("ingest deferred (spend throttled): %s", recording_id)
        raise
