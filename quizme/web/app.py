"""FastAPI application factory.

Run locally: ``uv run uvicorn quizme.web.app:app --reload``
In Azure: the ``http_app`` function in ``function_app.py`` wraps this via ASGI.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from quizme.web import pages
from quizme.web.auth import require_user
from quizme.web.routes import browse, ingestion, review, settings, telegram_webhook, todo, upload

app = FastAPI(title="Quizme", version="0.1.0")

# Every app + UI route requires the single authorised identity (FR-46). Easy Auth
# also gates this at the platform edge; this is belt-and-braces.
_auth = [Depends(require_user)]

# JSON API
app.include_router(upload.router, dependencies=_auth)
app.include_router(ingestion.router, dependencies=_auth)
app.include_router(review.router, dependencies=_auth)
app.include_router(browse.router, dependencies=_auth)
app.include_router(todo.router, dependencies=_auth)
app.include_router(settings.router, dependencies=_auth)

# Server-rendered UI
app.include_router(pages.router, dependencies=_auth)

# Telegram webhook — NOT behind Easy Auth (path excluded); self-authenticates
# by secret token + allowed chat id (AD-10).
app.include_router(telegram_webhook.router)

app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")


@app.get("/", include_in_schema=False)
async def index() -> RedirectResponse:
    return RedirectResponse("/app")


@app.get("/healthz", include_in_schema=False)
async def healthz() -> dict[str, str]:
    """Unauthenticated liveness probe."""
    return {"status": "ok"}
