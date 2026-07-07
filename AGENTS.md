# Collateral AI — agent guide

Monorepo: `frontend/` (Next.js, SEO-first), `backend/` (Django + DRF), `deploy/` (Pulumi → GCP).

## Conventions
- **Backend**: cookiecutter layout. Apps live in `collateral_ai/`. Split settings in
  `config/settings/{base,local,production,test}.py`. DRF + drf-spectacular; API under `/api/v1/`.
  Payments via `dj-stripe`; email via Resend (`django-anymail[resend]`), console backend locally.
  Lint/format with ruff; types with mypy; tests with `pytest -n auto --reuse-db`.
- **Frontend**: App Router. SEO is non-negotiable — Metadata API, `app/sitemap.ts`, `app/robots.ts`,
  JSON-LD. Typed API client generated from the backend OpenAPI schema (`pnpm gen:api`); TanStack
  Query for client data; Zustand only where genuinely needed. Never expose the Stripe secret key.
- **Infra**: Pulumi (Python) owns GCP resources; GitHub Actions owns deploys. DB is private (VPC
  connector). Secrets live in Secret Manager — never commit real secrets.

## Common commands
- `just up` / `just down` — local stack
- `just manage <cmd>` — Django manage.py
- `just gen-api` — regenerate frontend API types after backend changes
- `just test` — backend tests
- `/scaffold-app <name>` — add a Django app
- `/infra-up` — pulumi preview/up
- `/deploy <frontend|backend|both>` — deploy via GitHub Actions

## When changing the backend API
Regenerate the frontend types (`just gen-api`) so the typed client stays in sync.
