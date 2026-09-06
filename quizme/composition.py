"""Composition root — builds the :class:`quizme.application.deps.Deps` bundle
from environment configuration.

Used by ``functions/function_app.py`` (Azure) and local scripts. This is the ONE
place concrete adapters are wired; everything below sees port protocols only
(AD-11).

Auth: if ``AZURE_OPENAI_API_KEY`` / ``AZURE_SPEECH_KEY`` are set (local dev) they
are used; otherwise ``DefaultAzureCredential`` → Managed Identity in Azure.
"""

from __future__ import annotations

import os

from quizme.application.config import Config, load
from quizme.application.deps import Deps
from quizme.application.spend import SpendMeterImpl


def build_deps(config: Config | None = None) -> Deps:
    from azure.identity import DefaultAzureCredential

    from quizme.adapters.delivery_telegram import TelegramDelivery
    from quizme.adapters.embedder_foundry import FoundryEmbedder
    from quizme.adapters.intake_azure import AzureRecordingIntake
    from quizme.adapters.llm_foundry import FoundryLLM
    from quizme.adapters.misc import LLMGrader, SystemClock
    from quizme.adapters.store_postgres import PostgresStore
    from quizme.adapters.transcriber_speech import AzureSpeechTranscriber

    cfg = config or load()
    cred = DefaultAzureCredential()
    aoai_key = os.environ.get("AZURE_OPENAI_API_KEY") or None
    speech_key = os.environ.get("AZURE_SPEECH_KEY") or None

    store = PostgresStore(_require("DATABASE_URL"))
    llm = FoundryLLM(config=cfg.llm, sink=store, api_key=aoai_key)
    clock = SystemClock()

    return Deps(
        config=cfg,
        clock=clock,
        store=store,
        llm=llm,
        transcriber=AzureSpeechTranscriber(  # type: ignore[arg-type]  # structural match; nested-Protocol variance
            region=os.environ.get("AZURE_SPEECH_REGION", cfg.app.region),
            api_key=speech_key,
            credential=cred,
        ),
        embedder=FoundryEmbedder(embeddings=cfg.embeddings, llm=cfg.llm, api_key=aoai_key),
        intake=AzureRecordingIntake(
            blob_account_url=_require("AZURE_BLOB_ACCOUNT_URL"),
            queue_account_url=_require("AZURE_QUEUE_ACCOUNT_URL"),
            store=store,
            credential=cred,
        ),
        delivery=TelegramDelivery(
            bot_token=_require("TELEGRAM_BOT_TOKEN"),
            allowed_chat_id=int(_require("TELEGRAM_ALLOWED_CHAT_ID")),
            webhook_secret=_require("TELEGRAM_WEBHOOK_SECRET"),
        ),
        grader=LLMGrader(llm),
        spend=SpendMeterImpl(store=store, clock=clock, budget=cfg.budget),
    )


def _require(name: str) -> str:
    v = os.environ.get(name)
    if not v:
        raise RuntimeError(f"missing required environment variable: {name}")
    return v
