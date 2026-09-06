"""Delivery — Telegram bot, webhook mode (AD-10).

The only component with outbound traffic off Azure. Carries generated Questions,
model answers, and user Answers ONLY — never audio, transcripts, sources, notes,
or the KB (PRD §5.2).

Chat-id resolution: ``TELEGRAM_ALLOWED_CHAT_ID`` env if set, otherwise the value
the webhook self-enrolled into ``app_setting['telegram_chat_id']`` on first
contact. Until a chat id is known, ``verify_webhook`` accepts any chat (so the
first message can enrol) and outbound sends raise.
"""

from __future__ import annotations

import hmac
from typing import Any

import httpx

from quizme.domain.errors import AdapterError

_SETTING = "telegram_chat_id"


class TelegramDelivery:
    def __init__(self, *, bot_token: str, webhook_secret: str, store: Any, allowed_chat_id: int | None = None) -> None:
        self._base = f"https://api.telegram.org/bot{bot_token}"
        self._webhook_secret = webhook_secret
        self._store = store
        self._env_chat_id = allowed_chat_id

    def _chat_id(self) -> int | None:
        if self._env_chat_id is not None:
            return self._env_chat_id
        val = self._store.get_setting(_SETTING)
        return int(val) if val is not None else None

    def enrol_chat(self, chat_id: int) -> None:
        if self._chat_id() is None:
            self._store.set_setting(_SETTING, chat_id)

    def verify_webhook(self, *, secret_header: str, chat_id: int) -> bool:
        if not self._webhook_secret or not hmac.compare_digest(secret_header or "", self._webhook_secret):
            return False
        known = self._chat_id()
        return known is None or chat_id == known

    def send_message(self, text: str) -> None:
        self._post("sendMessage", {"chat_id": self._require_chat(), "text": text})

    def send_question(self, *, question_id: str, prompt: str) -> None:
        self._post(
            "sendMessage",
            {
                "chat_id": self._require_chat(),
                "text": prompt,
                "reply_markup": {
                    "inline_keyboard": [[{"text": "🚩 dispute", "callback_data": f"dispute:{question_id}"}]]
                },
            },
        )

    def _require_chat(self) -> int:
        cid = self._chat_id()
        if cid is None:
            raise AdapterError("no Telegram chat id yet — send the bot a message first")
        return cid

    def _post(self, method: str, payload: dict) -> None:
        try:
            r = httpx.post(f"{self._base}/{method}", json=payload, timeout=30.0)
            r.raise_for_status()
            if not r.json().get("ok"):
                raise AdapterError(f"telegram {method}: {r.text}")
        except AdapterError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise AdapterError(f"telegram {method} failed: {exc}") from exc
