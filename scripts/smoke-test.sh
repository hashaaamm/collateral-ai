#!/usr/bin/env bash
# Local smoke test for Collateral AI — verifies the running stack before deploy.
# Usage: bash scripts/smoke-test.sh
# Env overrides: FRONTEND_URL, BACKEND_URL, SCHEMA_PATH (default /api/schema/)
set -uo pipefail

FRONTEND_URL="${FRONTEND_URL:-http://localhost:3000}"
BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"
SCHEMA_PATH="${SCHEMA_PATH:-/api/schema/}"   # FastAPI: set to /openapi.json
HEALTH_PATH="${HEALTH_PATH:-/health/}"

GREEN='\033[0;32m'; RED='\033[0;31m'; NC='\033[0m'
fail=0
pass() { printf "  ${GREEN}✅ %s${NC}\n" "$1"; }
err()  { printf "  ${RED}❌ %s${NC}\n" "$1"; fail=$((fail+1)); }

# Wait for a URL to return any of the accepted codes, retrying with backoff.
wait_for() {
  local url="$1" accept="$2" name="$3" tries=30
  for ((i=1; i<=tries; i++)); do
    code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "$url" 2>/dev/null || echo 000)
    if [[ " $accept " == *" $code "* ]]; then pass "$name ($code) $url"; return 0; fi
    sleep 2
  done
  err "$name — last status $code at $url (waited ~60s)"
  return 1
}

echo "── Waiting for stack ─────────────────────────────────────"
wait_for "$BACKEND_URL$HEALTH_PATH"  "200"     "backend health"
wait_for "$BACKEND_URL$SCHEMA_PATH"  "200"     "openapi schema"
wait_for "$FRONTEND_URL/"            "200 304" "frontend root"

echo "── Content checks ────────────────────────────────────────"
# Frontend returns HTML
if curl -s --max-time 5 "$FRONTEND_URL/" | grep -qi "<html"; then pass "frontend serves HTML";
else err "frontend did not return HTML"; fi

# OpenAPI schema is parseable-ish (has a paths/openapi key)
if curl -s --max-time 5 "$BACKEND_URL$SCHEMA_PATH" | grep -qiE 'openapi|paths'; then pass "schema looks valid";
else err "schema content unexpected"; fi

# SEO files (Next.js). Non-fatal if absent (React SPA).
for path in /sitemap.xml /robots.txt; do
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "$FRONTEND_URL$path")
  [[ "$code" == "200" ]] && pass "SEO $path (200)" || printf "  (skip) %s -> %s\n" "$path" "$code"
done

echo "──────────────────────────────────────────────────────────"
if [[ "$fail" -gt 0 ]]; then
  printf "${RED}Smoke test FAILED: %d check(s). Do NOT deploy.${NC}\n" "$fail"
  echo "Tip: 'just logs django' / 'just logs frontend' to diagnose."
  exit 1
fi
printf "${GREEN}Smoke test passed — stack is healthy locally.${NC}\n"
echo "Open: $FRONTEND_URL  ·  API docs: $BACKEND_URL/api/docs/ (Django) or /docs (FastAPI)"
exit 0
