"""FastAPI application factory.

Run locally: ``uv run uvicorn quizme.web.app:app --reload``
In Azure: wrapped as the HTTP function in ``functions/`` (ASGI).
"""

from __future__ import annotations

from fastapi import Depends, FastAPI

from quizme.web.auth import require_user
from quizme.web.routes import browse, ingestion, review, settings, telegram_webhook, todo, upload

app = FastAPI(title="Quizme", version="0.1.0")

# Every app route requires the single authorised identity (FR-46).
_auth = [Depends(require_user)]

app.include_router(upload.router, dependencies=_auth)
app.include_router(ingestion.router, dependencies=_auth)
app.include_router(review.router, dependencies=_auth)
app.include_router(browse.router, dependencies=_auth)
app.include_router(todo.router, dependencies=_auth)
app.include_router(settings.router, dependencies=_auth)

# Telegram webhook — NOT behind Easy Auth (path excluded); authenticates itself
# by secret token + allowed chat id (AD-10).
app.include_router(telegram_webhook.router)


@app.get("/healthz", include_in_schema=False)
async def healthz() -> dict[str, str]:
    """Unauthenticated liveness probe."""
    return {"status": "ok"}
