#!/usr/bin/env bash
# One-time bootstrap of the Pulumi self-managed state backend for Collateral AI.
# Creates a versioned GCS bucket for state + a GCP KMS key for secret encryption, then logs in
# and initializes the stack. Idempotent — safe to re-run. Run once per project, before `pulumi up`.
#
# Requires: gcloud auth (ADC), roles to create buckets + KMS keys in the project.
set -euo pipefail

PROJECT="${GOOGLE_PROJECT:-collateralai-501708}"
REGION="${GOOGLE_REGION:-us-central1}"
STACK="${1:-prod}"
BUCKET="gs://${PROJECT}-pulumi-state"
KEYRING="pulumi"
KEY="stack"
KMS_URL="gcpkms://projects/${PROJECT}/locations/${REGION}/keyRings/${KEYRING}/cryptoKeys/${KEY}"

echo "Project: $PROJECT  Region: $REGION  Stack: $STACK"

# 1. State bucket (versioned for history/recovery)
if ! gsutil ls -b "$BUCKET" >/dev/null 2>&1; then
  gsutil mb -p "$PROJECT" -l "$REGION" -b on "$BUCKET"
  gsutil versioning set on "$BUCKET"
  echo "Created state bucket $BUCKET"
else
  echo "State bucket $BUCKET already exists"
fi

# 2. KMS keyring + key for Pulumi secret encryption
gcloud kms keyrings create "$KEYRING" --location "$REGION" --project "$PROJECT" 2>/dev/null \
  && echo "Created KMS keyring $KEYRING" || echo "KMS keyring $KEYRING exists"
gcloud kms keys create "$KEY" --keyring "$KEYRING" --location "$REGION" --project "$PROJECT" \
  --purpose encryption 2>/dev/null \
  && echo "Created KMS key $KEY" || echo "KMS key $KEY exists"

# 3. Point Pulumi at the bucket backend and init the stack
pulumi login "$BUCKET"
if ! pulumi stack select "$STACK" 2>/dev/null; then
  pulumi stack init "$STACK" --secrets-provider="$KMS_URL"
  echo "Initialized stack '$STACK' with KMS secrets provider"
fi

cat <<EOF

State backend ready.
  state:   $BUCKET   (versioned)
  secrets: $KMS_URL

After the first 'pulumi up' creates the CI service account, grant it state access:
  gcloud storage buckets add-iam-policy-binding $BUCKET \\
    --member="serviceAccount:github-cicd-sa@${PROJECT}.iam.gserviceaccount.com" \\
    --role="roles/storage.objectAdmin"
  gcloud kms keys add-iam-policy-binding $KEY --keyring $KEYRING --location $REGION --project $PROJECT \\
    --member="serviceAccount:github-cicd-sa@${PROJECT}.iam.gserviceaccount.com" \\
    --role="roles/cloudkms.cryptoKeyEncrypterDecrypter"
EOF
