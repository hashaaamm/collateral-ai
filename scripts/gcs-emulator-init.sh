#!/usr/bin/env bash
# Create the local logo bucket (idempotent) and set CORS so the browser (localhost:3001)
# can PUT directly to the emulator. Run after `just up`.
set -euo pipefail
HOST="${1:-http://localhost:4443}"
BUCKET="collateral-ai-local-media"
curl -sf -X POST "$HOST/storage/v1/b" -H "Content-Type: application/json" \
  -d "{\"name\":\"$BUCKET\"}" >/dev/null 2>&1 || true
curl -sf -X PATCH "$HOST/storage/v1/b/$BUCKET" -H "Content-Type: application/json" \
  -d '{"cors":[{"origin":["http://localhost:3001","http://localhost:3000"],"method":["GET","PUT","POST","OPTIONS"],"responseHeader":["Content-Type"],"maxAgeSeconds":3600}]}' >/dev/null
echo "GCS emulator: bucket + CORS ready"
