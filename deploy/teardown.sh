#!/usr/bin/env bash
# Robust teardown for Collateral AI infra. Usage: bash deploy/teardown.sh [stack]
#
# Plain `pulumi destroy` reliably gets stuck on GCP's Service Networking connection: after Cloud SQL
# is deleted, GCP keeps the producer connection reserved for a long time (often >20 min), and
# Pulumi keeps retrying the servicenetworking delete API, which keeps failing. The fix that actually
# works: delete Cloud SQL (destroy pass 1), remove the VPC peering from the network side, ORPHAN the
# connection resource from Pulumi state, then destroy everything else. This script does that, and
# clears stale locks left by interrupted runs. Idempotent.
#
# Requires: gcloud auth (CLI + ADC) for the target project, and the Pulumi venv/deps.
set -uo pipefail

STACK="${1:-prod}"
: "${GOOGLE_PROJECT:?set GOOGLE_PROJECT (the target GCP project id)}"
export SQL_DELETION_PROTECTION=false     # allow the DB to be torn down

pulumi cancel --yes --stack "$STACK" 2>/dev/null || true   # clear any stale lock

echo "==> destroy pass 1 (removes Cloud SQL etc.; expected to fail on the SN connection)"
if pulumi destroy --yes --stack "$STACK"; then echo "Teardown complete ✅"; exit 0; fi

# Remove the VPC peering directly (works even when the servicenetworking delete API is stuck).
NET=$(gcloud compute networks list --project "$GOOGLE_PROJECT" \
        --filter="name~'-network'" --format='value(name)' 2>/dev/null | head -1)
if [ -n "$NET" ]; then
  echo "==> removing peering servicenetworking-googleapis-com from $NET"
  gcloud compute networks peerings delete servicenetworking-googleapis-com \
    --network="$NET" --project="$GOOGLE_PROJECT" --quiet 2>/dev/null || true
fi

# Orphan the connection from Pulumi state so destroy stops trying the failing API.
CONN_URN=$(pulumi stack --show-urns --stack "$STACK" 2>/dev/null \
             | grep -o 'urn:[^ ]*servicenetworking[^ ]*Connection[^ ]*' | head -1)
if [ -n "$CONN_URN" ]; then
  echo "==> dropping the Service Networking connection from state: $CONN_URN"
  pulumi state delete "$CONN_URN" --force --yes --stack "$STACK" 2>/dev/null || true
fi

echo "==> destroy pass 2 (connection orphaned; removes connector/network/etc.)"
pulumi cancel --yes --stack "$STACK" 2>/dev/null || true
if pulumi destroy --yes --stack "$STACK"; then echo "Teardown complete ✅"; exit 0; fi

cat <<EOF

Teardown still incomplete. Inspect and finish manually:
  pulumi stack --show-urns --stack $STACK
  gcloud compute networks list --project $GOOGLE_PROJECT
  gcloud compute networks vpc-access connectors list --region <region> --project $GOOGLE_PROJECT
Delete any stragglers (connector, subnet, address, network) with gcloud, then re-run this script.
EOF
exit 1
