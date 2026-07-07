# Document Ingestion — Phase 1 (Upload Surface) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a user upload PDFs to a company and see them listed with a live status, with bytes going straight to GCS — no processing yet (`complete` is a stub that returns 202).

**Architecture:** A new Django `documents` app adds a `Document` model and a DRF `DocumentViewSet` mirroring the existing `companies` app. Upload is a two-call flow: `POST /api/documents/` reserves a `pending` row and returns a signed GCS PUT URL; the browser PUTs the file (with an XHR progress bar); `POST /api/documents/{id}/complete/` flips it to `processing` and (Phase 1) just returns 202. The frontend adds a Documents tab to Company Detail with a dropzone, table, progress bar, and polling.

**Tech Stack:** Django + DRF, drf-spectacular, GCS V4 signed URLs (reused from `companies/gcs.py`), React + Vite, TanStack Query, openapi-fetch/openapi-typescript, Tailwind v4, Phosphor icons.

## Global Constraints

- Backend: Django 6.0.x, DRF `GenericViewSet` + mixins, `IsAuthenticated` is the project default (do not override).
- Mirror the `collateral_ai.companies` app patterns exactly (app layout, serializer/view style, `@extend_schema`, test style with `factory`/`APIClient`).
- MVP accepts **`application/pdf` only**; reject other content types with 400.
- GCS may be unconfigured (CI/unit tests): endpoints that need it return **503** when `gcs.is_configured()` is false (mirror `logo_upload_url`).
- Bytes never pass through the backend — always signed PUT direct to GCS.
- Backend tests run via `just pytest <path>` (docker compose, settings `config.settings.test`). Frontend tests run via `pnpm test` from `frontend/`.
- TDD: write the failing test first. Commit after each green task. DRY. YAGNI.
- Status values live in one place: `collateral_ai.documents.statuses.DocumentStatus`.

## File Structure

**Backend (new app `collateral_ai/documents/`):**
- `__init__.py`, `apps.py` — app scaffold.
- `statuses.py` — `DocumentStatus` constants.
- `models.py` — `Document` model (Phase 1 fields only; `DocumentChunk` is Phase 2).
- `gcs.py` — `build_document_object_path()` + thin re-export of the signed-URL helper.
- `migrations/0001_initial.py` — `Document` table.
- `api/__init__.py`, `api/serializers.py` — `DocumentSerializer`.
- `api/views.py` — `DocumentViewSet` (list, create+upload-url, `complete` stub).
- `tests/__init__.py`, `tests/factories.py`, `tests/test_models.py`, `tests/api/__init__.py`, `tests/api/test_views.py`.

**Backend (modified):**
- `config/settings/base.py` — add app to `LOCAL_APPS`.
- `config/api_router.py` — register `DocumentViewSet`.

**Frontend (new):**
- `src/lib/api/upload.ts` — `putWithProgress()` (XHR upload with progress), isolated for testability.
- `src/lib/api/documents.ts` — `useDocuments`, `uploadDocument`, `useCompleteDocument` + types.
- `src/lib/api/documents.test.ts` — upload orchestration test.
- `src/components/status-pill.tsx` — reusable `StatusPill`.
- `src/components/documents-tab.tsx` — dropzone + table + progress + polling.

**Frontend (modified):**
- `src/lib/api/schema.d.ts` — regenerated (`just gen-api`).
- `src/routes/company-detail.tsx` — add underline tab bar; move current profile into Overview; mount `DocumentsTab`. **Keep additive** (shared with the company-CRUD session).

---

### Task 1: `documents` app + `Document` model

**Files:**
- Create: `backend/collateral_ai/documents/__init__.py` (empty)
- Create: `backend/collateral_ai/documents/apps.py`
- Create: `backend/collateral_ai/documents/statuses.py`
- Create: `backend/collateral_ai/documents/models.py`
- Create: `backend/collateral_ai/documents/tests/__init__.py` (empty)
- Create: `backend/collateral_ai/documents/tests/factories.py`
- Create: `backend/collateral_ai/documents/tests/test_models.py`
- Modify: `backend/config/settings/base.py` (add to `LOCAL_APPS`)
- Create: `backend/collateral_ai/documents/migrations/__init__.py` (empty)
- Create: `backend/collateral_ai/documents/migrations/0001_initial.py` (generated)

**Interfaces:**
- Produces: `DocumentStatus` with `PENDING="pending"`, `PROCESSING="processing"`, `PROCESSED="processed"`, `FAILED="failed"`, and `CHOICES`. `Document` model with fields `company` (FK), `file_name`, `storage_path`, `content_type`, `status`, `page_count`, `chunks_count`, `tables_count`, `images_count`, `error_message`, `created_at`, `updated_at`. `DocumentFactory`.

- [ ] **Step 1: Register the app in settings**

In `backend/config/settings/base.py`, add to `LOCAL_APPS`:

```python
LOCAL_APPS = [
    "collateral_ai.users",
    "collateral_ai.companies",
    "collateral_ai.documents",
    # Your stuff: custom apps go here
]
```

- [ ] **Step 2: Create the app scaffold**

`backend/collateral_ai/documents/apps.py`:

```python
from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class DocumentsConfig(AppConfig):
    name = "collateral_ai.documents"
    verbose_name = _("Documents")
```

`backend/collateral_ai/documents/statuses.py`:

```python
class DocumentStatus:
    PENDING = "pending"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"

    CHOICES = [
        (PENDING, "Pending"),
        (PROCESSING, "Processing"),
        (PROCESSED, "Processed"),
        (FAILED, "Failed"),
    ]
```

Create the empty files `documents/__init__.py`, `documents/tests/__init__.py`, `documents/migrations/__init__.py`.

- [ ] **Step 3: Write the failing model tests**

`backend/collateral_ai/documents/tests/factories.py`:

```python
from __future__ import annotations

from factory import Faker
from factory import SubFactory
from factory.django import DjangoModelFactory

from collateral_ai.companies.tests.factories import CompanyFactory
from collateral_ai.documents.models import Document


class DocumentFactory(DjangoModelFactory[Document]):
    company = SubFactory(CompanyFactory)
    file_name = Faker("file_name", extension="pdf")
    storage_path = "media/companies/1/documents/1/doc.pdf"
    content_type = "application/pdf"

    class Meta:
        model = Document
```

`backend/collateral_ai/documents/tests/test_models.py`:

```python
from __future__ import annotations

import pytest

from collateral_ai.documents.models import Document
from collateral_ai.documents.statuses import DocumentStatus
from collateral_ai.documents.tests.factories import DocumentFactory

pytestmark = pytest.mark.django_db


def test_str_includes_file_name():
    doc = DocumentFactory(file_name="report.pdf")
    assert "report.pdf" in str(doc)


def test_defaults_status_pending_and_zero_counts():
    doc = DocumentFactory()
    assert doc.status == DocumentStatus.PENDING
    assert doc.chunks_count == 0
    assert doc.tables_count == 0
    assert doc.images_count == 0
    assert doc.page_count is None
    assert doc.error_message == ""


def test_ordering_is_newest_first():
    first = DocumentFactory()
    second = DocumentFactory()
    assert list(Document.objects.all()) == [second, first]


def test_company_related_name_documents():
    doc = DocumentFactory()
    assert list(doc.company.documents.all()) == [doc]
```

- [ ] **Step 4: Run the tests to verify they fail**

Run: `just pytest collateral_ai/documents/tests/test_models.py`
Expected: FAIL (collection/import error — `Document` does not exist yet).

- [ ] **Step 5: Implement the `Document` model**

`backend/collateral_ai/documents/models.py`:

```python
from django.db import models
from django.utils.translation import gettext_lazy as _

from collateral_ai.documents.statuses import DocumentStatus


class Document(models.Model):
    """A PDF uploaded to a company's knowledge base."""

    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="documents",
    )
    file_name = models.CharField(_("file name"), max_length=255)
    storage_path = models.CharField(_("storage object path"), max_length=512, blank=True)
    content_type = models.CharField(_("content type"), max_length=100)
    status = models.CharField(
        _("status"),
        max_length=32,
        choices=DocumentStatus.CHOICES,
        default=DocumentStatus.PENDING,
    )
    page_count = models.PositiveIntegerField(null=True, blank=True)
    chunks_count = models.PositiveIntegerField(default=0)
    tables_count = models.PositiveIntegerField(default=0)
    images_count = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("document")
        verbose_name_plural = _("documents")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.file_name} ({self.status})"
```

- [ ] **Step 6: Generate the migration**

Run: `just makemigrations documents`
Expected: creates `collateral_ai/documents/migrations/0001_initial.py`.

- [ ] **Step 7: Run the tests to verify they pass**

Run: `just pytest collateral_ai/documents/tests/test_models.py`
Expected: PASS (4 tests).

- [ ] **Step 8: Commit**

```bash
git add backend/collateral_ai/documents backend/config/settings/base.py
git commit -m "feat(documents): add Document model, statuses, and app scaffold"
```

---

### Task 2: Documents GCS object path helper

**Files:**
- Create: `backend/collateral_ai/documents/gcs.py`
- Create: `backend/collateral_ai/documents/tests/test_gcs.py`

**Interfaces:**
- Consumes: `collateral_ai.companies.gcs` (`is_configured`, `signed_upload_url`, `_SANITIZE_RE`).
- Produces: `build_document_object_path(company_id: int, document_id: int, filename: str) -> str`, and re-exports `is_configured` and `signed_upload_url` so the documents view depends only on `documents.gcs`.

- [ ] **Step 1: Write the failing test**

`backend/collateral_ai/documents/tests/test_gcs.py`:

```python
from __future__ import annotations

from collateral_ai.documents import gcs


def test_object_path_is_scoped_and_sanitized():
    path = gcs.build_document_object_path(7, 42, "Q3 Report!.PDF")
    assert path.startswith("media/companies/7/documents/42/")
    assert path.endswith(".pdf")
    # unsafe characters collapsed, lowercased
    assert " " not in path
    assert "!" not in path


def test_object_path_falls_back_when_stem_empty():
    path = gcs.build_document_object_path(1, 1, "***.pdf")
    assert path == "media/companies/1/documents/1/document.pdf"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `just pytest collateral_ai/documents/tests/test_gcs.py`
Expected: FAIL (`ModuleNotFoundError` / attribute missing).

- [ ] **Step 3: Implement the helper**

`backend/collateral_ai/documents/gcs.py`:

```python
"""GCS object paths for company documents.

Reuses the companies signed-URL machinery (dual prod/emulator signing) so there is
one signing code path in the project. Only the object-path convention is document-specific.
"""
from __future__ import annotations

from pathlib import PurePosixPath

from collateral_ai.companies.gcs import _SANITIZE_RE
from collateral_ai.companies.gcs import is_configured  # noqa: F401  (re-exported)
from collateral_ai.companies.gcs import signed_upload_url  # noqa: F401  (re-exported)

DOCUMENT_PREFIX = "media/companies"


def build_document_object_path(company_id: int, document_id: int, filename: str) -> str:
    path = PurePosixPath(filename)
    stem = _SANITIZE_RE.sub("_", path.stem.lower()).strip("_") or "document"
    suffix = path.suffix.lower() or ".pdf"
    name = stem + suffix
    return f"{DOCUMENT_PREFIX}/{company_id}/documents/{document_id}/{name}"
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `just pytest collateral_ai/documents/tests/test_gcs.py`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/collateral_ai/documents/gcs.py backend/collateral_ai/documents/tests/test_gcs.py
git commit -m "feat(documents): add GCS object-path helper reusing companies signer"
```

---

### Task 3: `DocumentViewSet` — list, create+upload-url, complete stub

**Files:**
- Create: `backend/collateral_ai/documents/api/__init__.py` (empty)
- Create: `backend/collateral_ai/documents/api/serializers.py`
- Create: `backend/collateral_ai/documents/api/views.py`
- Modify: `backend/config/api_router.py`
- Create: `backend/collateral_ai/documents/tests/api/__init__.py` (empty)
- Create: `backend/collateral_ai/documents/tests/api/test_views.py`

**Interfaces:**
- Consumes: `documents.gcs` (`is_configured`, `build_document_object_path`, `signed_upload_url`), `Document`, `DocumentStatus`.
- Produces routes: `GET /api/documents/?company={id}`, `POST /api/documents/`, `GET /api/documents/{id}/`, `POST /api/documents/{id}/complete/`.
  - `POST /api/documents/` request `{company:int, file_name:str, content_type:str}` → **201** `{...Document fields, upload_url:str}`; **400** on non-PDF; **503** when GCS unconfigured.
  - `POST /api/documents/{id}/complete/` → **202** `{...Document fields}` (status becomes `processing`).

- [ ] **Step 1: Write the failing API tests**

`backend/collateral_ai/documents/tests/api/test_views.py`:

```python
from __future__ import annotations

from http import HTTPStatus
from unittest import mock

import pytest
from rest_framework.test import APIClient

from collateral_ai.companies.tests.factories import CompanyFactory
from collateral_ai.documents.models import Document
from collateral_ai.documents.statuses import DocumentStatus
from collateral_ai.documents.tests.factories import DocumentFactory
from collateral_ai.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def auth_client() -> APIClient:
    client = APIClient()
    client.force_authenticate(user=UserFactory())
    return client


def test_list_requires_auth():
    assert APIClient().get("/api/documents/").status_code == HTTPStatus.FORBIDDEN


def test_list_is_scoped_to_company(auth_client):
    a, b = CompanyFactory(), CompanyFactory()
    DocumentFactory(company=a, file_name="a.pdf")
    DocumentFactory(company=b, file_name="b.pdf")
    resp = auth_client.get(f"/api/documents/?company={a.pk}")
    assert resp.status_code == HTTPStatus.OK
    names = [d["file_name"] for d in resp.json()]
    assert names == ["a.pdf"]


def test_create_reserves_pending_doc_and_returns_upload_url(auth_client):
    company = CompanyFactory()
    with mock.patch(
        "collateral_ai.documents.api.views.gcs.is_configured", return_value=True,
    ), mock.patch(
        "collateral_ai.documents.api.views.gcs.signed_upload_url",
        return_value="https://signed-put",
    ):
        resp = auth_client.post(
            "/api/documents/",
            {"company": company.pk, "file_name": "report.pdf", "content_type": "application/pdf"},
            format="json",
        )
    assert resp.status_code == HTTPStatus.CREATED
    body = resp.json()
    assert body["upload_url"] == "https://signed-put"
    assert body["status"] == DocumentStatus.PENDING
    doc = Document.objects.get(pk=body["id"])
    assert doc.company_id == company.pk
    assert doc.storage_path.startswith(f"media/companies/{company.pk}/documents/{doc.pk}/")


def test_create_rejects_non_pdf(auth_client):
    company = CompanyFactory()
    with mock.patch(
        "collateral_ai.documents.api.views.gcs.is_configured", return_value=True,
    ):
        resp = auth_client.post(
            "/api/documents/",
            {"company": company.pk, "file_name": "a.docx", "content_type": "application/msword"},
            format="json",
        )
    assert resp.status_code == HTTPStatus.BAD_REQUEST
    assert not Document.objects.exists()


def test_create_503_when_unconfigured(auth_client):
    company = CompanyFactory()
    with mock.patch(
        "collateral_ai.documents.api.views.gcs.is_configured", return_value=False,
    ):
        resp = auth_client.post(
            "/api/documents/",
            {"company": company.pk, "file_name": "a.pdf", "content_type": "application/pdf"},
            format="json",
        )
    assert resp.status_code == HTTPStatus.SERVICE_UNAVAILABLE


def test_complete_marks_processing_and_returns_202(auth_client):
    doc = DocumentFactory(status=DocumentStatus.PENDING)
    resp = auth_client.post(f"/api/documents/{doc.pk}/complete/")
    assert resp.status_code == HTTPStatus.ACCEPTED
    assert resp.json()["status"] == DocumentStatus.PROCESSING
    doc.refresh_from_db()
    assert doc.status == DocumentStatus.PROCESSING


def test_complete_retries_failed_doc(auth_client):
    doc = DocumentFactory(status=DocumentStatus.FAILED, error_message="boom")
    resp = auth_client.post(f"/api/documents/{doc.pk}/complete/")
    assert resp.status_code == HTTPStatus.ACCEPTED
    doc.refresh_from_db()
    assert doc.status == DocumentStatus.PROCESSING
    assert doc.error_message == ""
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `just pytest collateral_ai/documents/tests/api/test_views.py`
Expected: FAIL (404s / import errors — viewset and routes do not exist).

- [ ] **Step 3: Implement the serializer**

`backend/collateral_ai/documents/api/serializers.py`:

```python
from rest_framework import serializers

from collateral_ai.documents.models import Document


class DocumentSerializer(serializers.ModelSerializer[Document]):
    class Meta:
        model = Document
        fields = [
            "id",
            "company",
            "file_name",
            "content_type",
            "status",
            "page_count",
            "chunks_count",
            "tables_count",
            "images_count",
            "error_message",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "page_count",
            "chunks_count",
            "tables_count",
            "images_count",
            "error_message",
            "created_at",
        ]
```

- [ ] **Step 4: Implement the viewset**

`backend/collateral_ai/documents/api/views.py`:

```python
from drf_spectacular.utils import OpenApiResponse
from drf_spectacular.utils import extend_schema
from drf_spectacular.utils import inline_serializer
from rest_framework import serializers
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.mixins import CreateModelMixin
from rest_framework.mixins import ListModelMixin
from rest_framework.mixins import RetrieveModelMixin
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from collateral_ai.documents import gcs
from collateral_ai.documents.models import Document
from collateral_ai.documents.statuses import DocumentStatus

from .serializers import DocumentSerializer

ALLOWED_DOCUMENT_TYPES = {"application/pdf"}


class DocumentViewSet(
    ListModelMixin,
    RetrieveModelMixin,
    CreateModelMixin,
    GenericViewSet,
):
    serializer_class = DocumentSerializer
    queryset = Document.objects.all()

    def get_queryset(self):
        qs = super().get_queryset()
        company = self.request.query_params.get("company")
        if company:
            qs = qs.filter(company_id=company)
        return qs

    @extend_schema(
        request=inline_serializer(
            name="DocumentCreateRequest",
            fields={
                "company": serializers.IntegerField(),
                "file_name": serializers.CharField(),
                "content_type": serializers.CharField(),
            },
        ),
        responses=inline_serializer(
            name="DocumentCreateResponse",
            fields={
                "id": serializers.IntegerField(),
                "company": serializers.IntegerField(),
                "file_name": serializers.CharField(),
                "content_type": serializers.CharField(),
                "status": serializers.CharField(),
                "page_count": serializers.IntegerField(allow_null=True),
                "chunks_count": serializers.IntegerField(),
                "tables_count": serializers.IntegerField(),
                "images_count": serializers.IntegerField(),
                "error_message": serializers.CharField(),
                "created_at": serializers.DateTimeField(),
                "upload_url": serializers.URLField(),
            },
        ),
    )
    def create(self, request, *args, **kwargs):
        if not gcs.is_configured():
            return Response(
                {"detail": "Document upload is not configured in this environment."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        company = request.data.get("company")
        file_name = request.data.get("file_name")
        content_type = request.data.get("content_type")
        if not company or not file_name or content_type not in ALLOWED_DOCUMENT_TYPES:
            return Response(
                {"detail": "A company, file_name, and application/pdf content_type are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        doc = Document.objects.create(
            company_id=company,
            file_name=file_name,
            content_type=content_type,
            status=DocumentStatus.PENDING,
        )
        object_path = gcs.build_document_object_path(int(company), doc.pk, file_name)
        doc.storage_path = object_path
        doc.save(update_fields=["storage_path", "updated_at"])
        upload_url = gcs.signed_upload_url(object_path, content_type)
        data = self.get_serializer(doc).data
        return Response({**data, "upload_url": upload_url}, status=status.HTTP_201_CREATED)

    @extend_schema(
        request=None,
        responses={202: OpenApiResponse(response=DocumentSerializer)},
    )
    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        doc = self.get_object()
        # Phase 1: the worker is a stub. Flip to processing so the UI shows a pill;
        # Phase 2 wires this to the Cloud Run Job / inline worker.
        doc.status = DocumentStatus.PROCESSING
        doc.error_message = ""
        doc.save(update_fields=["status", "error_message", "updated_at"])
        return Response(self.get_serializer(doc).data, status=status.HTTP_202_ACCEPTED)
```

- [ ] **Step 5: Register the route**

In `backend/config/api_router.py`, add the import and registration:

```python
from collateral_ai.documents.api.views import DocumentViewSet
```

and, alongside the existing registrations:

```python
router.register("documents", DocumentViewSet, basename="document")
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `just pytest collateral_ai/documents/tests/api/test_views.py`
Expected: PASS (7 tests).

- [ ] **Step 7: Run the whole documents suite + a quick schema check**

Run: `just pytest collateral_ai/documents`
Expected: PASS (all documents tests).
Run: `just manage spectacular --file /dev/null`
Expected: exits 0 (schema generates without errors for the new endpoints).

- [ ] **Step 8: Commit**

```bash
git add backend/collateral_ai/documents/api backend/collateral_ai/documents/tests/api backend/config/api_router.py
git commit -m "feat(documents): DocumentViewSet — list, create+upload-url, complete stub"
```

---

### Task 4: Frontend API layer — upload helper + documents hooks

**Files:**
- Modify: `frontend/src/lib/api/schema.d.ts` (regenerated via `just gen-api`)
- Create: `frontend/src/lib/api/upload.ts`
- Create: `frontend/src/lib/api/documents.ts`
- Create: `frontend/src/lib/api/documents.test.ts`

**Interfaces:**
- Consumes: `api` from `./client`, generated `components["schemas"]` types.
- Produces:
  - `putWithProgress(url: string, file: File, onProgress: (pct: number) => void): Promise<void>` (from `./upload`).
  - `type Document = components["schemas"]["Document"]`.
  - `useDocuments(companyId: number)` — TanStack Query; `refetchInterval` polls every 3000 ms while any doc `status === "processing"`, else `false`.
  - `uploadDocument(args: { companyId: number; file: File; onProgress: (pct: number) => void }): Promise<Document>` — POST create → `putWithProgress` → POST complete; returns the completed document.
  - `useCompleteDocument()` — mutation calling `POST /api/documents/{id}/complete/` (used by the retry button).

- [ ] **Step 1: Regenerate the typed schema**

Ensure the local stack is up (`just up`) so `http://localhost:8000/api/schema/` includes the new endpoints, then:

Run: `just gen-api`
Expected: `frontend/src/lib/api/schema.d.ts` now contains `/api/documents/` paths and a `Document` schema.

- [ ] **Step 2: Implement the XHR upload helper (no test — thin I/O wrapper)**

`frontend/src/lib/api/upload.ts`:

```ts
/**
 * PUT a file straight to a signed GCS URL, reporting 0–100 progress.
 * Uses XHR because fetch() cannot report upload progress.
 */
export function putWithProgress(
  url: string,
  file: File,
  onProgress: (pct: number) => void,
): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", url);
    xhr.setRequestHeader("Content-Type", file.type);
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100));
    };
    xhr.onload = () =>
      xhr.status >= 200 && xhr.status < 300
        ? resolve()
        : reject(new Error("upload_failed"));
    xhr.onerror = () => reject(new Error("upload_failed"));
    xhr.send(file);
  });
}
```

- [ ] **Step 3: Write the failing orchestration test**

`frontend/src/lib/api/documents.test.ts`:

```ts
import { afterEach, describe, expect, it, vi } from "vitest";
import { uploadDocument } from "./documents";
import { api } from "./client";
import * as upload from "./upload";

afterEach(() => vi.restoreAllMocks());

function pdf() {
  return new File(["x"], "report.pdf", { type: "application/pdf" });
}

describe("uploadDocument", () => {
  it("creates the doc, PUTs the bytes with progress, then completes it", async () => {
    const post = vi.spyOn(api, "POST");
    post.mockResolvedValueOnce({
      data: { id: 7, upload_url: "https://gcs/put", status: "pending" },
      error: undefined,
    } as never);
    post.mockResolvedValueOnce({
      data: { id: 7, status: "processing" },
      error: undefined,
    } as never);
    const put = vi.spyOn(upload, "putWithProgress").mockResolvedValue();
    const onProgress = vi.fn();

    const doc = await uploadDocument({ companyId: 3, file: pdf(), onProgress });

    expect(post).toHaveBeenNthCalledWith(1, "/api/documents/", {
      body: { company: 3, file_name: "report.pdf", content_type: "application/pdf" },
    });
    expect(put).toHaveBeenCalledWith("https://gcs/put", expect.any(File), onProgress);
    expect(post).toHaveBeenNthCalledWith(2, "/api/documents/{id}/complete/", {
      params: { path: { id: 7 } },
    });
    expect(doc.status).toBe("processing");
  });

  it("throws upload_not_configured when create returns 503", async () => {
    vi.spyOn(api, "POST").mockResolvedValue({
      data: undefined,
      error: { detail: "no" },
      response: { status: 503 },
    } as never);
    await expect(
      uploadDocument({ companyId: 3, file: pdf(), onProgress: vi.fn() }),
    ).rejects.toThrow("upload_not_configured");
  });
});
```

- [ ] **Step 4: Run the test to verify it fails**

Run (from `frontend/`): `pnpm test documents`
Expected: FAIL (`uploadDocument` not exported).

- [ ] **Step 5: Implement the documents hooks**

`frontend/src/lib/api/documents.ts`:

```ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { components } from "./schema";
import { api } from "./client";
import { putWithProgress } from "./upload";

export type Document = components["schemas"]["Document"];

export function useDocuments(companyId: number) {
  return useQuery({
    queryKey: ["documents", companyId],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/documents/", {
        params: { query: { company: companyId } },
      });
      if (error) throw error;
      return data;
    },
    refetchInterval: (query) =>
      (query.state.data ?? []).some((d) => d.status === "processing") ? 3000 : false,
  });
}

export async function uploadDocument({
  companyId,
  file,
  onProgress,
}: {
  companyId: number;
  file: File;
  onProgress: (pct: number) => void;
}): Promise<Document> {
  const created = await api.POST("/api/documents/", {
    body: { company: companyId, file_name: file.name, content_type: file.type },
  });
  const createStatus = created.response?.status;
  if (created.error || !created.data) {
    throw new Error(createStatus === 503 ? "upload_not_configured" : "upload_failed");
  }
  await putWithProgress(created.data.upload_url, file, onProgress);
  const done = await api.POST("/api/documents/{id}/complete/", {
    params: { path: { id: created.data.id } },
  });
  if (done.error || !done.data) throw new Error("complete_failed");
  return done.data as Document;
}

export function useCompleteDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      const { data, error } = await api.POST("/api/documents/{id}/complete/", {
        params: { path: { id } },
      });
      if (error || !data) throw new Error("complete_failed");
      return data as Document;
    },
    onSuccess: (doc) =>
      qc.invalidateQueries({ queryKey: ["documents", doc.company] }),
  });
}
```

> Note on casts: the create response type includes `upload_url`; the `complete` response is typed as `Document`. If the generated types surface an operation whose error branch collapses the union (as with the logo endpoint), read `response.status` off the un-narrowed result first — the pattern used above and in `companies.ts`.

- [ ] **Step 6: Run the test to verify it passes**

Run (from `frontend/`): `pnpm test documents`
Expected: PASS (2 tests).

- [ ] **Step 7: Typecheck**

Run (from `frontend/`): `pnpm typecheck`
Expected: exit 0. (If casts are needed for the openapi-fetch unions, add them narrowly as noted.)

- [ ] **Step 8: Commit**

```bash
git add frontend/src/lib/api/schema.d.ts frontend/src/lib/api/upload.ts frontend/src/lib/api/documents.ts frontend/src/lib/api/documents.test.ts
git commit -m "feat(documents): frontend upload helper + documents query/mutation hooks"
```

---

### Task 5: Documents tab UI — dropzone, table, progress, polling

**Files:**
- Create: `frontend/src/components/status-pill.tsx`
- Create: `frontend/src/components/documents-tab.tsx`
- Modify: `frontend/src/routes/company-detail.tsx` (add tab bar; Overview holds current content; mount `DocumentsTab`)

**Interfaces:**
- Consumes: `useDocuments`, `uploadDocument`, `useCompleteDocument`, `Document` from `@/lib/api/documents`; `useQueryClient` for invalidation after upload.
- Produces: `StatusPill({ status })` and `DocumentsTab({ companyId })` React components.

- [ ] **Step 1: Implement `StatusPill`**

`frontend/src/components/status-pill.tsx`:

```tsx
import { CheckCircle, CircleNotch, XCircle } from "@phosphor-icons/react";

const MAP: Record<string, { label: string; cls: string; Icon: typeof CheckCircle }> = {
  processed: { label: "Processed", cls: "text-success bg-success-soft", Icon: CheckCircle },
  processing: { label: "Processing", cls: "text-warning bg-warning-soft", Icon: CircleNotch },
  pending: { label: "Processing", cls: "text-warning bg-warning-soft", Icon: CircleNotch },
  failed: { label: "Failed", cls: "text-destructive bg-danger-soft", Icon: XCircle },
};

export function StatusPill({ status }: { status: string }) {
  const s = MAP[status] ?? MAP.pending;
  return (
    <span
      className={`inline-flex items-center gap-[5px] rounded-full px-[10px] py-[3px] text-[11.5px] font-semibold ${s.cls}`}
    >
      <s.Icon size={13} weight="fill" className={status === "processing" ? "animate-spin" : ""} />
      {s.label}
    </span>
  );
}
```

> Confirm token classes exist in the frontend theme: `text-success`/`bg-success-soft`, `text-warning`/`bg-warning-soft`, `bg-danger-soft`, `text-destructive`. If a name differs (the companies UI uses `text-destructive`), use the existing token; add any missing `*-soft` background to the Tailwind `@theme` block per the design tokens in `mvp-frontend-architecture`.

- [ ] **Step 2: Implement `DocumentsTab`**

`frontend/src/components/documents-tab.tsx`:

```tsx
import { useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowClockwise, FilePdf, UploadSimple } from "@phosphor-icons/react";

import { StatusPill } from "@/components/status-pill";
import {
  useCompleteDocument,
  useDocuments,
  uploadDocument,
  type Document,
} from "@/lib/api/documents";

function num(n: number | null | undefined) {
  return n == null ? "—" : String(n);
}

export function DocumentsTab({ companyId }: { companyId: number }) {
  const qc = useQueryClient();
  const { data: docs = [], isLoading } = useDocuments(companyId);
  const retry = useCompleteDocument();
  const fileRef = useRef<HTMLInputElement>(null);
  const [progress, setProgress] = useState<number | null>(null);
  const [error, setError] = useState<string>("");

  async function onFiles(files: FileList | null) {
    if (!files) return;
    setError("");
    for (const file of Array.from(files)) {
      if (file.type !== "application/pdf") {
        setError("Only PDF files are supported.");
        continue;
      }
      setProgress(0);
      try {
        await uploadDocument({ companyId, file, onProgress: setProgress });
      } catch (e) {
        setError(
          e instanceof Error && e.message === "upload_not_configured"
            ? "Document upload isn't configured in this environment."
            : "Upload failed. Try again.",
        );
      }
    }
    setProgress(null);
    qc.invalidateQueries({ queryKey: ["documents", companyId] });
  }

  return (
    <div>
      <input
        ref={fileRef}
        type="file"
        accept="application/pdf"
        multiple
        hidden
        aria-label="Upload PDF documents"
        onChange={(e) => onFiles(e.target.files)}
      />
      <button
        type="button"
        onClick={() => fileRef.current?.click()}
        className="mb-4 flex w-full flex-col items-center gap-2 rounded-2xl border border-dashed border-field bg-subtle py-8 text-center hover:bg-surface"
      >
        <UploadSimple size={22} className="text-faint" />
        <span className="text-[13.5px] font-medium text-body">
          Drop PDFs here or <span className="text-brand">browse</span>
        </span>
        <span className="text-[11.5px] text-faint">PDF only · max 50 MB</span>
      </button>

      {progress !== null && (
        <div className="mb-4 h-[6px] w-full overflow-hidden rounded-full bg-border-soft">
          <div className="h-full bg-brand transition-[width]" style={{ width: `${progress}%` }} />
        </div>
      )}
      {error && <p className="mb-3 text-[12.5px] text-destructive">{error}</p>}

      {isLoading ? (
        <p className="text-[13px] text-mute">Loading…</p>
      ) : docs.length === 0 ? (
        <p className="text-[13px] text-mute">No documents yet. Upload a PDF to get started.</p>
      ) : (
        <div className="overflow-hidden rounded-2xl border border-hairline bg-surface">
          <table className="w-full text-[13px]">
            <thead className="bg-subtle text-[11px] font-semibold uppercase tracking-wide text-faint">
              <tr>
                <th className="px-4 py-[10px] text-left">File name</th>
                <th className="px-4 py-[10px] text-center">Pages</th>
                <th className="px-4 py-[10px] text-center">Chunks</th>
                <th className="px-4 py-[10px] text-center">Tables</th>
                <th className="px-4 py-[10px] text-center">Images</th>
                <th className="px-4 py-[10px] text-right">Status</th>
              </tr>
            </thead>
            <tbody>
              {docs.map((d: Document) => (
                <tr key={d.id} className="border-t border-hairline-soft">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-[9px]">
                      <FilePdf size={18} className="text-destructive" />
                      <span className="font-medium text-body">{d.file_name}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-center text-mute">{num(d.page_count)}</td>
                  <td className="px-4 py-3 text-center text-mute">{num(d.chunks_count)}</td>
                  <td className="px-4 py-3 text-center text-mute">{num(d.tables_count)}</td>
                  <td className="px-4 py-3 text-center text-mute">{num(d.images_count)}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-2">
                      <StatusPill status={d.status} />
                      {d.status === "failed" && (
                        <button
                          type="button"
                          onClick={() => retry.mutate(d.id)}
                          className="flex items-center gap-1 text-[12px] text-brand hover:underline"
                        >
                          <ArrowClockwise size={13} /> Retry
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Add the tab bar to Company Detail (additive)**

In `frontend/src/routes/company-detail.tsx`: add `useState` for the active tab, render an underline tab bar (`Overview | Documents | Generated Materials`), move the existing profile card into the **Overview** panel, and render `<DocumentsTab companyId={Number(companyId)} />` in the **Documents** panel. Leave **Generated Materials** as a simple placeholder (`<p className="text-[13px] text-mute">Coming soon.</p>`).

Insert after the imports:

```tsx
import { useState } from "react";
import { DocumentsTab } from "@/components/documents-tab";

const TABS = ["Overview", "Documents", "Generated Materials"] as const;
type Tab = (typeof TABS)[number];
```

Replace the profile card `<div className="rounded-2xl border border-hairline bg-surface p-6"> … </div>` block by wrapping it in a tab shell. Add above it:

```tsx
const [tab, setTab] = useState<Tab>("Overview");
```

and render the tab bar + panels (keep the existing profile markup inside the Overview branch):

```tsx
<div className="mb-5 flex gap-5 border-b border-hairline">
  {TABS.map((t) => (
    <button
      key={t}
      type="button"
      onClick={() => setTab(t)}
      className={`-mb-px border-b-2 pb-[10px] text-[13.5px] font-medium ${
        tab === t ? "border-brand text-ink" : "border-transparent text-mute hover:text-body"
      }`}
    >
      {t}
    </button>
  ))}
</div>

{tab === "Overview" && (
  <div className="rounded-2xl border border-hairline bg-surface p-6">
    {/* ...existing profile grid markup unchanged... */}
  </div>
)}
{tab === "Documents" && <DocumentsTab companyId={Number(companyId)} />}
{tab === "Generated Materials" && (
  <p className="text-[13px] text-mute">Coming soon.</p>
)}
```

- [ ] **Step 4: Typecheck, lint, and run the frontend test suite**

Run (from `frontend/`): `pnpm typecheck && pnpm lint && pnpm test`
Expected: all pass (existing tests + the new `documents.test.ts`).

- [ ] **Step 5: Manual verification (preview)**

With the local stack up (`just up`, then `just gcs-init` for the GCS emulator), open a company detail page, switch to the **Documents** tab, upload a PDF, and confirm: progress bar animates, the row appears with a **Processing** pill (Phase 1 leaves it processing since the worker is a stub), and the list is scoped to the company. A failed state isn't reachable in Phase 1; verify the empty state and the upload error path (e.g., picking a non-PDF shows the inline error).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/status-pill.tsx frontend/src/components/documents-tab.tsx frontend/src/routes/company-detail.tsx
git commit -m "feat(documents): Documents tab — dropzone, table, progress bar, polling"
```

---

### Task 6: Delete a document (API + UI)

Deletes the `Document` row and its stored PDF from GCS. `DocumentChunk` rows (and their
pgvector embeddings) cascade away via the FK — so this also removes vectors once Phase 2 exists,
with no extra code. Extended-image GCS cleanup is added in Phase 2.

**Files:**
- Modify: `backend/collateral_ai/documents/gcs.py` (add `delete_object`)
- Modify: `backend/collateral_ai/documents/api/views.py` (add `DestroyModelMixin` + `perform_destroy`)
- Modify: `backend/collateral_ai/documents/tests/api/test_views.py` (add delete tests)
- Modify: `frontend/src/lib/api/documents.ts` (add `useDeleteDocument`)
- Modify: `frontend/src/lib/api/documents.test.ts` (add delete hook test)
- Modify: `frontend/src/components/documents-tab.tsx` (add per-row delete + confirm)

**Interfaces:**
- Produces: `gcs.delete_object(object_path: str) -> None` (best-effort). `DELETE /api/documents/{id}/` → **204**. `useDeleteDocument()` mutation taking `{ id, companyId }`.

- [ ] **Step 1: Write the failing backend delete tests**

Add to `backend/collateral_ai/documents/tests/api/test_views.py`:

```python
def test_delete_removes_row_and_cleans_gcs(auth_client):
    doc = DocumentFactory(storage_path="media/companies/1/documents/1/doc.pdf")
    with mock.patch(
        "collateral_ai.documents.api.views.gcs.is_configured", return_value=True,
    ), mock.patch(
        "collateral_ai.documents.api.views.gcs.delete_object",
    ) as delete_object:
        resp = auth_client.delete(f"/api/documents/{doc.pk}/")
    assert resp.status_code == HTTPStatus.NO_CONTENT
    assert not Document.objects.filter(pk=doc.pk).exists()
    delete_object.assert_called_once_with("media/companies/1/documents/1/doc.pdf")


def test_delete_skips_gcs_when_unconfigured(auth_client):
    doc = DocumentFactory()
    with mock.patch(
        "collateral_ai.documents.api.views.gcs.is_configured", return_value=False,
    ), mock.patch(
        "collateral_ai.documents.api.views.gcs.delete_object",
    ) as delete_object:
        resp = auth_client.delete(f"/api/documents/{doc.pk}/")
    assert resp.status_code == HTTPStatus.NO_CONTENT
    delete_object.assert_not_called()
```

- [ ] **Step 2: Run to verify they fail**

Run: `just pytest collateral_ai/documents/tests/api/test_views.py -k delete`
Expected: FAIL (405 Method Not Allowed — no `DestroyModelMixin` yet).

- [ ] **Step 3: Add the GCS delete helper**

Append to `backend/collateral_ai/documents/gcs.py`:

```python
import logging

from collateral_ai.companies.gcs import _bucket

logger = logging.getLogger(__name__)


def delete_object(object_path: str) -> None:
    """Best-effort delete of a stored object; never raises."""
    try:
        _bucket().blob(object_path).delete()
    except Exception:  # noqa: BLE001 — cleanup must not block the row delete
        logger.warning("Failed to delete GCS object %s", object_path, exc_info=True)
```

> Self-contained on `main` (uses `companies.gcs._bucket`, which exists there). The company-CRUD
> branch adds its own `companies.gcs.delete_object`; there is no collision with this one.

- [ ] **Step 4: Add destroy to the viewset**

In `backend/collateral_ai/documents/api/views.py`, import and add the mixin:

```python
from rest_framework.mixins import DestroyModelMixin
```

Add `DestroyModelMixin` to the `DocumentViewSet` base list (e.g. after `CreateModelMixin`), and add:

```python
    def perform_destroy(self, instance):
        if instance.storage_path and gcs.is_configured():
            gcs.delete_object(instance.storage_path)
        instance.delete()
```

- [ ] **Step 5: Run the backend delete tests to verify they pass**

Run: `just pytest collateral_ai/documents/tests/api/test_views.py -k delete`
Expected: PASS (2 tests). Then run the full suite: `just pytest collateral_ai/documents` → PASS.

- [ ] **Step 6: Commit the backend delete**

```bash
git add backend/collateral_ai/documents/gcs.py backend/collateral_ai/documents/api/views.py backend/collateral_ai/documents/tests/api/test_views.py
git commit -m "feat(documents): DELETE endpoint with best-effort GCS cleanup (chunks cascade)"
```

- [ ] **Step 7: Regenerate the schema for the DELETE path**

With the local stack up, run: `just gen-api`
Expected: `schema.d.ts` now types `delete` on `/api/documents/{id}/`.

- [ ] **Step 8: Write the failing delete-hook test**

Add to `frontend/src/lib/api/documents.test.ts`:

```ts
import { useDeleteDocument } from "./documents";

describe("useDeleteDocument", () => {
  it("issues a DELETE for the given id", async () => {
    const del = vi.spyOn(api, "DELETE").mockResolvedValue({ data: undefined, error: undefined } as never);
    const { mutationFn } = useDeleteDocument.__test__({ id: 7, companyId: 3 });
    await mutationFn();
    expect(del).toHaveBeenCalledWith("/api/documents/{id}/", { params: { path: { id: 7 } } });
  });
});
```

> The hook is a TanStack `useMutation`; to keep the test hook-free, factor the request into a
> plain exported `deleteDocument(id: number)` and test that directly instead of the mutation
> wrapper. Prefer this — replace the snippet above with:

```ts
import { deleteDocument } from "./documents";

describe("deleteDocument", () => {
  it("issues a DELETE for the given id", async () => {
    const del = vi.spyOn(api, "DELETE").mockResolvedValue({ data: undefined, error: undefined } as never);
    await deleteDocument(7);
    expect(del).toHaveBeenCalledWith("/api/documents/{id}/", { params: { path: { id: 7 } } });
  });
});
```

- [ ] **Step 9: Run to verify it fails**

Run (from `frontend/`): `pnpm test documents`
Expected: FAIL (`deleteDocument` not exported).

- [ ] **Step 10: Implement `deleteDocument` + `useDeleteDocument`**

Add to `frontend/src/lib/api/documents.ts`:

```ts
export async function deleteDocument(id: number): Promise<void> {
  const { error } = await api.DELETE("/api/documents/{id}/", {
    params: { path: { id } },
  });
  if (error) throw new Error("delete_failed");
}

export function useDeleteDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id }: { id: number; companyId: number }) => deleteDocument(id),
    onSuccess: (_data, { companyId }) =>
      qc.invalidateQueries({ queryKey: ["documents", companyId] }),
  });
}
```

- [ ] **Step 11: Run to verify it passes**

Run (from `frontend/`): `pnpm test documents`
Expected: PASS.

- [ ] **Step 12: Add the delete action to the table**

In `frontend/src/components/documents-tab.tsx`, import the trash icon and hook:

```tsx
import { ArrowClockwise, FilePdf, Trash, UploadSimple } from "@phosphor-icons/react";
import {
  useCompleteDocument,
  useDeleteDocument,
  useDocuments,
  uploadDocument,
  type Document,
} from "@/lib/api/documents";
```

Inside the component add `const del = useDeleteDocument();`, and in the status cell's action group
add a delete button after the Retry button:

```tsx
<button
  type="button"
  onClick={() => {
    if (window.confirm(`Delete “${d.file_name}”? This can’t be undone.`)) {
      del.mutate({ id: d.id, companyId });
    }
  }}
  className="flex items-center gap-1 text-[12px] text-mute hover:text-destructive"
  aria-label={`Delete ${d.file_name}`}
>
  <Trash size={14} />
</button>
```

- [ ] **Step 13: Typecheck, lint, test**

Run (from `frontend/`): `pnpm typecheck && pnpm lint && pnpm test`
Expected: all pass.

- [ ] **Step 14: Commit the frontend delete**

```bash
git add frontend/src/lib/api/schema.d.ts frontend/src/lib/api/documents.ts frontend/src/lib/api/documents.test.ts frontend/src/components/documents-tab.tsx
git commit -m "feat(documents): delete a document from the Documents tab (confirm + invalidate)"
```

---

## Self-Review

**Spec coverage (Phase 1 scope):**
- `Document` model incl. `tables_count`/`images_count`/`updated_at` → Task 1. ✓
- `DocumentStatus` constants → Task 1. ✓
- Company-scoped list, create+upload-url (503/400 guards), complete stub (202) → Task 3. ✓
- Signed PUT direct to GCS, object-path convention → Tasks 2–3. ✓
- Two-call upload flow with progress bar → Task 4 (`uploadDocument` + `putWithProgress`). ✓
- Documents tab: dropzone, table (design columns), StatusPill, polling, retry affordance → Task 5. ✓
- Delete document: `DELETE` endpoint + best-effort GCS PDF cleanup (chunks/vectors cascade in
  Phase 2) + row delete action with confirm → Task 6. ✓
- Schema regen + typed hooks → Task 4 (+ Task 6 regen for the DELETE path). ✓
- `DocumentChunk`, pgvector, worker, Vertex, Cloud Run Job, Pulumi → **Phase 2** (out of scope here, by design). ✓

**Placeholder scan:** No TBD/TODO; every code step shows the code. The one prose step (Task 5 Step 3) edits an existing file whose full contents are already in the repo — it gives exact insertion points and code, and instructs keeping the existing profile markup verbatim inside the Overview branch.

**Type consistency:** `uploadDocument`/`useDocuments`/`useCompleteDocument`/`putWithProgress` signatures match across Tasks 4 and 5. `DocumentStatus` string values (`pending`/`processing`/`processed`/`failed`) are consistent across model, view, StatusPill, and polling predicate. Response shapes (`create` → `{...doc, upload_url}`; `complete` → `Document` with `status`) match the tests and hooks.

**Note carried to Phase 2:** the `complete` view currently only flips status; Phase 2 replaces the stub body with the worker trigger (Cloud Run Job / inline `call_command`) and the status becomes worker-driven.
