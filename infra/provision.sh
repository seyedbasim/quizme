#!/usr/bin/env bash
# Starting-point provisioning. Review every line before running — this spends
# real credit against a hard $150/mo cap. Not idempotent; not IaC.
set -euo pipefail

LOCATION="southeastasia"
RG="rg-quizme-sea"
PREFIX="quizme$RANDOM"

az group create -n "$RG" -l "$LOCATION"

az storage account create -n "${PREFIX}sa" -g "$RG" -l "$LOCATION" --sku Standard_LRS
az storage container create --account-name "${PREFIX}sa" -n recordings
az storage container create --account-name "${PREFIX}sa" -n transcripts
az storage queue create --account-name "${PREFIX}sa" -n ingest

az postgres flexible-server create -g "$RG" -n "${PREFIX}-pg" -l "$LOCATION" \
  --tier Burstable --sku-name Standard_B1ms --storage-size 32 --version 16 \
  --active-directory-auth Enabled --password-auth Disabled
# then: az postgres flexible-server parameter set -g "$RG" -s "${PREFIX}-pg" \
#         --name azure.extensions --value VECTOR

az keyvault create -n "kv-${PREFIX}" -g "$RG" -l "$LOCATION"

# Foundry (Azure OpenAI) + Speech — confirm model availability/quota FIRST (Open Q 13):
#   az cognitiveservices account list-skus --location southeastasia --kind OpenAI
az cognitiveservices account create -n "${PREFIX}-aoai" -g "$RG" -l "$LOCATION" \
  --kind OpenAI --sku S0
az cognitiveservices account create -n "${PREFIX}-speech" -g "$RG" -l "$LOCATION" \
  --kind SpeechServices --sku S0

echo "Now: create model deployments (regional/datazone, NOT global), the Function App"
echo "(Flex Consumption), wire Managed Identity RBAC, and enable Easy Auth. See README.md."
