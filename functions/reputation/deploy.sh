#!/bin/bash
set -e

PROJECT_ID=${AGENT_MKT_PROJECT_ID:-$(gcloud config get-value project)}
REGION=${AGENT_MKT_REGION:-us-central1}
if [ -z "$CLOUDSDK_CONFIG" ]; then
  export CLOUDSDK_CONFIG=$(mktemp -d)
fi
CONFIG_DIR="$CLOUDSDK_CONFIG"

export CLOUDSDK_CONFIG="$CONFIG_DIR"

# Navigate to the function directory (where package.json lives)
cd "$(dirname "$0")"

echo "🚀 Deploying Reputation Logic to $PROJECT_ID..."

gcloud functions deploy reputation-guard \
    --gen2 \
    --runtime=nodejs20 \
    --region="$REGION" \
    --source=. \
    --entry-point=updateAgentReputation \
    --trigger-event-filters=type=google.cloud.firestore.document.v1.created \
    --trigger-event-filters=database='(default)' \
    --trigger-event-filters=document='transactions/{txId}' \
    --project="$PROJECT_ID" \
    --quiet

echo "✅ Deployment Complete!"
