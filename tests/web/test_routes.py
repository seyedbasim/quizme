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
    from quizme.web import pages

    monkeypatch.setattr(pages, "get_deps", lambda: fake)
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

    def list_review_items(self, *, status="open"):
        return []

    def topic_labels(self, ids):
        return {}

    def load_kus(self):
        return {}

    def all_cards(self):
        return []

    def get_quiz_by_date(self, d):
        return None

    def month_spend_usd(self, *, year, month):
        return 0.0

    def ingestion_status(self, *, limit=50):
        return []


class _FakeConfig:
    ingest = SimpleNamespace(allowed_formats=["m4a"], max_file_mb=200)
    quiz = SimpleNamespace(send_time_local="07:30")
    budget = SimpleNamespace(monthly_credit_usd=150)


class _FakeDeps:
    def __init__(self):
        self.store = _FakeStore()
        self.config = _FakeConfig()
        self.clock = SimpleNamespace(now=lambda: __import__("datetime").datetime.now(__import__("datetime").UTC))
        self.spend = SimpleNamespace(projected_month_end_usd=lambda: 0.0, is_throttled=lambda: False)
        self.delivery = SimpleNamespace(
            verify_webhook=lambda *, secret_header, chat_id: secret_header == "s3cr3t" and chat_id == 42,
            enrol_chat=lambda chat_id: None,
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


def test_dashboard_renders(client):
    r = client.get("/app", headers={"X-MS-CLIENT-PRINCIPAL": _principal("user-123")})
    assert r.status_code == 200
    assert "Dashboard" in r.text and "knowledge units" in r.text


def test_todo_page_renders(client):
    r = client.get("/app/todo", headers={"X-MS-CLIENT-PRINCIPAL": _principal("user-123")})
    assert r.status_code == 200
    assert "To-Do" in r.text


def test_static_css_served(client):
    r = client.get("/static/app.css")
    assert r.status_code == 200 and "--accent" in r.text
