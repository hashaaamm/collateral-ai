# Companies Feature Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Companies feature — a `companies` Django app (Company model + list/create/retrieve API + a signed-URL logo-upload endpoint) and three handoff-styled frontend pages (list, detail, create), with logos uploaded directly to GCS via V4 signed URLs.

**Architecture:** Backend adds a `companies` app with a `Company` model, a `companies/gcs.py` module isolating all GCS V4 signing (keyless via IAM SignBlob on Cloud Run), a `CompanySerializer` (logo write-only object path; `logo_url` read-only signed GET), and a `CompanyViewSet` (list/create/retrieve + a `logo-upload-url` action). Frontend regenerates OpenAPI types, adds TanStack Query hooks + a pure upload helper, and three pages under the guarded app-shell. One Pulumi change grants the runtime SA self-`tokenCreator` and widens bucket CORS origins.

**Tech Stack:** Django + DRF + drf-spectacular, `django-storages[google]` (bundles `google-cloud-storage` + `google-auth`), pytest + factory_boy; React 19 + Vite, TanStack Router/Query, openapi-fetch, zod, react-hook-form; Pulumi (GCP).

## Global Constraints

- **All infra changes go through Pulumi** (`deploy/__main__.py`), applied with `infra-up`. Never mutate infra via `gcloud`/console. Reading state for verification is fine.
- **Images never upload to the backend body** — the browser PUTs directly to GCS via a signed URL.
- GCS object path for logos: `media/companies/logos/<uuid4>/<sanitized-filename>`.
- Logo-upload content-type allowlist: `image/png`, `image/jpeg`, `image/webp`, `image/svg+xml`.
- Signed PUT URL expiry ~15 min; signed GET URL expiry ~1 h.
- APIs require auth (DRF default `IsAuthenticated`; frontend already sends `Authorization: Token <token>`).
- Backend commands run in the backend container/venv (`docker compose run --rm django ...` or `just manage ...`); frontend commands run from `frontend/` with `pnpm`.
- Frontend TypeScript strict (`noUnusedLocals`/`noUnusedParameters`); no raw hex in JSX — use design tokens (`bg-brand`, `text-ink`, `border-hairline`, `bg-surface`, `text-subtext`, `text-body`, `border-field`, `bg-subtle`, `text-mute`, `text-faint`, `bg-brand-soft`, `text-brand`, `bg-page`, `text-destructive`) or arbitrary values for one-off pixels. `pnpm lint` has ONE pre-existing warning in `frontend/src/components/ui/button.tsx` — not a finding; leave button.tsx alone.
- Model is lean: `id, name, website, industry, description, brand_colors (JSON hex list), logo (object path), created_at`. Shared workspace (no per-user scoping). List/detail read-only; no edit/delete.
- Branch `feat/companies`; commit per task, no push.

---

### Task 1: Infrastructure — runtime SA signing + bucket CORS (Pulumi)

**Files:**
- Modify: `deploy/__main__.py`

**Interfaces:**
- Consumes: existing `run_sa` (`gcp.serviceaccount.Account`, `account_id="cloud-run-sa"`), `SLUG`, and the `bucket` CORS default.
- Produces: nothing code-level; enables keyless V4 signing in prod and browser PUT from the real origin. The apply (`infra-up`) is performed by the controller before prod verification.

- [ ] **Step 1: Grant the runtime SA `serviceAccountTokenCreator` on itself**

In `deploy/__main__.py`, immediately after the `for role in [...]: gcp.projects.IAMMember(... run ...)` loop that grants `run_sa` its project roles, add:

```python
# Let the Cloud Run runtime SA sign blobs AS ITSELF (keyless V4 signed URLs via the
# IAM SignBlob API) — required for GCS logo upload/display signed URLs.
gcp.serviceaccount.IAMMember(
    f"{SLUG}-run-sa-token-creator",
    service_account_id=run_sa.name,
    role="roles/iam.serviceAccountTokenCreator",
    member=run_sa.email.apply(lambda e: f"serviceAccount:{e}"),
)
```

- [ ] **Step 2: Include the real frontend origin in bucket CORS**

In `deploy/__main__.py`, change the media bucket's CORS origins default so a browser on the production frontend can PUT to GCS. Replace:

```python
        origins=os.environ.get("BUCKET_CORS_ALLOWED_ORIGINS", "http://localhost:3000,https://collateralai.example.com").split(","),
```
with:
```python
        origins=os.environ.get("BUCKET_CORS_ALLOWED_ORIGINS", "http://localhost:3000,https://collateralai.tinyfleet.dev").split(","),
```

- [ ] **Step 3: Validate the Pulumi program**

Run from `deploy/`: `python -c "import ast, pathlib; ast.parse(pathlib.Path('__main__.py').read_text())"`
Expected: no output (valid Python). If Pulumi + GCP creds are available in this environment, also run `pulumi preview` and confirm the plan shows exactly one new `IAMMember` (token creator) and one bucket update (CORS); otherwise note that `infra-up` apply is deferred to the controller.

- [ ] **Step 4: Commit**

```bash
git add deploy/__main__.py
git commit -m "Infra: runtime SA self-tokenCreator + prod origin in bucket CORS"
```

---

### Task 2: `companies` app — Company model, migration, admin, registration

**Files:**
- Create: `backend/collateral_ai/companies/__init__.py`
- Create: `backend/collateral_ai/companies/apps.py`
- Create: `backend/collateral_ai/companies/models.py`
- Create: `backend/collateral_ai/companies/admin.py`
- Create: `backend/collateral_ai/companies/migrations/__init__.py`
- Create: `backend/collateral_ai/companies/tests/__init__.py`
- Create: `backend/collateral_ai/companies/tests/factories.py`
- Create: `backend/collateral_ai/companies/tests/test_models.py`
- Modify: `backend/config/settings/base.py` (add to `LOCAL_APPS`)

**Interfaces:**
- Produces: `collateral_ai.companies.models.Company` with fields `name, website, industry, description, brand_colors (list), logo (str), created_at`; `CompanyFactory` in tests.

- [ ] **Step 1: Register the app** — in `backend/config/settings/base.py`, change:

```python
LOCAL_APPS = [
    "collateral_ai.users",
    # Your stuff: custom apps go here
]
```
to:
```python
LOCAL_APPS = [
    "collateral_ai.users",
    "collateral_ai.companies",
    # Your stuff: custom apps go here
]
```

- [ ] **Step 2: App package + config**

`backend/collateral_ai/companies/__init__.py`: empty file.
`backend/collateral_ai/companies/migrations/__init__.py`: empty file.
`backend/collateral_ai/companies/tests/__init__.py`: empty file.

`backend/collateral_ai/companies/apps.py`:
```python
from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class CompaniesConfig(AppConfig):
    name = "collateral_ai.companies"
    verbose_name = _("Companies")
```

- [ ] **Step 3: Write the failing model test — `backend/collateral_ai/companies/tests/test_models.py`**

```python
from __future__ import annotations

import pytest

from collateral_ai.companies.models import Company
from collateral_ai.companies.tests.factories import CompanyFactory

pytestmark = pytest.mark.django_db


def test_company_str_is_name():
    company = CompanyFactory(name="Acme AI")
    assert str(company) == "Acme AI"


def test_brand_colors_defaults_to_empty_list():
    company = Company.objects.create(name="NoColors")
    assert company.brand_colors == []


def test_ordering_is_newest_first():
    first = CompanyFactory(name="First")
    second = CompanyFactory(name="Second")
    assert list(Company.objects.all()) == [second, first]


def test_logo_defaults_blank():
    company = CompanyFactory()
    assert company.logo == ""
```

- [ ] **Step 4: Write the factory — `backend/collateral_ai/companies/tests/factories.py`**

```python
from __future__ import annotations

from factory import Faker
from factory.django import DjangoModelFactory

from collateral_ai.companies.models import Company


class CompanyFactory(DjangoModelFactory[Company]):
    name = Faker("company")
    website = Faker("url")
    industry = Faker("bs")
    description = Faker("catch_phrase")

    class Meta:
        model = Company
```

- [ ] **Step 5: Run the test to verify it fails**

Run: `docker compose -f docker-compose.local.yml run --rm django pytest collateral_ai/companies/tests/test_models.py -q`
Expected: FAIL — `ModuleNotFoundError: collateral_ai.companies.models` (model not created yet).

- [ ] **Step 6: Implement the model — `backend/collateral_ai/companies/models.py`**

```python
from django.db import models
from django.utils.translation import gettext_lazy as _


class Company(models.Model):
    """A company profile — reusable context shared across the workspace."""

    name = models.CharField(_("name"), max_length=255)
    website = models.URLField(_("website"), blank=True)
    industry = models.CharField(_("industry"), max_length=120, blank=True)
    description = models.TextField(_("description"), blank=True)
    brand_colors = models.JSONField(_("brand colors"), default=list, blank=True)
    logo = models.CharField(_("logo object path"), max_length=512, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("company")
        verbose_name_plural = _("companies")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.name
```

- [ ] **Step 7: Admin — `backend/collateral_ai/companies/admin.py`**

```python
from django.contrib import admin

from .models import Company


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ["name", "industry", "website", "created_at"]
    search_fields = ["name", "industry"]
```

- [ ] **Step 8: Create the migration**

Run: `docker compose -f docker-compose.local.yml run --rm django python manage.py makemigrations companies`
Expected: creates `backend/collateral_ai/companies/migrations/0001_initial.py`.

- [ ] **Step 9: Run the tests + migrate check**

Run: `docker compose -f docker-compose.local.yml run --rm django pytest collateral_ai/companies/tests/test_models.py -q`
Expected: PASS (4 tests). Also run `docker compose -f docker-compose.local.yml run --rm django python manage.py makemigrations --check --dry-run` → no pending changes.

- [ ] **Step 10: Commit**

```bash
git add backend/collateral_ai/companies backend/config/settings/base.py
git commit -m "Add companies app with Company model and migration"
```

---

### Task 3: GCS signing module — `companies/gcs.py` (TDD)

**Files:**
- Create: `backend/collateral_ai/companies/gcs.py`
- Create: `backend/collateral_ai/companies/tests/test_gcs.py`

**Interfaces:**
- Consumes: `settings.GS_BUCKET_NAME` (defined only in production settings).
- Produces:
  - `is_configured() -> bool`
  - `build_logo_object_path(filename: str) -> str` → `media/companies/logos/<uuid4>/<sanitized>`
  - `signed_upload_url(object_path: str, content_type: str) -> str` (V4 PUT)
  - `signed_get_url(object_path: str) -> str` (V4 GET)

- [ ] **Step 1: Write the failing tests — `backend/collateral_ai/companies/tests/test_gcs.py`**

```python
from __future__ import annotations

from unittest import mock

from collateral_ai.companies import gcs


def test_is_configured_false_without_bucket(settings):
    settings.GS_BUCKET_NAME = ""
    assert gcs.is_configured() is False


def test_is_configured_true_with_bucket(settings):
    settings.GS_BUCKET_NAME = "my-bucket"
    assert gcs.is_configured() is True


def test_build_logo_object_path_sanitizes_and_uuids():
    path = gcs.build_logo_object_path("My Logo (v2).PNG")
    assert path.startswith("media/companies/logos/")
    # <prefix>/<uuid>/<sanitized-filename>
    prefix, uuid_seg, filename = path.rsplit("/", 2)
    assert prefix == "media/companies/logos"
    assert len(uuid_seg) >= 32  # a uuid hex/str
    assert filename == "my_logo_v2.png"
    assert " " not in filename and "(" not in filename


def test_signed_upload_url_delegates_to_blob(settings):
    settings.GS_BUCKET_NAME = "my-bucket"
    with mock.patch.object(gcs, "_bucket") as bucket, \
         mock.patch.object(gcs, "_signing_credentials"):
        blob = bucket.return_value.blob.return_value
        blob.generate_signed_url.return_value = "https://signed-put"
        url = gcs.signed_upload_url("media/companies/logos/x/a.png", "image/png")
        assert url == "https://signed-put"
        _, kwargs = blob.generate_signed_url.call_args
        assert kwargs["method"] == "PUT"
        assert kwargs["content_type"] == "image/png"
        assert kwargs["version"] == "v4"


def test_signed_get_url_delegates_to_blob(settings):
    settings.GS_BUCKET_NAME = "my-bucket"
    with mock.patch.object(gcs, "_bucket") as bucket, \
         mock.patch.object(gcs, "_signing_credentials"):
        blob = bucket.return_value.blob.return_value
        blob.generate_signed_url.return_value = "https://signed-get"
        url = gcs.signed_get_url("media/companies/logos/x/a.png")
        assert url == "https://signed-get"
        _, kwargs = blob.generate_signed_url.call_args
        assert kwargs["method"] == "GET"
        assert kwargs["version"] == "v4"
```

- [ ] **Step 2: Run to verify failure**

Run: `docker compose -f docker-compose.local.yml run --rm django pytest collateral_ai/companies/tests/test_gcs.py -q`
Expected: FAIL — `ModuleNotFoundError: collateral_ai.companies.gcs`.

- [ ] **Step 3: Implement — `backend/collateral_ai/companies/gcs.py`**

```python
"""GCS V4 signed URLs for company logos.

Signing is keyless on Cloud Run: default ADC credentials are refreshed and used
with the IAM SignBlob API (requires roles/iam.serviceAccountTokenCreator on the
runtime SA itself). No service-account key file is needed. When GS_BUCKET_NAME is
unset (local dev), the module is "not configured" and callers degrade gracefully.
"""
from __future__ import annotations

import datetime
import re
import uuid
from pathlib import PurePosixPath

import google.auth
from django.conf import settings
from google.auth.transport import requests as ga_requests
from google.cloud import storage

LOGO_PREFIX = "media/companies/logos"
UPLOAD_EXPIRY = datetime.timedelta(minutes=15)
GET_EXPIRY = datetime.timedelta(hours=1)

_SANITIZE_RE = re.compile(r"[^a-z0-9._-]+")


def is_configured() -> bool:
    return bool(getattr(settings, "GS_BUCKET_NAME", ""))


def build_logo_object_path(filename: str) -> str:
    name = PurePosixPath(filename).name.lower()
    name = _SANITIZE_RE.sub("_", name).strip("_") or "logo"
    return f"{LOGO_PREFIX}/{uuid.uuid4().hex}/{name}"


def _signing_credentials():
    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    credentials.refresh(ga_requests.Request())
    return credentials


def _bucket():
    return storage.Client().bucket(settings.GS_BUCKET_NAME)


def signed_upload_url(object_path: str, content_type: str) -> str:
    creds = _signing_credentials()
    blob = _bucket().blob(object_path)
    return blob.generate_signed_url(
        version="v4",
        expiration=UPLOAD_EXPIRY,
        method="PUT",
        content_type=content_type,
        service_account_email=creds.service_account_email,
        access_token=creds.token,
    )


def signed_get_url(object_path: str) -> str:
    creds = _signing_credentials()
    blob = _bucket().blob(object_path)
    return blob.generate_signed_url(
        version="v4",
        expiration=GET_EXPIRY,
        method="GET",
        service_account_email=creds.service_account_email,
        access_token=creds.token,
    )
```

Note: the tests patch both `gcs._bucket` and `gcs._signing_credentials`, so `google.auth`/`storage` are never called — the tests are hermetic and need no GCP credentials.

- [ ] **Step 4: Run to verify pass**

Run: `docker compose -f docker-compose.local.yml run --rm django pytest collateral_ai/companies/tests/test_gcs.py -q`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/collateral_ai/companies/gcs.py backend/collateral_ai/companies/tests/test_gcs.py
git commit -m "Add GCS V4 signing module for company logos"
```

---

### Task 4: API — serializer, viewset, upload-url action, router, tests, schema regen

**Files:**
- Create: `backend/collateral_ai/companies/api/__init__.py`
- Create: `backend/collateral_ai/companies/api/serializers.py`
- Create: `backend/collateral_ai/companies/api/views.py`
- Create: `backend/collateral_ai/companies/tests/api/__init__.py`
- Create: `backend/collateral_ai/companies/tests/api/test_views.py`
- Modify: `backend/config/api_router.py`
- Modify: `frontend/src/lib/api/schema.d.ts` (regenerated)

**Interfaces:**
- Consumes: `Company`, `CompanyFactory`, `companies.gcs`.
- Produces: routes `GET/POST /api/companies/`, `GET /api/companies/{id}/`, `POST /api/companies/logo-upload-url/`. Serializer read fields `id, name, website, industry, description, brand_colors, logo_url, created_at`; write fields include `logo`.

- [ ] **Step 1: Serializer — `backend/collateral_ai/companies/api/serializers.py`**

```python
from rest_framework import serializers

from collateral_ai.companies import gcs
from collateral_ai.companies.models import Company


class CompanySerializer(serializers.ModelSerializer[Company]):
    logo_url = serializers.SerializerMethodField()
    # Declared explicitly so the OpenAPI schema types brand_colors as string[]
    # (a bare JSONField would emit a loose type that breaks the typed frontend).
    brand_colors = serializers.ListField(
        child=serializers.CharField(), required=False,
    )

    class Meta:
        model = Company
        fields = [
            "id",
            "name",
            "website",
            "industry",
            "description",
            "brand_colors",
            "logo",
            "logo_url",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]
        extra_kwargs = {"logo": {"write_only": True, "required": False}}

    def get_logo_url(self, obj: Company) -> str | None:
        if obj.logo and gcs.is_configured():
            return gcs.signed_get_url(obj.logo)
        return None
```

- [ ] **Step 2: Views — `backend/collateral_ai/companies/api/views.py`**

```python
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.mixins import CreateModelMixin
from rest_framework.mixins import ListModelMixin
from rest_framework.mixins import RetrieveModelMixin
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from collateral_ai.companies import gcs
from collateral_ai.companies.models import Company

from .serializers import CompanySerializer

ALLOWED_LOGO_TYPES = {"image/png", "image/jpeg", "image/webp", "image/svg+xml"}


class CompanyViewSet(
    RetrieveModelMixin,
    ListModelMixin,
    CreateModelMixin,
    GenericViewSet,
):
    serializer_class = CompanySerializer
    queryset = Company.objects.all()

    @action(detail=False, methods=["post"], url_path="logo-upload-url")
    def logo_upload_url(self, request):
        if not gcs.is_configured():
            return Response(
                {"detail": "Logo upload is not configured in this environment."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        filename = request.data.get("filename")
        content_type = request.data.get("content_type")
        if not filename or content_type not in ALLOWED_LOGO_TYPES:
            return Response(
                {"detail": "A filename and a supported image content_type are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        object_path = gcs.build_logo_object_path(filename)
        upload_url = gcs.signed_upload_url(object_path, content_type)
        return Response({"upload_url": upload_url, "object_path": object_path})
```

- [ ] **Step 3: Wire the router** — in `backend/config/api_router.py`, add the import and registration next to the users one:

```python
from collateral_ai.companies.api.views import CompanyViewSet
from collateral_ai.users.api.views import UserViewSet

router = DefaultRouter() if settings.DEBUG else SimpleRouter()

router.register("users", UserViewSet)
router.register("companies", CompanyViewSet, basename="company")
```

- [ ] **Step 4: Write the API tests — `backend/collateral_ai/companies/tests/api/test_views.py`**

```python
from __future__ import annotations

from http import HTTPStatus
from unittest import mock

import pytest
from rest_framework.test import APIClient

from collateral_ai.companies.models import Company
from collateral_ai.companies.tests.factories import CompanyFactory
from collateral_ai.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def auth_client() -> APIClient:
    client = APIClient()
    client.force_authenticate(user=UserFactory())
    return client


def test_list_requires_auth():
    assert APIClient().get("/api/companies/").status_code == HTTPStatus.FORBIDDEN


def test_list_returns_companies(auth_client):
    CompanyFactory(name="Acme AI")
    resp = auth_client.get("/api/companies/")
    assert resp.status_code == HTTPStatus.OK
    names = [c["name"] for c in resp.json()]
    assert "Acme AI" in names


def test_create_company(auth_client):
    resp = auth_client.post(
        "/api/companies/",
        {"name": "NewCo", "brand_colors": ["#5b5bd6"]},
        format="json",
    )
    assert resp.status_code == HTTPStatus.CREATED
    assert Company.objects.filter(name="NewCo").exists()
    assert resp.json()["brand_colors"] == ["#5b5bd6"]


def test_retrieve_company(auth_client):
    company = CompanyFactory(name="Acme AI")
    resp = auth_client.get(f"/api/companies/{company.pk}/")
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()["name"] == "Acme AI"


def test_logo_url_is_signed_when_configured(auth_client):
    company = CompanyFactory(logo="media/companies/logos/x/a.png")
    with mock.patch(
        "collateral_ai.companies.api.serializers.gcs.is_configured",
        return_value=True,
    ), mock.patch(
        "collateral_ai.companies.api.serializers.gcs.signed_get_url",
        return_value="https://signed-get",
    ):
        resp = auth_client.get(f"/api/companies/{company.pk}/")
    assert resp.json()["logo_url"] == "https://signed-get"


def test_logo_upload_url_503_when_unconfigured(auth_client):
    with mock.patch(
        "collateral_ai.companies.api.views.gcs.is_configured",
        return_value=False,
    ):
        resp = auth_client.post(
            "/api/companies/logo-upload-url/",
            {"filename": "a.png", "content_type": "image/png"},
            format="json",
        )
    assert resp.status_code == HTTPStatus.SERVICE_UNAVAILABLE


def test_logo_upload_url_rejects_bad_content_type(auth_client):
    with mock.patch(
        "collateral_ai.companies.api.views.gcs.is_configured",
        return_value=True,
    ):
        resp = auth_client.post(
            "/api/companies/logo-upload-url/",
            {"filename": "a.exe", "content_type": "application/x-msdownload"},
            format="json",
        )
    assert resp.status_code == HTTPStatus.BAD_REQUEST


def test_logo_upload_url_returns_signed_put(auth_client):
    with mock.patch(
        "collateral_ai.companies.api.views.gcs.is_configured",
        return_value=True,
    ), mock.patch(
        "collateral_ai.companies.api.views.gcs.build_logo_object_path",
        return_value="media/companies/logos/x/a.png",
    ), mock.patch(
        "collateral_ai.companies.api.views.gcs.signed_upload_url",
        return_value="https://signed-put",
    ):
        resp = auth_client.post(
            "/api/companies/logo-upload-url/",
            {"filename": "a.png", "content_type": "image/png"},
            format="json",
        )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == {
        "upload_url": "https://signed-put",
        "object_path": "media/companies/logos/x/a.png",
    }
```

`backend/collateral_ai/companies/api/__init__.py` and `backend/collateral_ai/companies/tests/api/__init__.py`: empty files.

- [ ] **Step 5: Run the API tests**

Run: `docker compose -f docker-compose.local.yml run --rm django pytest collateral_ai/companies/tests/api/test_views.py -q`
Expected: PASS (8 tests).

- [ ] **Step 6: Regenerate the frontend OpenAPI types (no server needed)**

Run:
```bash
docker compose -f docker-compose.local.yml run --rm django python manage.py spectacular --format openapi-json > /tmp/schema.json
cd frontend && pnpm exec openapi-typescript /tmp/schema.json -o src/lib/api/schema.d.ts
```
Expected: `frontend/src/lib/api/schema.d.ts` now contains `"/api/companies/"`, `"/api/companies/{id}/"`, and `"/api/companies/logo-upload-url/"` paths. Verify: `grep -c "api/companies" frontend/src/lib/api/schema.d.ts` returns ≥ 3. Then `cd frontend && pnpm typecheck` passes.

- [ ] **Step 7: Commit**

```bash
git add backend/collateral_ai/companies/api backend/collateral_ai/companies/tests/api backend/config/api_router.py frontend/src/lib/api/schema.d.ts
git commit -m "Add companies API (CRUD + signed logo-upload-url) and regen OpenAPI types"
```

---

### Task 5: Frontend API hooks + upload helper (TDD helper)

**Files:**
- Create: `frontend/src/lib/api/companies.ts`
- Create: `frontend/src/lib/api/companies.test.ts`

**Interfaces:**
- Consumes: `api` from `@/lib/api/client`, regenerated `schema.d.ts` types.
- Produces:
  - `useCompanies()` — list query (`["companies"]`).
  - `useCompany(id: number)` — detail query (`["companies", id]`).
  - `useCreateCompany()` — create mutation, invalidates `["companies"]`.
  - `requestUploadAndPut(file: File): Promise<string>` — requests a signed URL, PUTs the file to GCS, returns the `object_path`. Throws `Error("upload_not_configured")` on 503, `Error("upload_failed")` on any other failure.
  - `Company` / `CompanyListItem` types derived from the schema.

- [ ] **Step 1: Write the failing test — `frontend/src/lib/api/companies.test.ts`**

```ts
import { afterEach, describe, expect, it, vi } from "vitest";
import { requestUploadAndPut } from "./companies";
import { api } from "./client";

afterEach(() => vi.restoreAllMocks());

function file() {
  return new File(["x"], "logo.png", { type: "image/png" });
}

describe("requestUploadAndPut", () => {
  it("requests a signed URL then PUTs the file and returns the object path", async () => {
    vi.spyOn(api, "POST").mockResolvedValue({
      data: { upload_url: "https://gcs/put", object_path: "media/companies/logos/x/logo.png" },
      error: undefined,
    } as never);
    const put = vi.spyOn(globalThis, "fetch").mockResolvedValue({ ok: true } as Response);

    const path = await requestUploadAndPut(file());

    expect(path).toBe("media/companies/logos/x/logo.png");
    expect(put).toHaveBeenCalledWith(
      "https://gcs/put",
      expect.objectContaining({ method: "PUT", headers: { "Content-Type": "image/png" } }),
    );
  });

  it("throws upload_not_configured on 503", async () => {
    vi.spyOn(api, "POST").mockResolvedValue({
      data: undefined,
      error: { detail: "not configured" },
      response: { status: 503 },
    } as never);
    await expect(requestUploadAndPut(file())).rejects.toThrow("upload_not_configured");
  });

  it("throws upload_failed when the GCS PUT fails", async () => {
    vi.spyOn(api, "POST").mockResolvedValue({
      data: { upload_url: "https://gcs/put", object_path: "p" },
      error: undefined,
    } as never);
    vi.spyOn(globalThis, "fetch").mockResolvedValue({ ok: false, status: 403 } as Response);
    await expect(requestUploadAndPut(file())).rejects.toThrow("upload_failed");
  });
});
```

- [ ] **Step 2: Run to verify failure**

Run (from `frontend/`): `pnpm test src/lib/api/companies.test.ts`
Expected: FAIL — cannot resolve `./companies`.

- [ ] **Step 3: Implement — `frontend/src/lib/api/companies.ts`**

```ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { components } from "./schema";
import { api } from "./client";

export type Company = components["schemas"]["Company"];

export function useCompanies() {
  return useQuery({
    queryKey: ["companies"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/companies/");
      if (error) throw error;
      return data;
    },
  });
}

export function useCompany(id: number) {
  return useQuery({
    queryKey: ["companies", id],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/companies/{id}/", {
        params: { path: { id } },
      });
      if (error) throw error;
      return data;
    },
  });
}

export function useCreateCompany() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: {
      name: string;
      website?: string;
      industry?: string;
      description?: string;
      brand_colors?: string[];
      logo?: string;
    }) => {
      const { data, error } = await api.POST("/api/companies/", { body });
      if (error || !data) throw new Error("create_failed");
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["companies"] }),
  });
}

/**
 * Request a signed upload URL for `file`, PUT the bytes straight to GCS, and
 * return the stored object path. The file never passes through our backend.
 */
export async function requestUploadAndPut(file: File): Promise<string> {
  const { data, error, response } = await api.POST("/api/companies/logo-upload-url/", {
    body: { filename: file.name, content_type: file.type },
  });
  if (error || !data) {
    throw new Error(response?.status === 503 ? "upload_not_configured" : "upload_failed");
  }
  const put = await fetch(data.upload_url, {
    method: "PUT",
    headers: { "Content-Type": file.type },
    body: file,
  });
  if (!put.ok) throw new Error("upload_failed");
  return data.object_path;
}
```

Note: the `logo-upload-url` request body type comes from the regenerated schema; if openapi-typescript typed the body as required-with-extra-fields, mirror the Task-3 login pattern and cast with `as components["schemas"][...]` only if the compiler requires it. Run `pnpm typecheck` and adjust the cast only if there is an error.

- [ ] **Step 4: Run to verify pass + typecheck**

Run (from `frontend/`): `pnpm test src/lib/api/companies.test.ts && pnpm typecheck`
Expected: PASS (3 tests) and no type errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/api/companies.ts frontend/src/lib/api/companies.test.ts
git commit -m "Add companies API hooks and signed-URL upload helper"
```

---

### Task 6: Frontend — Companies list + detail pages + routes

**Files:**
- Create: `frontend/src/routes/companies-list.tsx`
- Create: `frontend/src/routes/company-detail.tsx`
- Create: `frontend/src/components/company-logo.tsx`
- Modify: `frontend/src/router.tsx`

**Interfaces:**
- Consumes: `useCompanies`, `useCompany`, `Company` from `@/lib/api/companies`; `Link`, `useParams` from `@tanstack/react-router`; phosphor icons.
- Produces: `CompaniesListPage`, `CompanyDetailPage` (named exports); a `CompanyLogo` avatar component. Routes `/companies` (replaces the placeholder) and `/companies/$companyId`.

- [ ] **Step 1: Shared logo/initial avatar — `frontend/src/components/company-logo.tsx`**

```tsx
function initial(name: string): string {
  return (name.trim()[0] ?? "?").toUpperCase();
}

export function CompanyLogo({
  name,
  logoUrl,
  size = 32,
}: {
  name: string;
  logoUrl?: string | null;
  size?: number;
}) {
  if (logoUrl) {
    return (
      <img
        src={logoUrl}
        alt={`${name} logo`}
        className="flex-none rounded-lg object-cover"
        style={{ width: size, height: size }}
      />
    );
  }
  return (
    <div
      className="flex flex-none items-center justify-center rounded-lg bg-brand-tint font-bold text-brand"
      style={{ width: size, height: size, fontSize: size * 0.4 }}
    >
      {initial(name)}
    </div>
  );
}
```

- [ ] **Step 2: List page — `frontend/src/routes/companies-list.tsx`**

```tsx
import { Link } from "@tanstack/react-router";
import { Buildings, CaretRight, Plus } from "@phosphor-icons/react";

import { CompanyLogo } from "@/components/company-logo";
import { useCompanies } from "@/lib/api/companies";

export function CompaniesListPage() {
  const { data: companies, isLoading, isError } = useCompanies();

  return (
    <div className="mx-auto max-w-[1080px] px-10 pb-[60px] pt-8">
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="text-[24px] font-bold tracking-[-0.03em] text-ink">Companies</h1>
          <p className="mt-1 text-sm text-subtext">
            Reusable company context shared across every generation.
          </p>
        </div>
        <Link
          to="/companies/new"
          className="flex items-center gap-[7px] rounded-[10px] bg-brand px-[15px] py-[10px] text-[13.5px] font-semibold text-white hover:bg-brand-hover"
        >
          <Plus weight="bold" size={14} />
          Create Company
        </Link>
      </div>

      <div className="overflow-hidden rounded-2xl border border-hairline bg-surface">
        <div className="grid grid-cols-[2fr_1fr_1fr_auto] gap-4 border-b border-hairline bg-subtle px-5 py-3 text-[11px] font-semibold uppercase tracking-wide text-faint">
          <span>Company</span>
          <span>Industry</span>
          <span>Website</span>
          <span className="w-4" />
        </div>

        {isLoading && <div className="px-5 py-8 text-center text-sm text-mute">Loading…</div>}
        {isError && (
          <div className="px-5 py-8 text-center text-sm text-destructive">
            Couldn’t load companies.
          </div>
        )}
        {companies?.length === 0 && (
          <div className="flex flex-col items-center gap-2 px-5 py-12 text-center">
            <Buildings size={28} className="text-faint" />
            <p className="text-sm text-mute">No companies yet.</p>
          </div>
        )}
        {companies?.map((c) => (
          <Link
            key={c.id}
            to="/companies/$companyId"
            params={{ companyId: String(c.id) }}
            className="grid grid-cols-[2fr_1fr_1fr_auto] items-center gap-4 border-b border-hairline px-5 py-[14px] last:border-b-0 hover:bg-subtle"
          >
            <span className="flex items-center gap-3">
              <CompanyLogo name={c.name} logoUrl={c.logo_url} />
              <span className="text-[13.5px] font-semibold text-ink">{c.name}</span>
            </span>
            <span className="text-[13px] text-body">{c.industry || "—"}</span>
            <span className="truncate text-[13px] text-subtext">{c.website || "—"}</span>
            <CaretRight size={14} className="text-faint" />
          </Link>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Detail page — `frontend/src/routes/company-detail.tsx`**

```tsx
import { Link, useParams } from "@tanstack/react-router";
import { CaretRight, Globe } from "@phosphor-icons/react";

import { CompanyLogo } from "@/components/company-logo";
import { useCompany } from "@/lib/api/companies";

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-faint">
        {label}
      </div>
      <div className="text-[13.5px] text-body">{value || "—"}</div>
    </div>
  );
}

export function CompanyDetailPage() {
  const { companyId } = useParams({ from: "/companies/$companyId" });
  const { data: company, isLoading, isError } = useCompany(Number(companyId));

  if (isLoading) {
    return <div className="mx-auto max-w-[1080px] px-10 pt-8 text-sm text-mute">Loading…</div>;
  }
  if (isError || !company) {
    return (
      <div className="mx-auto max-w-[1080px] px-10 pt-8">
        <p className="text-sm text-destructive">Company not found.</p>
        <Link to="/companies" className="mt-2 inline-block text-sm text-brand">
          Back to companies
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-[1080px] px-10 pb-[60px] pt-8">
      <div className="mb-[18px] flex items-center gap-[7px] text-[12.5px] text-mute">
        <Link to="/companies" className="hover:text-brand">
          Companies
        </Link>
        <CaretRight size={11} />
        <span className="font-medium text-body">{company.name}</span>
      </div>

      <div className="mb-6 flex items-center gap-4">
        <CompanyLogo name={company.name} logoUrl={company.logo_url} size={56} />
        <div>
          <h1 className="text-[23px] font-bold tracking-[-0.02em] text-ink">{company.name}</h1>
          <div className="mt-1 flex items-center gap-3">
            {company.industry && (
              <span className="rounded-full bg-brand-soft px-[10px] py-[3px] text-[11.5px] font-semibold text-brand">
                {company.industry}
              </span>
            )}
            {company.website && (
              <a
                href={company.website}
                target="_blank"
                rel="noreferrer"
                className="flex items-center gap-[6px] text-[12.5px] text-subtext hover:text-brand"
              >
                <Globe size={14} />
                {company.website}
              </a>
            )}
          </div>
        </div>
      </div>

      <div className="rounded-2xl border border-hairline bg-surface p-6">
        <div className="grid grid-cols-2 gap-6">
          <Field label="Website" value={company.website ?? ""} />
          <Field label="Industry" value={company.industry ?? ""} />
          <div className="col-span-2">
            <Field label="Description" value={company.description ?? ""} />
          </div>
          <div className="col-span-2">
            <div className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-faint">
              Brand colors
            </div>
            {company.brand_colors && company.brand_colors.length > 0 ? (
              <div className="flex items-center gap-2">
                {company.brand_colors.map((hex, i) => (
                  <span
                    key={`${hex}-${i}`}
                    title={hex}
                    className="size-[34px] rounded-lg border border-hairline"
                    style={{ background: hex }}
                  />
                ))}
              </div>
            ) : (
              <div className="text-[13.5px] text-body">—</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Register routes** — in `frontend/src/router.tsx`, replace the existing `companiesRoute` component wiring and add the detail route. Change the `companiesRoute` definition to use the new page and add a child param route. Replace:

```tsx
import { CompaniesPage } from "@/routes/companies";
```
with:
```tsx
import { CompaniesListPage } from "@/routes/companies-list";
import { CompanyDetailPage } from "@/routes/company-detail";
```
Change the `companiesRoute` component from `CompaniesPage` to `CompaniesListPage`, and add (after it):
```tsx
const companyDetailRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/companies/$companyId",
  component: CompanyDetailPage,
});
```
Add `companyDetailRoute` to `appRoute.addChildren([...])`. (Delete the now-unused `frontend/src/routes/companies.tsx` placeholder file, since nothing imports it anymore.)

- [ ] **Step 5: Verify**

Run (from `frontend/`): `pnpm typecheck && pnpm lint && pnpm build`
Expected: all pass (no new lint problems beyond the known button.tsx warning).

- [ ] **Step 6: Commit**

```bash
git rm frontend/src/routes/companies.tsx
git add frontend/src/routes/companies-list.tsx frontend/src/routes/company-detail.tsx frontend/src/components/company-logo.tsx frontend/src/router.tsx
git commit -m "Add companies list + detail pages and routes"
```

---

### Task 7: Frontend — New Company page (form + logo upload) + route

**Files:**
- Create: `frontend/src/routes/company-new.tsx`
- Modify: `frontend/src/router.tsx`

**Interfaces:**
- Consumes: `useCreateCompany`, `requestUploadAndPut` from `@/lib/api/companies`; `useNavigate`, `Link` from `@tanstack/react-router`; react-hook-form + zodResolver; phosphor icons; `Button`, `Input`.
- Produces: `NewCompanyPage` (named export); route `/companies/new` registered **before** `/companies/$companyId`.

- [ ] **Step 1: Create page — `frontend/src/routes/company-new.tsx`**

```tsx
import { useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Link, useNavigate } from "@tanstack/react-router";
import { ArrowRight, Buildings, Globe, Plus, UploadSimple, X } from "@phosphor-icons/react";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { requestUploadAndPut, useCreateCompany } from "@/lib/api/companies";

const schema = z.object({
  name: z.string().min(1, "Company name is required"),
  website: z.union([z.string().url("Enter a valid URL"), z.literal("")]).optional(),
  industry: z.string().optional(),
  description: z.string().optional(),
});
type Values = z.infer<typeof schema>;

const MAX_COLORS = 5;

export function NewCompanyPage() {
  const navigate = useNavigate();
  const create = useCreateCompany();
  const fileRef = useRef<HTMLInputElement>(null);

  const [colors, setColors] = useState<string[]>([]);
  const [logoPath, setLogoPath] = useState<string>("");
  const [logoPreview, setLogoPreview] = useState<string>("");
  const [uploadState, setUploadState] = useState<"idle" | "uploading" | "error" | "unavailable">(
    "idle",
  );

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<Values>({ resolver: zodResolver(schema), defaultValues: { name: "" } });

  async function onPickFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadState("uploading");
    setLogoPreview(URL.createObjectURL(file));
    try {
      setLogoPath(await requestUploadAndPut(file));
      setUploadState("idle");
    } catch (err) {
      setLogoPath("");
      setUploadState(err instanceof Error && err.message === "upload_not_configured" ? "unavailable" : "error");
    }
  }

  const onSubmit = handleSubmit((values) => {
    create.mutate(
      {
        name: values.name,
        website: values.website || undefined,
        industry: values.industry || undefined,
        description: values.description || undefined,
        brand_colors: colors,
        logo: logoPath || undefined,
      },
      { onSuccess: (c) => navigate({ to: "/companies/$companyId", params: { companyId: String(c.id) } }) },
    );
  });

  return (
    <div className="mx-auto max-w-[760px] px-10 pb-[60px] pt-[26px]">
      <div className="mb-[18px] flex items-center gap-[7px] text-[12.5px] text-mute">
        <Link to="/companies" className="hover:text-brand">
          Companies
        </Link>
        <span>/</span>
        <span className="font-medium text-body">New company</span>
      </div>
      <h1 className="mb-1 text-[24px] font-bold tracking-[-0.03em] text-ink">Create Company</h1>
      <p className="mb-[26px] text-[13.5px] text-subtext">Add a company profile.</p>

      <form onSubmit={onSubmit}>
        <div className="rounded-2xl border border-hairline bg-surface p-[26px]">
          {/* Logo row */}
          <div className="mb-6 flex items-center gap-4 border-b border-hairline pb-[22px]">
            {logoPreview ? (
              <img src={logoPreview} alt="Logo preview" className="size-[56px] flex-none rounded-[13px] object-cover" />
            ) : (
              <div className="flex size-[56px] flex-none items-center justify-center rounded-[13px] bg-[#f2f2f6] text-faint">
                <Buildings size={24} />
              </div>
            )}
            <div>
              <input ref={fileRef} type="file" accept="image/png,image/jpeg,image/webp,image/svg+xml" hidden onChange={onPickFile} />
              <button
                type="button"
                onClick={() => fileRef.current?.click()}
                disabled={uploadState === "uploading"}
                className="flex items-center gap-[7px] rounded-[9px] border border-field bg-surface px-[13px] py-2 text-[12.5px] font-semibold text-body hover:bg-subtle disabled:opacity-60"
              >
                <UploadSimple size={14} />
                {uploadState === "uploading" ? "Uploading…" : "Upload logo"}
              </button>
              <div className="mt-[6px] text-[11.5px] text-faint">
                {uploadState === "error" && <span className="text-destructive">Upload failed. Try again.</span>}
                {uploadState === "unavailable" && "Logo upload isn’t configured in this environment."}
                {uploadState !== "error" && uploadState !== "unavailable" && "SVG or PNG, at least 128×128"}
              </div>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-[18px_20px]">
            <div>
              <label htmlFor="name" className="mb-2 block text-[12px] font-semibold text-body">
                Company name <span className="text-destructive">*</span>
              </label>
              <Input id="name" placeholder="e.g. Acme AI" className="rounded-[10px] border-field bg-subtle px-3 py-[11px] text-[13.5px]" {...register("name")} />
              {errors.name && <p className="mt-1 text-xs text-destructive">{errors.name.message}</p>}
            </div>
            <div>
              <label htmlFor="website" className="mb-2 block text-[12px] font-semibold text-body">Website</label>
              <div className="flex items-center gap-2 rounded-[10px] border border-field bg-subtle px-3">
                <Globe size={15} className="text-faint" />
                <Input id="website" placeholder="https://acme.ai" className="h-auto border-0 bg-transparent px-0 py-[11px] text-[13.5px] shadow-none focus-visible:ring-0" {...register("website")} />
              </div>
              {errors.website && <p className="mt-1 text-xs text-destructive">{errors.website.message}</p>}
            </div>
            <div>
              <label htmlFor="industry" className="mb-2 block text-[12px] font-semibold text-body">Industry</label>
              <Input id="industry" placeholder="e.g. AI Software" className="rounded-[10px] border-field bg-subtle px-3 py-[11px] text-[13.5px]" {...register("industry")} />
            </div>
            <div>
              <label className="mb-2 block text-[12px] font-semibold text-body">Brand colors</label>
              <div className="flex items-center gap-2">
                {colors.map((hex, i) => (
                  <span key={i} className="relative">
                    <input
                      type="color"
                      value={hex}
                      onChange={(e) => setColors((c) => c.map((x, j) => (j === i ? e.target.value : x)))}
                      className="size-[34px] cursor-pointer rounded-lg border border-hairline"
                    />
                    <button type="button" onClick={() => setColors((c) => c.filter((_, j) => j !== i))} className="absolute -right-1 -top-1 rounded-full bg-surface text-mute" aria-label="Remove color">
                      <X size={12} />
                    </button>
                  </span>
                ))}
                {colors.length < MAX_COLORS && (
                  <button type="button" onClick={() => setColors((c) => [...c, "#5b5bd6"])} className="flex size-[34px] items-center justify-center rounded-lg border border-dashed border-field text-faint hover:bg-subtle" aria-label="Add color">
                    <Plus weight="bold" size={14} />
                  </button>
                )}
              </div>
            </div>
            <div className="col-span-2">
              <label htmlFor="description" className="mb-2 block text-[12px] font-semibold text-body">Description</label>
              <textarea id="description" rows={2} placeholder="One line on what the company does." className="w-full resize-none rounded-[10px] border border-field bg-subtle px-3 py-[11px] text-[13.5px] leading-[1.55] text-ink outline-none" {...register("description")} />
            </div>
          </div>
        </div>

        {create.isError && <p className="mt-3 text-sm text-destructive">Couldn’t create the company. Please try again.</p>}

        <div className="mt-5 flex justify-end gap-[9px]">
          <Link to="/companies" className="rounded-[10px] border border-field bg-surface px-4 py-[10px] text-[13.5px] font-semibold text-body hover:bg-subtle">
            Cancel
          </Link>
          <Button type="submit" disabled={create.isPending || uploadState === "uploading"} className="flex h-auto items-center gap-[7px] rounded-[10px] bg-brand px-[18px] py-[10px] text-[13.5px] font-semibold text-white hover:bg-brand-hover">
            {create.isPending ? "Creating…" : <>Create Company <ArrowRight weight="bold" size={14} /></>}
          </Button>
        </div>
      </form>
    </div>
  );
}
```

- [ ] **Step 2: Register the route (before the param route)** — in `frontend/src/router.tsx`, import and add `companyNewRoute`, ensuring it is listed **before** `companyDetailRoute` in `appRoute.addChildren([...])` so `/companies/new` is not captured by `/companies/$companyId`:

```tsx
import { NewCompanyPage } from "@/routes/company-new";
```
```tsx
const companyNewRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/companies/new",
  component: NewCompanyPage,
});
```
In `appRoute.addChildren([...])`, order the company routes as: `companiesRoute`, `companyNewRoute`, `companyDetailRoute`.

- [ ] **Step 3: Verify**

Run (from `frontend/`): `pnpm typecheck && pnpm lint && pnpm build`
Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/routes/company-new.tsx frontend/src/router.tsx
git commit -m "Add New Company page with signed-URL logo upload"
```

---

## Post-implementation (controller)

After all tasks pass review:
1. **Apply infra via Pulumi:** run `infra-up` (deploy/) to grant the runtime SA self-`tokenCreator` and update bucket CORS. This is required before logo upload works in prod.
2. **Merge `feat/companies` → `main`** and push → CD deploys backend (migrations run) + frontend.
3. **Prod verify:** log in, create a company with a logo (signed PUT to GCS → create), confirm the logo renders on the list and detail via the signed GET URL; create one without a logo; confirm list/detail/guards.

## Notes for the implementer
- Backend tests never hit real GCP — `companies.gcs` functions are mocked at their call sites (`companies.api.views.gcs.*`, `companies.api.serializers.gcs.*`, or `gcs._bucket`/`gcs._signing_credentials`).
- The frontend PUT to GCS uses raw `fetch` (not the openapi-fetch `api` client) because the signed URL is an external GCS endpoint; no auth header is sent (the signature authorizes it).
- Local dev: `logo-upload-url` returns 503 and the create form shows "not configured" — creating companies without a logo works locally and in tests.
