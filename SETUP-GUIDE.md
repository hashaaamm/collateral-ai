# Collateral AI — setup runbook

Step-by-step for the parts Pulumi can't (or shouldn't) do. Each step is tagged **[run]** (a command
Claude Code or you can run) or **[manual]** (console / external, must be a human). Do them in order.
Fill in the values from the plugin's memory / your project.

Example values used below (replace with yours):
`APP_PROJECT=claude-code-plugin-501015`, `DNS_PROJECT=shared-infra-project-501613`,
`DOMAIN=tinyfleet.dev`, `FRONTEND_HOST=app.tinyfleet.dev`, `REGION=us-central1`.

## 1. GCP projects & billing

- **[manual]** Create the app + shared-infra projects (Console → New Project) and **link a billing
  account** to each. (Project creation needs org/billing perms Claude usually won't have.)
- **[run]** Set the active project + ADC quota project:
  ```bash
  gcloud config set project APP_PROJECT
  gcloud auth application-default set-quota-project APP_PROJECT
  ```
- **[run]** Verify billing is on:
  ```bash
  gcloud beta billing projects describe APP_PROJECT --format='value(billingEnabled)'
  ```

## 2. Auth

- **[manual/run]** Log in (browser flow — you approve it):
  ```bash
  gcloud auth login            # CLI, as the account that OWNS the projects
  gcloud auth application-default login   # ADC for Pulumi
  ```

## 3. DNS zone + domain delegation (shared-infra project)

- **[run]** Enable DNS API + create the managed zone in the shared project:
  ```bash
  gcloud services enable dns.googleapis.com --project DNS_PROJECT
  gcloud dns managed-zones create tinyfleet-dev \
    --project DNS_PROJECT --dns-name "DOMAIN." \
    --description "Public zone for DOMAIN"
  ```
  Use the zone name (`tinyfleet-dev`) as `DNS_ZONE` in `deploy/.env`.
- **[run]** Get the zone's nameservers:
  ```bash
  gcloud dns managed-zones describe tinyfleet-dev --project DNS_PROJECT --format='value(nameServers)'
  ```
- **[manual]** At your **domain registrar** (or Cloud Domains) for `DOMAIN`, set the nameservers to
  the 4 values above. DNS delegation can take up to a few hours to propagate. (If the domain was
  bought via Google Cloud Domains, you can point it at the zone in the Console.)

## 4. State backend + provision

- **[run]** Enable KMS (for the Pulumi state key) and bootstrap state:
  ```bash
  gcloud services enable cloudkms.googleapis.com --project APP_PROJECT
  bash deploy/bootstrap-state.sh prod
  ```
- **[run]** Fill `deploy/.env` (from `env-template`): `GOOGLE_PROJECT=APP_PROJECT`, `GITHUB_REPO`,
  and for the custom-domain frontend: `FRONTEND_HOSTING=gcs`, `DOMAIN`, `FRONTEND_SUBDOMAIN=app`,
  `DNS_PROJECT`, `DNS_ZONE`. **Confirm sizing/cost**, then:
  ```bash
  bash deploy/teardown.sh --help >/dev/null 2>&1 || true   # (teardown available for later)
  cd deploy && pulumi preview && pulumi up      # review the plan + cost, then apply
  ```
- **[manual]** The Google-managed SSL cert for `FRONTEND_HOST` goes ACTIVE only once DNS resolves to
  the LB IP — after step 3 propagates. Check: `gcloud compute ssl-certificates describe demo-app-frontend-cert --global`.

## 5. Real secret values

- **[run]** Pulumi seeds `REPLACE_ME` placeholders; set the real values:
  ```bash
  echo -n 'RESEND_KEY'  | gcloud secrets versions add resend-api-key       --data-file=- --project APP_PROJECT
  echo -n 'sk_live_...' | gcloud secrets versions add stripe-secret-key    --data-file=- --project APP_PROJECT
  echo -n 'whsec_...'   | gcloud secrets versions add stripe-webhook-secret --data-file=- --project APP_PROJECT
  ```
- **[manual]** Get those from the Stripe and Resend dashboards (and verify the Resend sending domain).

## 6. GitHub repo + CI secrets

- **[run]** Create the repo and push (if not already):
  ```bash
  gh repo create OWNER/REPO --private --source=. --push
  ```
- **[run]** WIF is provisioned by Pulumi (needs `GITHUB_REPO` set before `pulumi up`). Populate the
  Actions secrets from stack outputs:
  ```bash
  bash scripts/set-github-secrets.sh OWNER/REPO
  ```

## 7. Deploy

- **Backend / Next.js** → push to `main`; GitHub Actions builds + deploys to Cloud Run.
- **React SPA (GCS+CDN)** → the frontend is static, so its deploy step SYNCS the build to the bucket
  and invalidates the CDN (not a Cloud Run deploy):
  ```bash
  cd frontend && pnpm install && VITE_API_URL=<backend-run-url> pnpm build
  gcloud storage rsync ./dist gs://APP_PROJECT-demo-app-frontend --recursive --delete-unmatched-destination-objects
  gcloud compute url-maps invalidate-cdn-cache demo-app-frontend-urlmap --path '/*' --global
  ```
  Then open `https://FRONTEND_HOST`.
