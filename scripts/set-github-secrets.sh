#!/usr/bin/env bash
# Populate the GitHub Actions secrets this repo's cd.yml/jobs.yml need, from Pulumi stack outputs.
# Run AFTER `pulumi up` (so outputs exist) and `gh auth login`. Idempotent.
#
# Usage: bash scripts/set-github-secrets.sh <owner/repo> [stack]
set -euo pipefail

REPO="${1:?usage: set-github-secrets.sh <owner/repo> [stack]}"
STACK="${2:-prod}"
cd "$(dirname "$0")/../deploy"

out() { pulumi stack output "$1" --stack "$STACK" 2>/dev/null; }

PROJECT_ID="$(out project_id)"
WIF_PROVIDER="$(out wif_provider || true)"
SQL_CONN="$(out db_instance_connection_name)"
BUCKET="$(out static_media_bucket_name)"
FRONTEND_BUCKET="$(out frontend_bucket || true)"

if [ -z "${WIF_PROVIDER:-}" ]; then
  echo "ERROR: wif_provider output is empty — set GITHUB_REPO in deploy/.env and re-run 'pulumi up'." >&2
  exit 1
fi

set_secret() { echo -n "$2" | gh secret set "$1" --repo "$REPO"; echo "  set $1"; }

echo "Setting GitHub Actions secrets on $REPO from stack '$STACK':"
set_secret GCP_PROJECT_ID              "$PROJECT_ID"
set_secret GCP_WIF_PROVIDER            "$WIF_PROVIDER"
set_secret CLOUD_SQL_CONNECTION_NAME   "$SQL_CONN"
set_secret DJANGO_GCP_STORAGE_BUCKET_NAME "$BUCKET"
[ -n "${FRONTEND_BUCKET:-}" ] && set_secret FRONTEND_BUCKET "$FRONTEND_BUCKET"

# These are app-specific — prompt/edit as needed (defaults shown).
set_secret DJANGO_ALLOWED_HOSTS        "${DJANGO_ALLOWED_HOSTS:-.run.app,collateralai.example.com}"
set_secret DJANGO_ADMIN_URL            "${DJANGO_ADMIN_URL:-admin/}"
# Frontend build-time (point at the backend Cloud Run URL after its first deploy):
set_secret FRONTEND_API_URL   "${FRONTEND_API_URL:-https://REPLACE-backend.run.app}"   # backend Cloud Run URL
set_secret FRONTEND_SITE_URL  "${FRONTEND_SITE_URL:-https://collateralai.example.com}"

echo "Done. Verify with: gh secret list --repo $REPO"
echo "Note: FRONTEND_API_URL should be updated to the real backend *.run.app URL after the first deploy."
