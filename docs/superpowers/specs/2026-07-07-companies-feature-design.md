# Companies (list / detail / create) + logo upload via signed URLs — Design

Date: 2026-07-07
Status: Approved

## Goal

Add a **Companies** feature: a new `companies` Django app (model + list/create/retrieve
API + a signed-URL endpoint for logo upload) and three handoff-styled frontend pages
(list, detail, create). Logos are uploaded **directly to GCS via a V4 signed PUT URL**
(never through the backend) and served back via short-lived **signed GET URLs**. The
pages match the handoff visual style but show only the fields in the lean model below.

## Constraints (project-wide)

- **All infrastructure changes go through Pulumi** (`deploy/__main__.py`), applied with
  `infra-up`. Never mutate infra directly via `gcloud`/console. (Reading state for
  verification is fine.)
- Images are **never uploaded to the backend body** — the browser PUTs straight to GCS.
- Files are stored in proper folders (see Folder structure).
- Package manager: backend `uv`/pip via the container; frontend `pnpm` from `frontend/`.
- Frontend TypeScript strict; no raw hex in JSX (design tokens / arbitrary values).
- APIs require authentication (DRF default `IsAuthenticated`; the frontend already
  attaches `Authorization: Token <token>`).

## Out of scope

Per the model: documents, generated materials, AI summary, products/services,
target customers, tone of voice, and company **edit/delete**. Detail and list are
read-only. The design's fields not in the model are dropped from the create form.

---

## Data model — `companies.Company`

| Field          | Type                              | Notes                                            |
|----------------|-----------------------------------|--------------------------------------------------|
| `id`           | BigAutoField                      | PK                                               |
| `name`         | `CharField(max_length=255)`       | required                                         |
| `website`      | `URLField(blank=True)`            | optional                                         |
| `industry`     | `CharField(max_length=120, blank=True)` | optional, free text                        |
| `description`  | `TextField(blank=True)`          | optional                                         |
| `brand_colors` | `JSONField(default=list)`        | list of hex strings, e.g. `["#5b5bd6","#0f172a"]`; ≤ 5 |
| `logo`         | `CharField(max_length=512, blank=True)` | GCS object path (not an ImageField — upload bypasses Django) |
| `created_at`   | `DateTimeField(auto_now_add=True)`|                                                 |

- **Shared workspace:** any authenticated user can list/create/retrieve all companies.
  No per-user scoping, no `created_by` (not in the model).
- `Meta.ordering = ["-created_at"]`.
- `__str__` returns `name`.

---

## API (DRF, `IsAuthenticated`)

Registered under `companies` on the existing DRF router (`config/api_router.py`).

### `CompanyViewSet` (`RetrieveModelMixin` + `ListModelMixin` + `CreateModelMixin` + `GenericViewSet`)
- `GET /api/companies/` — list. One `CompanySerializer` used everywhere; read fields:
  `id, name, website, industry, description, brand_colors, logo_url, created_at`.
- `POST /api/companies/` — create. Writable: `name, website, industry, description, brand_colors, logo`. `logo` is the **object path** returned by the upload-URL step (optional).
- `GET /api/companies/{id}/` — retrieve. Same `CompanySerializer` fields as list.
- `@action(detail=False, methods=["post"], url_path="logo-upload-url")`
  `POST /api/companies/logo-upload-url/` — body `{filename, content_type}`.
  - Validates `content_type` against an allowlist: `image/png`, `image/jpeg`,
    `image/webp`, `image/svg+xml`. 400 on anything else.
  - Builds object path `media/companies/logos/<uuid4>/<sanitized-filename>`.
  - Returns `{ upload_url, object_path }` where `upload_url` is a V4 signed **PUT** URL
    (expiry ~15 min) bound to that `content_type`.
  - When GCS/signing is **not configured** (local dev), returns HTTP 503 with
    `{ detail: "Logo upload is not configured in this environment." }`.

### `CompanySerializer`
- `logo` — write-only, the object path (`CharField`, `required=False`, `allow_blank=True`).
- `logo_url` — read-only `SerializerMethodField`: if `logo` is set and GCS is configured,
  returns a V4 signed **GET** URL (expiry ~1 h); otherwise `null`.
- Two serializers or `fields`/`extra_kwargs` to include `description` only on retrieve is
  fine; simplest is one serializer exposing `description` on both (list can include it — cheap).
  **Decision:** one `CompanySerializer` with `description` on both list and detail.

### Signing service — `companies/gcs.py`
A small module isolating all GCS/signing so views/serializers stay clean and testable.
- `is_configured() -> bool` — true when `settings.GS_BUCKET_NAME` is set (prod).
- `signed_upload_url(object_path: str, content_type: str) -> str` — V4 signed PUT.
- `signed_get_url(object_path: str) -> str` — V4 signed GET.
- Signing uses the **IAM SignBlob API** (keyless) on Cloud Run: obtain default
  credentials via `google.auth.default()`, wrap with `google.auth.iam.Signer` (or
  `google.cloud.storage.Blob.generate_signed_url(..., service_account_email=..., access_token=...)`),
  so no SA key file is needed. The signer SA email + access token come from the runtime
  ADC. Local dev has no bucket → `is_configured()` is false and the endpoints degrade
  gracefully (503 for upload-url; `logo_url = null`).

---

## Folder structure (GCS)

`media/companies/logos/<uuid4>/<sanitized-filename>` — the `<uuid4>` segment makes the
path independent of the not-yet-created company id and keeps logos grouped under the
existing `media/` prefix used by django-storages.

## Upload flow (browser → GCS directly)

1. User selects a logo file in the create form.
2. Frontend → `POST /api/companies/logo-upload-url/` `{filename, content_type}` →
   `{upload_url, object_path}`.
3. Frontend `PUT`s the raw file to `upload_url` with header `Content-Type: <content_type>`
   (no auth header — the signature authorizes it). Shows a local preview + upload state.
4. On success the frontend holds `object_path`; on form submit it POSTs
   `/api/companies/` with `logo = object_path` and the other fields.
5. Detail/list render the logo from the serializer's signed `logo_url`.

---

## Infrastructure (Pulumi — `deploy/__main__.py`; apply with `infra-up`)

1. **Runtime SA can sign (keyless V4).** Grant the Cloud Run runtime SA
   `roles/iam.serviceAccountTokenCreator` **on itself** (a
   `gcp.serviceaccount.IAMMember` on `run_sa` with member = `run_sa`), so it can call
   IAM `SignBlob`. The `iamcredentials` API is already enabled.
2. **Bucket CORS origins.** Ensure `BUCKET_CORS_ALLOWED_ORIGINS` includes
   `https://collateralai.tinyfleet.dev` and `http://localhost:3000`. The bucket CORS
   already permits `GET, PUT, POST, DELETE` and the `Content-Type` header. Set this via
   the Pulumi config/env, not by editing the bucket directly.

No other infra changes. These must be applied (`infra-up`) before the logo flow works in
prod; the rest of the feature (companies CRUD without logos) works regardless.

---

## Frontend (React + Vite, TanStack Router/Query, design tokens)

New routes under the guarded app-shell layout (register `/companies/new` **before** the
`:companyId` param route):
- `/companies` — **CompaniesListPage** (replaces the current placeholder).
- `/companies/new` — **NewCompanyPage**.
- `/companies/$companyId` — **CompanyDetailPage**.

### API layer (`src/lib/api/companies.ts`)
Regenerate OpenAPI types (`pnpm gen:api`) after the backend endpoints exist, then:
- `useCompanies()` — list query.
- `useCompany(id)` — detail query.
- `useCreateCompany()` — create mutation (invalidates the list).
- `useLogoUpload()` — helper that (a) requests the signed URL, (b) PUTs the file to GCS,
  returns `{ object_path }`. Pure orchestration split into a testable function
  (`requestUploadAndPut(file)` given the api client) so it can be unit-tested.

### Pages (handoff-styled, tokens only)
- **List** (`max-w-[1080px]`): title "Companies" + subtitle; "Create Company" primary
  button → `/companies/new`. Table card (`border-hairline`, `rounded-2xl`): columns
  **Company** (initial/logo tile + name) · **Industry** · **Website** · **Created**;
  rows link to detail, hover state, trailing caret. Empty state ("No companies yet")
  when the list is empty. Loading skeleton while fetching.
- **Detail** (`max-w-[1080px]`): breadcrumb (Companies / name); header — 56px logo/initial
  tile (renders `logo_url` if present, else an initial), name (`23px/700`), industry pill
  (`bg-brand-soft text-brand`), website link (globe icon). Profile card: Website,
  Industry, Description, **Brand colors** (swatch row from `brand_colors`). Read-only.
  Not-found → friendly message + back link.
- **Create** (`max-w-[760px]`): breadcrumb (Companies / New company); "Create Company"
  title + subtitle. Card: logo row (56px tile preview + "Upload logo" button, hint
  "SVG or PNG, at least 128×128", upload progress/error, gracefully disabled with a hint
  when the upload-url endpoint returns 503 locally); a 2-col field grid — **Company name**
  (required), **Website** (globe icon), **Industry**, **Description** (textarea, full row),
  **Brand colors** (swatch inputs + add button, ≤ 5). Footer: "Cancel" (→ list) +
  "Create Company" primary. On success → navigate to `/companies/$newId`. Uses
  react-hook-form + zod (name required; website valid-URL-or-empty).

Design values are taken from the handoff (`Collate.dc.html` Companies / Company Detail /
New Company screens and the handoff README Design Tokens). Reuse existing tokens; add none
unless a needed color has no token.

---

## Testing

### Backend (pytest, `companies/tests/`)
- Model: creation, `brand_colors` default `[]`, `__str__`, ordering.
- Serializer: `logo_url` is a signed URL when `logo` set + configured (mock
  `companies.gcs.signed_get_url`); `null` when unset or unconfigured; `logo` is write-only.
- ViewSet: 403 unauthenticated; list/create/retrieve happy paths for an authed user;
  create with and without `logo`.
- `logo-upload-url`: 200 with `{upload_url, object_path}` for an allowed content type
  (mock `companies.gcs`); 400 for a disallowed content type; 503 when `is_configured()`
  is false.
- `gcs` module: `is_configured()` toggles on `GS_BUCKET_NAME`; object-path builder
  sanitizes filenames and uses a uuid segment. (Signing calls themselves mocked.)

### Frontend
- Unit-test the pure upload orchestration (`requestUploadAndPut`) with a mocked api
  client + fetch (asserts it requests the URL then PUTs with the right content-type and
  returns `object_path`).
- typecheck / lint / build green.

### Prod verification (after `infra-up` + deploy)
- Create a company with a real logo end-to-end (signed PUT to GCS, then create), and
  confirm the logo renders on list + detail via the signed GET URL.

---

## Sequencing

Larger than one screen; implemented as one cohesive feature, sequenced in the plan:
1. Infra (Pulumi grant + CORS origins).
2. Backend: `companies` app — model + migration, `gcs.py`, serializer, viewset +
   upload-url action, wire router, tests.
3. Frontend: regenerate OpenAPI types, API hooks + upload helper, list/detail/create
   pages, routes.
4. Prod verify (logo upload end-to-end).
