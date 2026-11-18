#!/usr/bin/env bash
# Publish the Power BI cost files to Azure Blob Storage with the Azure CLI.
# Uses Azurite (Microsoft's Azure Storage emulator) by default, so no Azure subscription is needed.
# For real Azure: set AZURE_STORAGE_CONNECTION_STRING to your storage account's connection string.
set -euo pipefail

CONTAINER="${CONTAINER:-finops-cost-reports}"
# Azurite's well-known public development account (not a secret).
AZURITE="DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1;"
export AZURE_STORAGE_CONNECTION_STRING="${AZURE_STORAGE_CONNECTION_STRING:-$AZURITE}"

echo "== 1. Build Power BI files"
python -m app.report --out powerbi > /dev/null

echo "== 2. Create blob container $CONTAINER (private)"
az storage container create --name "$CONTAINER" --public-access off --output none

echo "== 3. Upload to Azure Blob Storage"
az storage blob upload-batch --destination "$CONTAINER" --source powerbi --destination-path powerbi --overwrite --output none

echo "== 4. Verify"
az storage blob list --container-name "$CONTAINER" --prefix powerbi/ --query "[].{name:name, bytes:properties.contentLength}" --output table
count=$(az storage blob list --container-name "$CONTAINER" --prefix powerbi/ --query "length(@)" --output tsv)
echo "Uploaded $count files to Azure Blob Storage"
[ "$count" -ge 5 ]
