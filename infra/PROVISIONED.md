# Provisioned resources

Subscription `Basim-MCTv2` (`c136ba5f-36d9-490d-92c1-01475f282cd3`), tenant
`45af99f3-…`, resource group **`rg-quizme`**, region **`southeastasia`**.
Suffix `96616d`. Provisioned 2026-09-06.

**Status: DEPLOYED and live** (2026-09-07). `func-quizme-96616d.azurewebsites.net`
serves the web app (Easy Auth) + `/telegram/webhook`; `daily_quiz` timer and
`ingest_worker` queue trigger registered. Migrations `0001`+`0002` applied. Telegram
webhook set, chat id `7432349917` locked via KV secret `telegram-allowed-chat-id`.
Verified end-to-end: HTTP app, Managed Identity → Postgres/Blob/Queue/Foundry/KV,
Telegram outbound, queue worker (`build_deps` + pipeline `execute` + poison-queue
dead-lettering).

| Resource | Name | Notes |
| --- | --- | --- |
| Storage account | `stquizme96616d` | Standard LRS. Containers `recordings`, `transcripts`. Queues `ingest`, `ingest-poison`. |
| PostgreSQL Flexible | `psql-quizme-96616d` | Burstable B1ms, 32 GB, PG 16. `pgvector` 0.8.2 enabled. DB `quizme`, migration `0001` applied. Admin `quizadmin` (password in KV). Firewall: home IP + Azure services. |
| AI Foundry (live) | `seyedbasim95-2118-resource` (project `seyedbasim95-2118`) | `AIServices` kind. **In use as of 2026-09-07.** Deployments: `gpt-5-mini` = `gpt-5-mini` 2025-08-07 GlobalStandard 225K TPM; `embed` = `text-embedding-3-small` GlobalStandard 50K TPM. Endpoint `https://seyedbasim95-2118-resource.openai.azure.com`. |
| Azure OpenAI (legacy, idle) | `aoai-quizme-96616d` | System-assigned identity. Deployments: `chat` = `gpt-5-mini` GlobalStandard 50K TPM; `embed` = `text-embedding-3-small` GlobalStandard 50K TPM. No longer referenced by the app — kept as fallback, safe to delete. |
| Azure AI Speech | `spch-quizme-96616d` | S0. Endpoint `https://southeastasia.api.cognitive.microsoft.com/`. |
| Key Vault | `kv-quizme-96616d` | RBAC auth. Secrets: `database-url`, `pg-admin-password`, `aoai-api-key`, `speech-api-key`, `web-allowed-principal`, `telegram-bot-token`, `telegram-webhook-secret`, `easyauth-client-secret`. |
| Log Analytics | `log-quizme-96616d` | — |
| Application Insights | `appi-quizme-96616d` | workspace-based, linked to the Function App |
| **Function App** | `func-quizme-96616d` | **Flex Consumption**, Linux, Python 3.12, `httpsOnly`. `func-quizme-96616d.azurewebsites.net`. `host.json` `routePrefix=""`. System MI `c800203f-…`. **Deployed** — functions: `http_app_func`, `daily_quiz`, `ingest_worker`. |
| Entra app (Easy Auth) | `Quizme` — appId `2692dde1-b3b2-4558-aa37-93f44131a454`, SP `eec59ee5-…` | Single-tenant. **Assignment required = true**; only my user assigned. |

## Function App configuration

- **App settings:** `QUIZME_CONFIG`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_VERSION`, `AZURE_SPEECH_REGION`, `AZURE_BLOB_ACCOUNT_URL`, `AZURE_QUEUE_ACCOUNT_URL`, `AZURE_KEY_VAULT_URL`, `WEB_ALLOWED_PRINCIPAL` (my oid), `AZURE_QUEUE_CONNECTION__queueServiceUri` + `__credential=managedidentity` (MI queue trigger), `MICROSOFT_PROVIDER_AUTHENTICATION_SECRET`.
- **Key Vault references (all resolve OK):** `DATABASE_URL`, `AZURE_SPEECH_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`.
- **Pending:** `TELEGRAM_ALLOWED_CHAT_ID` — waiting on the chat id (message the bot, then `getUpdates`).
- **Easy Auth (v2):** require authentication, `RedirectToLoginPage` for browsers (401 for API clients), AAD provider, `excludedPaths = ["/healthz", "/telegram/webhook"]`, token store on. Verified: `/upload` → 401, `/healthz` and `/telegram/webhook` pass through.

## MI RBAC (Function App identity `c800203f-…`)

| Role | Scope |
| --- | --- |
| Storage Blob Data Contributor | `stquizme96616d` |
| Storage Queue Data Contributor | `stquizme96616d` |
| Cognitive Services OpenAI User | `seyedbasim95-2118-resource` (live), `aoai-quizme-96616d` (legacy) |
| Cognitive Services User | `spch-quizme-96616d` |
| Key Vault Secrets User | `kv-quizme-96616d` |

## Telegram

- Bot: `@basimquizme_bot`. Token in KV (`telegram-bot-token`).
- Webhook URL (set after deploy): `https://func-quizme-96616d.azurewebsites.net/telegram/webhook`
  with `secret_token` = KV `telegram-webhook-secret`.

## Deviations from the design (recorded in PRD §5.2 / AD-13)

1. **No Regional / DataZone chat+embedding deployment.** Top-tier models
   (`gpt-4.1`, `gpt-5.2`, `gpt-5.4`) have **0 default quota** on this subscription
   in `southeastasia`; `DataZoneStandard` deployments create but return
   `DeploymentNotFound`. Running `GlobalStandard` → inference may be processed
   outside Singapore.
2. **Model is `gpt-5-mini`, not top-tier**, for the same quota reason.

**To close:** Portal → Azure OpenAI → Quotas → request an increase for
`gpt-5.2` (or `gpt-4.1`) on `DataZoneStandard` in Southeast Asia. When granted,
add a deployment and update `config.toml` `[llm]`.

## RBAC granted

| Principal | Role | Scope |
| --- | --- | --- |
| me (`9d0d3472-…`) | Key Vault Secrets Officer | KV |
| me | Cognitive Services OpenAI User | AOAI |
| me | Cognitive Services User | Speech |

> RBAC on Cognitive Services can take 5–15 min to propagate; API-key auth works
> immediately (`localAuth` not disabled) and is the local-dev path.

## Done

- [x] Telegram bot + secrets in KV
- [x] Function App + App Insights + MI RBAC + Easy Auth
- [x] `TELEGRAM_ALLOWED_CHAT_ID` (KV secret `telegram-allowed-chat-id` = 7432349917)
- [x] All adapters + pipeline + quiz + web implemented and deployed
- [x] `setWebhook` → `https://func-quizme-96616d.azurewebsites.net/telegram/webhook`
- [x] Migrations `0001`, `0002` applied to the live DB

## Follow-ups (not blocking)

- [ ] Move Postgres auth to Entra (MI DB role) instead of the KV password.
- [ ] Blob lifecycle → Cool tier (PRD Open Q 7).
- [ ] Infrastructure-as-code (Bicep) for the estate.
- [ ] Request a DataZone/top-tier Foundry quota to replace `gpt-5-mini` (PRD §5.2).
- [ ] A few orphan `stage_run` rows from a synthetic worker test — harmless.

## Local dev

```bash
export DATABASE_URL="$(az keyvault secret show --vault-name kv-quizme-96616d -n database-url --query value -o tsv)"
export AZURE_OPENAI_ENDPOINT="https://seyedbasim95-2118-resource.openai.azure.com"
export AZURE_OPENAI_API_KEY="$(az keyvault secret show --vault-name kv-quizme-96616d -n aoai-api-key --query value -o tsv)"
export AZURE_SPEECH_KEY="$(az keyvault secret show --vault-name kv-quizme-96616d -n speech-api-key --query value -o tsv)"
export AZURE_SPEECH_REGION=southeastasia
```
