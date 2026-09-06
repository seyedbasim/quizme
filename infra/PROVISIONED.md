# Provisioned resources

Subscription `Basim-MCTv2` (`c136ba5f-36d9-490d-92c1-01475f282cd3`), tenant
`45af99f3-…`, resource group **`rg-quizme`**, region **`southeastasia`**.
Suffix `96616d`. Provisioned 2026-09-06.

| Resource | Name | Notes |
| --- | --- | --- |
| Storage account | `stquizme96616d` | Standard LRS. Containers `recordings`, `transcripts`. Queues `ingest`, `ingest-poison`. |
| PostgreSQL Flexible | `psql-quizme-96616d` | Burstable B1ms, 32 GB, PG 16. `pgvector` 0.8.2 enabled. DB `quizme`, migration `0001` applied. Admin `quizadmin` (password in KV). Firewall: home IP + Azure services. |
| Azure OpenAI (Foundry) | `aoai-quizme-96616d` | System-assigned identity. Deployments: `chat` = `gpt-5-mini` GlobalStandard 50K TPM; `embed` = `text-embedding-3-small` GlobalStandard 50K TPM. |
| Azure AI Speech | `spch-quizme-96616d` | S0. Endpoint `https://southeastasia.api.cognitive.microsoft.com/`. |
| Key Vault | `kv-quizme-96616d` | RBAC auth. Secrets: `database-url`, `pg-admin-password`, `aoai-api-key`, `speech-api-key`, `web-allowed-principal`, `telegram-bot-token`, `telegram-webhook-secret`, `easyauth-client-secret`. |
| Log Analytics | `log-quizme-96616d` | — |
| Application Insights | `appi-quizme-96616d` | workspace-based, linked to the Function App |
| **Function App** | `func-quizme-96616d` | **Flex Consumption**, Linux, Python 3.12, `httpsOnly`. Host `func-quizme-96616d.azurewebsites.net`. `host.json` `routePrefix=""` (serves at root). System-assigned MI `c800203f-…`. **No code deployed yet.** |
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
| Cognitive Services OpenAI User | `aoai-quizme-96616d` |
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

## Still to do

- [x] ~~Telegram bot~~ — created; token + webhook secret in KV.
- [x] ~~Function App + App Insights~~ — done.
- [x] ~~Managed Identity RBAC~~ — 5 roles granted.
- [x] ~~Easy Auth~~ — v2, require-auth, assignment-required, single user.
- [ ] **`TELEGRAM_ALLOWED_CHAT_ID`** — message `@basimquizme_bot`, then
      `curl https://api.telegram.org/bot<token>/getUpdates` to read the chat id;
      set it as a Function App app setting.
- [ ] **Implement the adapters + `functions/function_app.py::_build_deps()`** (code, not infra).
- [ ] **Deploy** — `cd functions && func azure functionapp publish func-quizme-96616d`,
      or push to `main` (GitHub Actions `deploy.yml` — needs repo secrets
      `AZURE_CREDENTIALS`, `AZURE_FUNCTIONAPP_NAME`, `DATABASE_URL`).
- [ ] **Set the webhook** once deployed:
      `curl "https://api.telegram.org/bot<token>/setWebhook" -d url=https://func-quizme-96616d.azurewebsites.net/telegram/webhook -d secret_token=<webhook-secret>`
- [ ] **Postgres Entra auth** (optional hardening) — currently password auth via
      the `database-url` KV secret. Move the MI to an Entra DB role later.
- [ ] Blob lifecycle → Cool tier (PRD Open Q 7).

## Local dev

```bash
export DATABASE_URL="$(az keyvault secret show --vault-name kv-quizme-96616d -n database-url --query value -o tsv)"
export AZURE_OPENAI_ENDPOINT="https://aoai-quizme-96616d.openai.azure.com"
export AZURE_OPENAI_API_KEY="$(az keyvault secret show --vault-name kv-quizme-96616d -n aoai-api-key --query value -o tsv)"
export AZURE_SPEECH_KEY="$(az keyvault secret show --vault-name kv-quizme-96616d -n speech-api-key --query value -o tsv)"
export AZURE_SPEECH_REGION=southeastasia
```
