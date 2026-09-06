"""Azure Functions host — the serverless composition root (AD-16, AD-17, AD-19).

Three functions, all scale-to-zero:

* ``http_app``    — the FastAPI ASGI app (UI + JSON API + Telegram webhook), FR-46..52
* ``daily_quiz``  — timer: build + push the quiz, project spend (FR-24, FR-38)
* ``ingest_worker`` — queue trigger on ``ingest``: run the pipeline (FR-1..18)

This is the ONLY place concrete adapters are constructed. Everything below the
composition root sees port protocols only.
"""

from __future__ import annotations

import logging

import azure.functions as func

from quizme.application.queue_worker import handle_message

app = func.FunctionApp()
log = logging.getLogger("quizme.functions")


def _build_deps():  # -> quizme.application.deps.Deps
    """Compose adapters from app settings / Key Vault references."""
    from quizme.composition import build_deps  # noqa: PLC0415

    return build_deps()


# --- HTTP: the FastAPI app --------------------------------------------------
@app.function_name("http_app")
@app.route(route="{*path}", auth_level=func.AuthLevel.ANONYMOUS)  # Easy Auth is at the edge
async def http_app(req: func.HttpRequest, context: func.Context) -> func.HttpResponse:
    from azure.functions import AsgiMiddleware  # noqa: PLC0415

    from quizme.web.app import app as fastapi_app  # noqa: PLC0415

    return await AsgiMiddleware(fastapi_app).handle_async(req, context)


# --- Timer: daily quiz ----------------------------------------------------
@app.function_name("daily_quiz")
@app.timer_trigger(schedule="0 30 23 * * *", arg_name="timer", run_on_startup=False)  # 07:30 SGT = 23:30 UTC
def daily_quiz(timer: func.TimerRequest) -> None:
    from quizme.application.quiz import build_daily_quiz  # noqa: PLC0415

    deps = _build_deps()
    build_daily_quiz(deps)


# --- Queue: ingestion worker -------------------------------------------
@app.function_name("ingest_worker")
@app.queue_trigger(arg_name="msg", queue_name="ingest", connection="AZURE_QUEUE_CONNECTION")
def ingest_worker(msg: func.QueueMessage) -> None:
    import json  # noqa: PLC0415

    deps = _build_deps()
    recording_id = json.loads(msg.get_body())["recording_id"]
    handle_message(recording_id, deps)
