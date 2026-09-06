"""Delivery — Telegram bot, webhook mode (AD-10).

The only component with outbound traffic off Azure. Carries generated Questions,
model answers, and user Answers ONLY — never audio, transcripts, sources, notes,
or the KB (PRD §5.2).

Outbound calls go straight to the Bot API over HTTPS. Inbound updates arrive at
the ``/telegram/webhook`` route (excluded from Easy Auth); ``verify_webhook``
checks the secret token + the single allowed chat id.
"""

from __future__ import annotations

import hmac

import httpx

from quizme.domain.errors import AdapterError


class TelegramDelivery:
    def __init__(self, *, bot_token: str, allowed_chat_id: int, webhook_secret: str) -> None:
        self._base = f"https://api.telegram.org/bot{bot_token}"
        self._chat_id = allowed_chat_id
        self._webhook_secret = webhook_secret

    def send_message(self, text: str) -> None:
        self._post("sendMessage", {"chat_id": self._chat_id, "text": text})

    def send_question(self, *, question_id: str, prompt: str) -> None:
        self._post(
            "sendMessage",
            {
                "chat_id": self._chat_id,
                "text": prompt,
                "reply_markup": {
                    "inline_keyboard": [[{"text": "🚩 dispute", "callback_data": f"dispute:{question_id}"}]]
                },
            },
        )

    def verify_webhook(self, *, secret_header: str, chat_id: int) -> bool:
        return (
            bool(self._webhook_secret)
            and hmac.compare_digest(secret_header or "", self._webhook_secret)
            and chat_id == self._chat_id
        )

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
