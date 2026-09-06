"""LLM — Azure AI Foundry chat deployment via the OpenAI-compatible endpoint
(AD-8, AD-13).

* auth: ``DefaultAzureCredential`` (Managed Identity in Azure) — no API key in prod;
* deployment: ``config.llm.deployment_for(stage)`` — per-stage override (FR-53);
* deployment type must be ``regional`` or ``datazone``, never ``global`` (AD-13);
* structured output enforced via the model's JSON-schema mode;
* every call -> one ``llm_call`` row with token counts + ``est_cost_usd`` (FR-38).
"""

from __future__ import annotations

from dataclasses import dataclass

from quizme.application.config import LLMConfig


@dataclass(slots=True)
class _Result:
    data: dict
    model: str
    input_tokens: int
    output_tokens: int
    est_cost_usd: float


class FoundryLLM:
    def __init__(self, *, config: LLMConfig, credential: object, store: object) -> None:
        self._config = config
        self._credential = credential
        self._store = store  # to write llm_call rows

    def complete_json(
        self,
        *,
        stage: str,
        prompt_version: str,
        system: str,
        user: str,
        schema: dict,
        temperature: float = 0.0,
    ) -> _Result:
        raise NotImplementedError(
            "FoundryLLM.complete_json: AzureOpenAI(azure_endpoint=config.endpoint, "
            "api_version=config.api_version, azure_ad_token_provider=...); "
            "client.chat.completions.create(model=config.deployment_for(stage), "
            "response_format={'type': 'json_schema', 'json_schema': schema}, temperature=..., "
            "messages=[system, user]); parse; price via a per-model rate table -> est_cost_usd; "
            "store.record_llm_call({stage, prompt_version, prompt_hash, model, tokens, est_cost_usd}). "
            "Raise LLMError on failure or unparseable output."
        )
