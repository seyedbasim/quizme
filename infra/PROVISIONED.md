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
| Key Vault | `kv-quizme-96616d` | RBAC auth. Secrets: `database-url`, `pg-admin-password`, `aoai-api-key`, `speech-api-key`, `web-allowed-principal`. |

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

## Still to provision

- [ ] **Telegram bot** — create via @BotFather; store `telegram-bot-token`,
      `telegram-webhook-secret`, `telegram-allowed-chat-id` in KV.
- [ ] **Function App** (Flex Consumption, Linux, Python 3.12) + its storage
      account + Application Insights.
- [ ] **Managed Identity RBAC** for the Function App: Blob Data Contributor +
      Queue Data Contributor on `stquizme96616d`; Cognitive Services OpenAI User
      on `aoai-quizme-96616d`; Cognitive Services User on `spch-quizme-96616d`;
      Key Vault Secrets User on `kv-quizme-96616d`; a Postgres Entra role.
- [ ] **Easy Auth** on the Function App — Microsoft identity, "Require
      authentication", enterprise app "Assignment required", only my account.
- [ ] Deploy the code; set the webhook.

## Local dev

```bash
export DATABASE_URL="$(az keyvault secret show --vault-name kv-quizme-96616d -n database-url --query value -o tsv)"
export AZURE_OPENAI_ENDPOINT="https://aoai-quizme-96616d.openai.azure.com"
export AZURE_OPENAI_API_KEY="$(az keyvault secret show --vault-name kv-quizme-96616d -n aoai-api-key --query value -o tsv)"
export AZURE_SPEECH_KEY="$(az keyvault secret show --vault-name kv-quizme-96616d -n speech-api-key --query value -o tsv)"
export AZURE_SPEECH_REGION=southeastasia
```
