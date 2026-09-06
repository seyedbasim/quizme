"""FastAPI application factory.

Run locally: ``uv run uvicorn quizme.web.app:app --reload``
In Azure: wrapped as the HTTP function in ``functions/`` (ASGI).
"""

from __future__ import annotations

from fastapi import Depends, FastAPI

from quizme.web.auth import require_user
from quizme.web.routes import browse, ingestion, review, settings, todo, upload

app = FastAPI(title="Quizme", version="0.1.0")

# Every route requires the single authorised identity (FR-46).
_auth = [Depends(require_user)]

app.include_router(upload.router, dependencies=_auth)
app.include_router(ingestion.router, dependencies=_auth)
app.include_router(review.router, dependencies=_auth)
app.include_router(browse.router, dependencies=_auth)
app.include_router(todo.router, dependencies=_auth)
app.include_router(settings.router, dependencies=_auth)


@app.get("/healthz", include_in_schema=False)
async def healthz() -> dict[str, str]:
    """Unauthenticated liveness probe."""
    return {"status": "ok"}


# The Telegram webhook is mounted here too (separate auth — secret token, AD-10).
# from quizme.web.routes import telegram_webhook
# app.include_router(telegram_webhook.router)
