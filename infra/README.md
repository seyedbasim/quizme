# Infrastructure

Region: **`southeastasia`** (Azure Singapore — PRD Open Q 11).
Subscription: the Visual Studio Enterprise (MCT) one — **dev/test terms, $150/mo hard cap.**

## Resources to provision

| Resource | SKU / notes |
| --- | --- |
| Resource group | `rg-quizme-sea` |
| Storage account | Standard LRS — Blob container `recordings`, `transcripts`; Queue `ingest` + `ingest-poison` |
| PostgreSQL Flexible Server | Burstable **B1ms**, 32 GB, `pgvector` (Server Parameters → `azure.extensions`), Entra auth on |
| Azure AI Foundry (Azure OpenAI) | chat deployment (confirm **regional or datazone** availability + quota in `southeastasia` — Open Q 13); embeddings deployment |
| Azure AI Speech | for batch/fast transcription (Whisper) — region `southeastasia` |
| Function App | **Flex Consumption**, Linux, Python 3.12; system-assigned Managed Identity |
| Key Vault | `kv-quizme-sea`; grant the Function App's identity `get`/`list` on secrets |
| Application Insights | linked to the Function App |

## Identity & secrets (AD-17)

- Function App Managed Identity gets:
  - `Storage Blob Data Contributor` + `Storage Queue Data Contributor` on the storage account
  - `Cognitive Services User` on the Foundry + Speech resources
  - Postgres: an Entra role mapped to the identity (no DB password)
  - Key Vault: `Key Vault Secrets User`
- Secrets in Key Vault: `telegram-bot-token`, `telegram-webhook-secret`, `telegram-allowed-chat-id`, `web-allowed-principal`.

## Auth (AD-10)

Enable App Service Authentication ("Easy Auth") on the Function App, Microsoft
identity provider, **"Require authentication"**, and set the enterprise app to
**"Assignment required"** with only your account assigned.

## Deploy

`.github/workflows/deploy.yml`: build, `alembic upgrade head`, `func azure functionapp publish`.

> This is a checklist, not IaC. Bicep/Terraform is deferred (architecture-spine → Deferred).
> `provision.sh` is a starting point.
