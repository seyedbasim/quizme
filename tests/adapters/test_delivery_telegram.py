"""TelegramDelivery — chat-id self-enrolment + webhook verification (no network)."""

from __future__ import annotations

import pytest

from quizme.adapters.delivery_telegram import TelegramDelivery
from quizme.domain.errors import AdapterError


class _Store:
    def __init__(self) -> None:
        self.settings: dict[str, object] = {}

    def get_setting(self, key: str) -> object:
        return self.settings.get(key)

    def set_setting(self, key: str, value: object) -> None:
        self.settings[key] = value


def _d(store, *, secret="sek", chat=None) -> TelegramDelivery:
    return TelegramDelivery(bot_token="t", webhook_secret=secret, store=store, allowed_chat_id=chat)


def test_verify_rejects_bad_secret() -> None:
    d = _d(_Store())
    assert d.verify_webhook(secret_header="nope", chat_id=1) is False


def test_first_contact_enrols_then_locks() -> None:
    store = _Store()
    d = _d(store)
    # any chat accepted while unenrolled
    assert d.verify_webhook(secret_header="sek", chat_id=555) is True
    d.enrol_chat(555)
    assert store.settings["telegram_chat_id"] == 555
    # now only that chat
    assert d.verify_webhook(secret_header="sek", chat_id=555) is True
    assert d.verify_webhook(secret_header="sek", chat_id=999) is False
    # enrol is idempotent
    d.enrol_chat(999)
    assert store.settings["telegram_chat_id"] == 555


def test_env_chat_id_wins() -> None:
    d = _d(_Store(), chat=42)
    assert d.verify_webhook(secret_header="sek", chat_id=42) is True
    assert d.verify_webhook(secret_header="sek", chat_id=43) is False


def test_send_without_chat_raises() -> None:
    with pytest.raises(AdapterError, match="chat id"):
        _d(_Store()).send_message("hi")
