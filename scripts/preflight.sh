#!/usr/bin/env bash
# Preflight prerequisite check for Collateral AI.
# Usage: bash scripts/preflight.sh [--cloud]
#   --cloud  also check gcloud/pulumi/gh (needed for infra + deploy)
set -uo pipefail

CHECK_CLOUD=0
[[ "${1:-}" == "--cloud" ]] && CHECK_CLOUD=1

GREEN='\033[0;32m'; YELLOW='\033[0;33m'; RED='\033[0;31m'; NC='\033[0m'
fail=0; warn=0

ok()   { printf "  ${GREEN}✅ %-16s${NC} %s\n" "$1" "$2"; }
bad()  { printf "  ${RED}❌ %-16s${NC} %s\n" "$1" "$2"; fail=$((fail+1)); }
note() { printf "  ${YELLOW}⚠️  %-16s${NC} %s\n" "$1" "$2"; warn=$((warn+1)); }

have() { command -v "$1" >/dev/null 2>&1; }
ver()  { "$@" 2>&1 | head -n1; }

echo "── Required ──────────────────────────────────────────────"
if have docker; then
  if docker info >/dev/null 2>&1; then ok docker "$(ver docker --version)";
  else bad docker "installed but daemon not running — start Docker Desktop"; fi
else bad docker "not found — install Docker Desktop (https://docker.com)"; fi

if docker compose version >/dev/null 2>&1; then ok "docker compose" "$(ver docker compose version)";
else bad "docker compose" "Compose v2 not found"; fi

have git  && ok git  "$(ver git --version)"   || bad git  "install git"
have just && ok just "$(ver just --version)"   || bad just "install just (brew install just)"

echo "── Frontend (Node) ───────────────────────────────────────"
if have node; then
  major=$(node -p "process.versions.node.split('.')[0]" 2>/dev/null || echo 0)
  if [[ "$major" -ge 20 ]]; then ok node "$(node --version)"; else note node "$(node --version) — want 20+ (24 LTS)"; fi
else note node "not found — required only if scaffolding a frontend"; fi
have pnpm && ok pnpm "$(ver pnpm --version)" || note pnpm "not found — 'npm i -g pnpm' (frontend only)"

echo "── Backend / IaC (Python) ────────────────────────────────"
if have python3; then
  pyok=$(python3 -c 'import sys; print(1 if sys.version_info[:2]>=(3,12) else 0)' 2>/dev/null || echo 0)
  [[ "$pyok" == "1" ]] && ok python3 "$(ver python3 --version)" || note python3 "$(ver python3 --version) — want 3.12+ (FastAPI/Pulumi)"
else note python3 "not found — needed for FastAPI or Pulumi"; fi

if [[ "$CHECK_CLOUD" == "1" ]]; then
  echo "── Cloud (deploy) ────────────────────────────────────────"
  have gcloud && ok gcloud "$(ver gcloud --version)" || bad gcloud "install Google Cloud SDK"
  if have gcloud && gcloud auth application-default print-access-token >/dev/null 2>&1; then
    ok "gcloud auth" "application-default credentials present"
  else bad "gcloud auth" "run: gcloud auth application-default login"; fi
  have pulumi && ok pulumi "$(ver pulumi version)" || bad pulumi "install Pulumi (curl -fsSL https://get.pulumi.com | sh)"
  if have gh && gh auth status >/dev/null 2>&1; then ok gh "authenticated"; else note gh "install/auth gh for /deploy (gh auth login)"; fi
fi

echo "── Ports ─────────────────────────────────────────────────"
for p in 3000 8000 5432 4443; do
  if lsof -i :"$p" >/dev/null 2>&1; then note "port $p" "in use — local stack may conflict"; else ok "port $p" "free"; fi
done

echo "──────────────────────────────────────────────────────────"
if [[ "$fail" -gt 0 ]]; then
  printf "${RED}Preflight FAILED: %d blocking issue(s), %d warning(s).${NC}\n" "$fail" "$warn"; exit 1
fi
printf "${GREEN}Preflight passed${NC} (%d warning(s)).\n" "$warn"; exit 0
