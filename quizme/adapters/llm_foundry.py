"""LLM — Azure AI Foundry chat deployment via the OpenAI-compatible endpoint
(AD-8, AD-13).

* auth: ``DefaultAzureCredential`` (Managed Identity in Azure); falls back to an
  API key from ``AZURE_OPENAI_API_KEY`` for local dev.
* deployment: ``config.llm.deployment_for(stage)`` — per-stage override (FR-53).
* structured output via the model's ``json_schema`` response format.
* every call writes one ``llm_call`` row (tokens, latency, est_cost) → SpendMeter (FR-38).

The deployed model (``gpt-5-mini``) is a reasoning model: it takes
``max_completion_tokens`` (not ``max_tokens``) and does not accept a custom
``temperature`` — the port's ``temperature`` arg is therefore advisory here.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from quizme.application.config import LLMConfig
from quizme.domain.errors import LLMError
from quizme.domain.ids import text_hash

# $/1M tokens (input, output). Placeholder rates — replace with the real Foundry
# rate card for the deployed models. Used only for the running-cost estimate.
_RATES: dict[str, tuple[float, float]] = {
    "gpt-5-mini": (0.25, 2.00),
    "gpt-5": (1.25, 10.00),
    "gpt-4.1": (2.00, 8.00),
    "gpt-4.1-mini": (0.40, 1.60),
    "text-embedding-3-small": (0.02, 0.0),
}
_DEFAULT_RATE = (1.0, 4.0)
_REASONING = re.compile(r"(^|[-_/])(o[134]|gpt-5)")


class _CallSink(Protocol):
    def record_llm_call(self, row: dict) -> None: ...


@dataclass(slots=True)
class LLMResultImpl:
    data: dict
    model: str
    input_tokens: int
    output_tokens: int
    est_cost_usd: float


class FoundryLLM:
    def __init__(self, *, config: LLMConfig, sink: _CallSink, api_key: str | None = None) -> None:
        self._config = config
        self._sink = sink
        self._client = _make_client(config, api_key)
        self._max_completion_tokens = 8000

    def complete_json(
        self,
        *,
        stage: str,
        prompt_version: str,
        system: str,
        user: str,
        schema: dict,
        temperature: float = 0.0,
    ) -> LLMResultImpl:
        deployment = self._config.deployment_for(stage)
        kwargs: dict[str, Any] = {
            "model": deployment,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": f"{stage}_out", "schema": schema, "strict": True},
            },
            "max_completion_tokens": self._max_completion_tokens,
        }
        if temperature is not None and not _REASONING.search(deployment):
            kwargs["temperature"] = temperature

        started = time.perf_counter()
        resp = self._create(kwargs, stage)
        latency_ms = int((time.perf_counter() - started) * 1000)

        choice = resp.choices[0]
        content = choice.message.content
        if not content:
            raise LLMError(f"{stage}: empty response (finish_reason={choice.finish_reason})")
        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            raise LLMError(f"{stage}: response was not valid JSON: {exc}") from exc

        usage = resp.usage
        in_tok = usage.prompt_tokens if usage else 0
        out_tok = usage.completion_tokens if usage else 0
        rate_in, rate_out = _RATES.get(_base_model(resp.model or deployment), _DEFAULT_RATE)
        cost = in_tok / 1_000_000 * rate_in + out_tok / 1_000_000 * rate_out

        self._sink.record_llm_call(
            {
                "ts": datetime.now(UTC),
                "stage": stage,
                "prompt_version": prompt_version,
                "prompt_hash": text_hash(system + "\x1f" + user),
                "model": resp.model or deployment,
                "input_tokens": in_tok,
                "output_tokens": out_tok,
                "latency_ms": latency_ms,
                "est_cost_usd": round(cost, 6),
            }
        )
        return LLMResultImpl(data, resp.model or deployment, in_tok, out_tok, round(cost, 6))

    def _create(self, kwargs: dict[str, Any], stage: str) -> Any:
        """Call the API; if the model rejects an unsupported param (temperature on
        a reasoning model), drop it and retry once."""
        try:
            return self._client.chat.completions.create(**kwargs)
        except Exception as exc:  # noqa: BLE001
            msg = str(exc)
            if "temperature" in kwargs and "temperature" in msg and "unsupported" in msg.lower():
                kwargs.pop("temperature")
                try:
                    return self._client.chat.completions.create(**kwargs)
                except Exception as exc2:  # noqa: BLE001
                    raise LLMError(f"{stage}: chat.completions failed: {exc2}") from exc2
            raise LLMError(f"{stage}: chat.completions failed: {exc}") from exc


def _base_model(name: str) -> str:
    # "gpt-5-mini-2025-08-07" -> "gpt-5-mini"
    return re.sub(r"-\d{4}-\d{2}-\d{2}$", "", name)


def _make_client(config: LLMConfig, api_key: str | None) -> Any:
    from openai import AzureOpenAI  # noqa: PLC0415

    if api_key:
        return AzureOpenAI(azure_endpoint=config.endpoint, api_version=config.api_version, api_key=api_key)
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider  # noqa: PLC0415

    token_provider = get_bearer_token_provider(DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default")
    return AzureOpenAI(
        azure_endpoint=config.endpoint,
        api_version=config.api_version,
        azure_ad_token_provider=token_provider,
    )
