"""Delivery — Telegram bot, webhook mode (AD-10).

The only component with outbound traffic off Azure. Carries generated Questions,
model answers, and user Answers ONLY — never audio, transcripts, sources, notes,
or the KB (PRD §5.2).

Webhook auth: ``X-Telegram-Bot-Api-Secret-Token`` must equal
``TELEGRAM_WEBHOOK_SECRET``; the update's ``chat.id`` must equal the single
``TELEGRAM_ALLOWED_CHAT_ID`` (AD-10).
"""

from __future__ import annotations


class TelegramDelivery:
    def __init__(self, *, bot_token: str, allowed_chat_id: int, webhook_secret: str) -> None:
        self._token = bot_token
        self._chat_id = allowed_chat_id
        self._webhook_secret = webhook_secret

    def send_message(self, text: str) -> None:
        raise NotImplementedError("Bot(token).send_message(chat_id=self._chat_id, text=text)")

    def send_question(self, *, question_id: str, prompt: str) -> None:
        raise NotImplementedError(
            "send the question with an inline keyboard: [answer inline] [dispute] (FR-26/FR-31); "
            "callback_data carries question_id"
        )

    def verify_webhook(self, *, secret_header: str, chat_id: int) -> bool:
        import hmac

        return (
            bool(self._webhook_secret)
            and hmac.compare_digest(secret_header, self._webhook_secret)
            and chat_id == self._chat_id
        )
