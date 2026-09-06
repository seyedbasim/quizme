"""Web layer tests — no Azure. Auth is enforced; routes call a fake Deps."""

from __future__ import annotations

import base64
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("WEB_ALLOWED_PRINCIPAL", "user-123")
    # reload auth so it picks up the env var
    import importlib

    from quizme.web import auth

    importlib.reload(auth)

    from quizme.web import app as appmod

    importlib.reload(appmod)
    from quizme.web.deps import get_deps

    fake = _FakeDeps()
    appmod.app.dependency_overrides[get_deps] = lambda: fake

    # telegram_webhook imports get_deps at module scope via a call, patch there too
    from quizme.web.routes import telegram_webhook

    monkeypatch.setattr(telegram_webhook, "get_deps", lambda: fake)
    for mod_name in ("todo", "review", "settings", "browse", "ingestion", "upload"):
        mod = importlib.import_module(f"quizme.web.routes.{mod_name}")
        monkeypatch.setattr(mod, "get_deps", lambda: fake, raising=False)

    with TestClient(appmod.app) as c:
        c.fake = fake
        yield c


def _principal(oid: str) -> str:
    payload = {"claims": [{"typ": "http://schemas.microsoft.com/identity/claims/objectidentifier", "val": oid}]}
    return base64.b64encode(json.dumps(payload).encode()).decode()


class _FakeStore:
    def list_action_items(self, *, status=None, origin=None):
        return []

    def topic_labels(self, ids):
        return {}


class _FakeDeps:
    def __init__(self):
        self.store = _FakeStore()
        self.clock = SimpleNamespace(now=lambda: __import__("datetime").datetime.now(__import__("datetime").UTC))
        self.delivery = SimpleNamespace(
            verify_webhook=lambda *, secret_header, chat_id: secret_header == "s3cr3t" and chat_id == 42,
            send_message=lambda t: None,
        )


def test_healthz_open(client):
    assert client.get("/healthz").json() == {"status": "ok"}


def test_protected_route_needs_principal(client):
    assert client.get("/todo").status_code == 401
    assert client.get("/todo", headers={"X-MS-CLIENT-PRINCIPAL": _principal("someone-else")}).status_code == 403


def test_protected_route_with_allowed_principal(client):
    r = client.get("/todo", headers={"X-MS-CLIENT-PRINCIPAL": _principal("user-123")})
    assert r.status_code == 200
    assert r.json() == {"items": []}


def test_webhook_rejects_bad_secret(client):
    r = client.post(
        "/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"},
        json={"message": {"chat": {"id": 42}, "text": "hi"}},
    )
    assert r.status_code == 403


def test_webhook_accepts_good_secret_no_quiz(client):
    client.fake.store.get_quiz_by_date = lambda d: None
    r = client.post(
        "/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "s3cr3t"},
        json={"message": {"chat": {"id": 42}, "text": "one second"}},
    )
    assert r.status_code == 200
