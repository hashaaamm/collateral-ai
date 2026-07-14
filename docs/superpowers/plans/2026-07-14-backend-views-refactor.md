# Backend Views Refactor (Thin Views + Services) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring the five DRF API modules into compliance with `backend/AGENTS.md`: views become pure wiring; validation moves into input serializers; business logic moves into per-app `services.py`; domain errors map through a config-level DRF exception handler; materials filtering becomes a django-filter FilterSet.

**Architecture:** Views wire queryset + serializers + `@extend_schema` only. Write serializers' `create()` call services; command-style endpoints (signed URLs, complete, regenerate) validate with a serializer then call the service from the view. Services are plain functions in `<app>/services.py` that never touch `request`/`Response` and raise `DomainError` subclasses, rendered as `{"detail": ...}` by `config/exception_handler.py`.

**Tech Stack:** Django 6.0.6, DRF 3.17.1, drf-spectacular 0.30.0, django-filter (added in Task 5), pytest + factory-boy, uv, docker compose (`just pytest`).

**Spec:** `docs/superpowers/specs/2026-07-14-backend-views-refactor-design.md`

## Global Constraints

- **Wire-identical** for all success responses and status codes. Only two approved deviations: (1) invalid numeric filter values on the materials list become **400** (today silently ignored); (2) the two hand-rolled 400 bodies (documents create, companies logo-upload-url) become DRF-standard field-keyed errors.
- OpenAPI **component names may change**; response *shapes* may not. Task 7 diffs the schema to prove it.
- Error `detail` strings must stay **byte-identical**: "Logo upload is not configured in this environment.", "Document upload is not configured in this environment.", "Document viewing is not configured in this environment.", "Document has no stored file.", "Generation is already in progress.", "Generation could not be started. Please try again.", "Processing could not be started. Please try again."
- `users` app and `TemplateViewSet` are **untouched**.
- Code style: ruff-enforced — imports one-per-line at top of file (PLC0415), exception messages via `msg = "..."` variable (EM101), ~88-char lines. Match existing comment density; keep the load-bearing comments (savepoint rationale, staleness policy, inline-trigger note) with the moved code.
- All test commands run from `backend/`: `just pytest <args>` (docker). **The main checkout's stack must be down first** (`just down` in `~/dev/CollateralAI/backend`) — fixed container names collide with this worktree.
- Commit after every task; messages end with `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.

---

### Task 1: Domain errors + DRF exception handler

**Files:**
- Create: `backend/collateral_ai/core/__init__.py`
- Create: `backend/collateral_ai/core/exceptions.py`
- Create: `backend/collateral_ai/core/tests/__init__.py`
- Create: `backend/collateral_ai/core/tests/test_exceptions.py`
- Create: `backend/config/exception_handler.py`
- Modify: `backend/config/settings/base.py:292-304` (REST_FRAMEWORK dict)

**Interfaces:**
- Produces: `collateral_ai.core.exceptions.DomainError(detail: str | None = None)` with attrs `status_code: int`, `detail: str`; subclasses `StorageNotConfiguredError` (503), `GenerationInProgressError` (409, default detail "Generation is already in progress."), `NoStoredFileError` (404, default detail "Document has no stored file."). `config.exception_handler.api_exception_handler(exc, context)` renders any `DomainError` as `Response({"detail": exc.detail}, status=exc.status_code)`. Tasks 2–4 raise these from services.

- [ ] **Step 0: Snapshot the pre-refactor OpenAPI schema (baseline for Task 7)**

```bash
cd ~/dev/CollateralAI/backend && just down   # avoid container-name collision
cd "$OLDPWD"  # back to the worktree
cd backend
just manage spectacular --file /app/schema-baseline.yml   # /app = bind-mounted repo dir
mv schema-baseline.yml /tmp/schema-baseline.yml
```

If the file doesn't appear next to `manage.py`, the bind-mount target differs — check with `grep -B2 -A6 'django:' docker-compose.local.yml` and write to wherever the repo dir is mounted. Keep the file OUT of git.

- [ ] **Step 1: Write the failing tests**

`backend/collateral_ai/core/tests/__init__.py` — empty file.

`backend/collateral_ai/core/tests/test_exceptions.py`:

```python
from http import HTTPStatus

from rest_framework.exceptions import NotFound

from collateral_ai.core.exceptions import DomainError
from collateral_ai.core.exceptions import GenerationInProgressError
from collateral_ai.core.exceptions import NoStoredFileError
from collateral_ai.core.exceptions import StorageNotConfiguredError
from config.exception_handler import api_exception_handler


def test_domain_error_renders_detail_and_status():
    exc = StorageNotConfiguredError("Logo upload is not configured in this environment.")
    resp = api_exception_handler(exc, context={})
    assert resp.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert resp.data == {
        "detail": "Logo upload is not configured in this environment.",
    }


def test_domain_error_default_details():
    assert GenerationInProgressError().detail == "Generation is already in progress."
    assert NoStoredFileError().detail == "Document has no stored file."
    conflict = api_exception_handler(GenerationInProgressError(), context={})
    assert conflict.status_code == HTTPStatus.CONFLICT
    missing = api_exception_handler(NoStoredFileError(), context={})
    assert missing.status_code == HTTPStatus.NOT_FOUND


def test_drf_exceptions_still_use_default_handler():
    resp = api_exception_handler(NotFound(), context={})
    assert resp.status_code == HTTPStatus.NOT_FOUND
    assert resp.data == {"detail": "Not found."}


def test_non_api_exceptions_return_none():
    # None means Django's normal 500 handling takes over — unchanged behavior.
    assert api_exception_handler(RuntimeError("boom"), context={}) is None


def test_str_is_the_detail():
    assert str(DomainError("nope")) == "nope"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `just pytest collateral_ai/core/tests/test_exceptions.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'collateral_ai.core'`

- [ ] **Step 3: Implement**

`backend/collateral_ai/core/__init__.py` — empty file (plain package, not a Django app: no models, no AppConfig needed).

`backend/collateral_ai/core/exceptions.py`:

```python
"""Domain errors raised by app services.

Services never touch request/Response (AGENTS.md); they raise these instead.
config.exception_handler renders any DomainError as {"detail": ...} with the
class's status code, keeping the wire format identical to a hand-built
Response({"detail": ...}, status=...).
"""

from __future__ import annotations


class DomainError(Exception):
    status_code = 400
    default_detail = "Invalid request."

    def __init__(self, detail: str | None = None) -> None:
        self.detail = detail or self.default_detail
        super().__init__(self.detail)


class StorageNotConfiguredError(DomainError):
    """GCS is not configured (no GS_BUCKET_NAME) — feature unavailable."""

    status_code = 503
    default_detail = "Storage is not configured in this environment."


class GenerationInProgressError(DomainError):
    """A fresh generation run is already active for this material."""

    status_code = 409
    default_detail = "Generation is already in progress."


class NoStoredFileError(DomainError):
    """The document row exists but no object was ever stored for it."""

    status_code = 404
    default_detail = "Document has no stored file."
```

`backend/config/exception_handler.py`:

```python
"""Project-wide DRF exception handler.

DomainError (raised by app services) → {"detail": ...} with the error's
status code; everything else defers to DRF's default handler.
"""

from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from collateral_ai.core.exceptions import DomainError


def api_exception_handler(exc, context):
    if isinstance(exc, DomainError):
        return Response({"detail": exc.detail}, status=exc.status_code)
    return drf_exception_handler(exc, context)
```

In `backend/config/settings/base.py`, add one line to the existing `REST_FRAMEWORK` dict (after `"DEFAULT_SCHEMA_CLASS"`):

```python
    "EXCEPTION_HANDLER": "config.exception_handler.api_exception_handler",
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `just pytest collateral_ai/core/tests/test_exceptions.py -v`
Expected: 5 PASS

- [ ] **Step 5: Run the full suite (nothing should regress from a handler that only adds a branch)**

Run: `just pytest`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add backend/collateral_ai/core backend/config/exception_handler.py backend/config/settings/base.py
git commit -m "feat(core): domain errors + project-wide DRF exception handler

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: Companies — services + input/response serializers + thin view

**Files:**
- Create: `backend/collateral_ai/companies/services.py`
- Create: `backend/collateral_ai/companies/tests/test_services.py`
- Modify: `backend/collateral_ai/companies/api/serializers.py` (append)
- Modify: `backend/collateral_ai/companies/api/views.py` (rewrite)
- Modify: `backend/collateral_ai/companies/tests/api/test_views.py` (patch targets only)

**Interfaces:**
- Consumes: `collateral_ai.core.exceptions.StorageNotConfiguredError` (Task 1).
- Produces: `companies.services.create_logo_upload_url(*, filename: str, content_type: str) -> tuple[str, str]` returning `(upload_url, object_path)`, raising `StorageNotConfiguredError`; `companies.services.delete_company(company: Company) -> None`. Serializers `LogoUploadUrlRequestSerializer`, `LogoUploadUrlResponseSerializer`; module constant `ALLOWED_LOGO_TYPES` moves from views.py to serializers.py.

- [ ] **Step 1: Write the failing service tests**

`backend/collateral_ai/companies/tests/test_services.py`:

```python
from unittest import mock

import pytest

from collateral_ai.companies import services
from collateral_ai.companies.tests.factories import CompanyFactory
from collateral_ai.core.exceptions import StorageNotConfiguredError

pytestmark = pytest.mark.django_db


def test_create_logo_upload_url_raises_when_unconfigured():
    with (
        mock.patch(
            "collateral_ai.companies.services.gcs.is_configured",
            return_value=False,
        ),
        pytest.raises(StorageNotConfiguredError) as excinfo,
    ):
        services.create_logo_upload_url(filename="a.png", content_type="image/png")
    assert str(excinfo.value) == (
        "Logo upload is not configured in this environment."
    )


def test_create_logo_upload_url_returns_url_and_path():
    with (
        mock.patch(
            "collateral_ai.companies.services.gcs.is_configured",
            return_value=True,
        ),
        mock.patch(
            "collateral_ai.companies.services.gcs.build_logo_object_path",
            return_value="media/companies/logos/x/a.png",
        ),
        mock.patch(
            "collateral_ai.companies.services.gcs.signed_upload_url",
            return_value="https://signed-put",
        ) as sign,
    ):
        url, path = services.create_logo_upload_url(
            filename="a.png",
            content_type="image/png",
        )
    assert url == "https://signed-put"
    assert path == "media/companies/logos/x/a.png"
    sign.assert_called_once_with("media/companies/logos/x/a.png", "image/png")


def test_delete_company_cleans_logo_then_deletes_row():
    company = CompanyFactory(logo="media/companies/logos/x/a.png")
    with (
        mock.patch(
            "collateral_ai.companies.services.gcs.is_configured",
            return_value=True,
        ),
        mock.patch(
            "collateral_ai.companies.services.gcs.delete_object",
        ) as delete_object,
    ):
        services.delete_company(company)
    delete_object.assert_called_once_with("media/companies/logos/x/a.png")
    assert not type(company).objects.filter(pk=company.pk).exists()


def test_delete_company_without_logo_skips_gcs():
    company = CompanyFactory(logo="")
    with mock.patch(
        "collateral_ai.companies.services.gcs.delete_object",
    ) as delete_object:
        services.delete_company(company)
    delete_object.assert_not_called()
    assert not type(company).objects.filter(pk=company.pk).exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `just pytest collateral_ai/companies/tests/test_services.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'collateral_ai.companies.services'`

- [ ] **Step 3: Implement the service**

`backend/collateral_ai/companies/services.py`:

```python
"""Business operations for companies."""

from __future__ import annotations

from collateral_ai.companies import gcs
from collateral_ai.companies.models import Company
from collateral_ai.core.exceptions import StorageNotConfiguredError


def create_logo_upload_url(*, filename: str, content_type: str) -> tuple[str, str]:
    """Return (upload_url, object_path) for a direct browser PUT of a logo."""
    if not gcs.is_configured():
        msg = "Logo upload is not configured in this environment."
        raise StorageNotConfiguredError(msg)
    object_path = gcs.build_logo_object_path(filename)
    return gcs.signed_upload_url(object_path, content_type), object_path


def delete_company(company: Company) -> None:
    """Delete the row and best-effort clean up the stored logo."""
    if company.logo and gcs.is_configured():
        gcs.delete_object(company.logo)
    company.delete()
```

- [ ] **Step 4: Run service tests to verify they pass**

Run: `just pytest collateral_ai/companies/tests/test_services.py -v`
Expected: 4 PASS

- [ ] **Step 5: Add the input/response serializers**

Append to `backend/collateral_ai/companies/api/serializers.py`:

```python
ALLOWED_LOGO_TYPES = ["image/png", "image/jpeg", "image/webp", "image/svg+xml"]


class LogoUploadUrlRequestSerializer(serializers.Serializer):
    filename = serializers.CharField()
    content_type = serializers.ChoiceField(choices=ALLOWED_LOGO_TYPES)


class LogoUploadUrlResponseSerializer(serializers.Serializer):
    upload_url = serializers.URLField()
    object_path = serializers.CharField()
```

- [ ] **Step 6: Rewrite the view as wiring only**

Replace the entire contents of `backend/collateral_ai/companies/api/views.py` with:

```python
from drf_spectacular.utils import extend_schema
from rest_framework import filters
from rest_framework.decorators import action
from rest_framework.mixins import CreateModelMixin
from rest_framework.mixins import DestroyModelMixin
from rest_framework.mixins import ListModelMixin
from rest_framework.mixins import RetrieveModelMixin
from rest_framework.mixins import UpdateModelMixin
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from collateral_ai.companies import services
from collateral_ai.companies.models import Company

from .serializers import CompanySerializer
from .serializers import LogoUploadUrlRequestSerializer
from .serializers import LogoUploadUrlResponseSerializer


class CompanyViewSet(
    RetrieveModelMixin,
    ListModelMixin,
    CreateModelMixin,
    UpdateModelMixin,
    DestroyModelMixin,
    GenericViewSet,
):
    serializer_class = CompanySerializer
    queryset = Company.objects.all()
    filter_backends = [filters.SearchFilter]
    search_fields = ["name"]

    def perform_destroy(self, instance):
        services.delete_company(instance)

    @extend_schema(
        request=LogoUploadUrlRequestSerializer,
        responses=LogoUploadUrlResponseSerializer,
    )
    @action(detail=False, methods=["post"], url_path="logo-upload-url")
    def logo_upload_url(self, request):
        body = LogoUploadUrlRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        upload_url, object_path = services.create_logo_upload_url(
            **body.validated_data,
        )
        data = {"upload_url": upload_url, "object_path": object_path}
        return Response(LogoUploadUrlResponseSerializer(data).data)
```

Note the removals: `ALLOWED_LOGO_TYPES`, the `gcs` import, `inline_serializer`, `serializers`, and `status` imports are gone from views.py.

- [ ] **Step 7: Update endpoint-test patch targets**

In `backend/collateral_ai/companies/tests/api/test_views.py`, replace every string `"collateral_ai.companies.api.views.gcs.` with `"collateral_ai.companies.services.gcs.` (the two `api.serializers.gcs` patches at lines ~56-60 stay as they are — `CompanySerializer.get_logo_url` did not move). Affected tests: `test_logo_upload_url_503_when_unconfigured`, `test_logo_upload_url_returns_signed_put`, `test_delete_removes_company_and_cleans_logo`, `test_delete_without_logo_skips_cleanup`.

- [ ] **Step 8: Run the app's full test suite**

Run: `just pytest collateral_ai/companies -v`
Expected: all pass — including `test_logo_upload_url_rejects_bad_content_type` (asserts only the 400 status, which the ChoiceField still produces) and the 503 test (its request body is valid, so validation-before-configured-check does not change its outcome).

- [ ] **Step 9: Commit**

```bash
git add backend/collateral_ai/companies
git commit -m "refactor(companies): move logo-URL + delete logic to services, validate via serializer

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: Documents — services + input/response serializers + thin view

**Files:**
- Create: `backend/collateral_ai/documents/services.py`
- Create: `backend/collateral_ai/documents/tests/test_services.py`
- Modify: `backend/collateral_ai/documents/api/serializers.py` (append)
- Modify: `backend/collateral_ai/documents/api/views.py` (rewrite)
- Modify: `backend/collateral_ai/documents/tests/api/test_views.py` (patch targets only)

**Interfaces:**
- Consumes: `StorageNotConfiguredError`, `NoStoredFileError` (Task 1); `documents.gcs` (`is_configured`, `build_document_object_path(company_id, document_id, filename)`, `signed_upload_url(path, content_type)`, `signed_get_url(path)`, `delete_object(path)`); `documents.worker_trigger.trigger_processing(document)`.
- Produces: `documents.services.create_document_with_upload_url(*, company_id: int, file_name: str, content_type: str) -> tuple[Document, str]`; `documents.services.start_processing(document: Document) -> Document`; `documents.services.get_view_url(document: Document) -> str`; `documents.services.delete_document(document: Document) -> None`. Serializers `DocumentCreateSerializer`, `DocumentWithUploadUrlSerializer`, `DocumentViewUrlSerializer`.

- [ ] **Step 1: Write the failing service tests**

`backend/collateral_ai/documents/tests/test_services.py`:

```python
from unittest import mock

import pytest

from collateral_ai.companies.tests.factories import CompanyFactory
from collateral_ai.core.exceptions import NoStoredFileError
from collateral_ai.core.exceptions import StorageNotConfiguredError
from collateral_ai.documents import services
from collateral_ai.documents.models import Document
from collateral_ai.documents.statuses import DocumentStatus
from collateral_ai.documents.tests.factories import DocumentFactory

pytestmark = pytest.mark.django_db


def test_create_document_raises_when_unconfigured():
    company = CompanyFactory()
    with (
        mock.patch(
            "collateral_ai.documents.services.gcs.is_configured",
            return_value=False,
        ),
        pytest.raises(StorageNotConfiguredError) as excinfo,
    ):
        services.create_document_with_upload_url(
            company_id=company.pk,
            file_name="a.pdf",
            content_type="application/pdf",
        )
    assert str(excinfo.value) == (
        "Document upload is not configured in this environment."
    )


def test_create_document_reserves_row_and_signs_url():
    company = CompanyFactory()
    with (
        mock.patch(
            "collateral_ai.documents.services.gcs.is_configured",
            return_value=True,
        ),
        mock.patch(
            "collateral_ai.documents.services.gcs.signed_upload_url",
            return_value="https://signed-put",
        ),
    ):
        doc, upload_url = services.create_document_with_upload_url(
            company_id=company.pk,
            file_name="a.pdf",
            content_type="application/pdf",
        )
    assert upload_url == "https://signed-put"
    assert doc.status == DocumentStatus.PENDING
    assert doc.company_id == company.pk
    assert doc.storage_path.startswith(f"media/companies/{company.pk}/documents/")


def test_start_processing_marks_failed_on_dispatch_error():
    doc = DocumentFactory(status=DocumentStatus.PENDING)
    with mock.patch(
        "collateral_ai.documents.services.trigger_processing",
        side_effect=RuntimeError("job boom"),
    ):
        doc = services.start_processing(doc)
    assert doc.status == DocumentStatus.FAILED
    assert doc.error_message == "Processing could not be started. Please try again."


def test_start_processing_flips_status_and_triggers():
    doc = DocumentFactory(status=DocumentStatus.PENDING, error_message="old")
    with mock.patch(
        "collateral_ai.documents.services.trigger_processing",
    ) as trigger:
        doc = services.start_processing(doc)
    trigger.assert_called_once()
    assert doc.status == DocumentStatus.PROCESSING
    assert doc.error_message == ""


def test_get_view_url_raises_without_stored_file():
    doc = DocumentFactory(storage_path="")
    with (
        mock.patch(
            "collateral_ai.documents.services.gcs.is_configured",
            return_value=True,
        ),
        pytest.raises(NoStoredFileError),
    ):
        services.get_view_url(doc)


def test_delete_document_cleans_gcs_then_deletes_row():
    doc = DocumentFactory(storage_path="media/companies/1/documents/1/doc.pdf")
    with (
        mock.patch(
            "collateral_ai.documents.services.gcs.is_configured",
            return_value=True,
        ),
        mock.patch(
            "collateral_ai.documents.services.gcs.delete_object",
        ) as delete_object,
    ):
        services.delete_document(doc)
    delete_object.assert_called_once_with("media/companies/1/documents/1/doc.pdf")
    assert not Document.objects.filter(pk=doc.pk).exists()
```

Note: `test_create_document_reserves_row_and_signs_url` does NOT mock `build_document_object_path` — the real one runs, so the assertion pins the actual path prefix (same as the existing endpoint test does).

- [ ] **Step 2: Run tests to verify they fail**

Run: `just pytest collateral_ai/documents/tests/test_services.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'collateral_ai.documents.services'`

- [ ] **Step 3: Implement the service**

`backend/collateral_ai/documents/services.py`:

```python
"""Business operations for documents: upload reservation, processing, cleanup."""

from __future__ import annotations

import logging

from django.utils import timezone

from collateral_ai.core.exceptions import NoStoredFileError
from collateral_ai.core.exceptions import StorageNotConfiguredError
from collateral_ai.documents import gcs
from collateral_ai.documents.models import Document
from collateral_ai.documents.statuses import DocumentStatus
from collateral_ai.documents.worker_trigger import trigger_processing

logger = logging.getLogger(__name__)

# User-facing failure text; the real exception is logged server-side, never
# sent to clients.
_GENERIC_DISPATCH_ERROR = "Processing could not be started. Please try again."


def create_document_with_upload_url(
    *,
    company_id: int,
    file_name: str,
    content_type: str,
) -> tuple[Document, str]:
    """Reserve a PENDING row and return (document, signed PUT url).

    ATOMIC_REQUESTS wraps the calling request in a transaction, so if signing
    raises the row is rolled back — no orphan PENDING row is left behind.
    """
    if not gcs.is_configured():
        msg = "Document upload is not configured in this environment."
        raise StorageNotConfiguredError(msg)
    doc = Document.objects.create(
        company_id=company_id,
        file_name=file_name,
        content_type=content_type,
        status=DocumentStatus.PENDING,
    )
    object_path = gcs.build_document_object_path(company_id, doc.pk, file_name)
    doc.storage_path = object_path
    doc.save(update_fields=["storage_path", "updated_at"])
    return doc, gcs.signed_upload_url(object_path, content_type)


def start_processing(document: Document) -> Document:
    """Flip to PROCESSING, dispatch the worker, return the refreshed row.

    trigger_processing runs the pipeline INLINE (synchronous, in this thread)
    when DOCUMENT_PROCESSOR_JOB is unset — dev/local convenience. In prod it
    fires a Kubernetes Job and returns immediately. If dispatch itself fails
    (e.g. the control plane is unreachable), mark the row failed with a generic
    message — never leak the raw exception — so the client stops polling a doc
    that will never progress.
    """
    document.status = DocumentStatus.PROCESSING
    document.error_message = ""
    document.save(update_fields=["status", "error_message", "updated_at"])
    try:
        trigger_processing(document)
    except Exception:
        logger.exception("Document %s processing dispatch failed", document.pk)
        Document.objects.filter(pk=document.pk).update(
            status=DocumentStatus.FAILED,
            error_message=_GENERIC_DISPATCH_ERROR,
            updated_at=timezone.now(),
        )
    document.refresh_from_db()
    return document


def get_view_url(document: Document) -> str:
    """Signed GET URL so the browser can open the stored PDF (spec §5.3)."""
    if not gcs.is_configured():
        msg = "Document viewing is not configured in this environment."
        raise StorageNotConfiguredError(msg)
    if not document.storage_path:
        raise NoStoredFileError
    return gcs.signed_get_url(document.storage_path)


def delete_document(document: Document) -> None:
    """Delete the row and best-effort clean up the stored object."""
    if document.storage_path and gcs.is_configured():
        gcs.delete_object(document.storage_path)
    document.delete()
```

- [ ] **Step 4: Run service tests to verify they pass**

Run: `just pytest collateral_ai/documents/tests/test_services.py -v`
Expected: 6 PASS

- [ ] **Step 5: Add the input/response serializers**

Append to `backend/collateral_ai/documents/api/serializers.py`:

```python
class DocumentCreateSerializer(serializers.Serializer):
    """Body for reserving an upload: name + type only, no file bytes."""

    file_name = serializers.CharField(max_length=255)  # matches Document.file_name
    content_type = serializers.ChoiceField(choices=["application/pdf"])


class DocumentWithUploadUrlSerializer(DocumentSerializer):
    """201 body for create: the reserved row plus its signed PUT URL."""

    upload_url = serializers.URLField()

    class Meta(DocumentSerializer.Meta):
        fields = [*DocumentSerializer.Meta.fields, "upload_url"]


class DocumentViewUrlSerializer(serializers.Serializer):
    url = serializers.URLField()
```

- [ ] **Step 6: Rewrite the view as wiring only**

Replace the entire contents of `backend/collateral_ai/documents/api/views.py` with:

```python
from drf_spectacular.utils import OpenApiResponse
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.mixins import CreateModelMixin
from rest_framework.mixins import DestroyModelMixin
from rest_framework.mixins import ListModelMixin
from rest_framework.mixins import RetrieveModelMixin
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from collateral_ai.documents import services
from collateral_ai.documents.models import Document

from .serializers import DocumentCreateSerializer
from .serializers import DocumentSerializer
from .serializers import DocumentViewUrlSerializer
from .serializers import DocumentWithUploadUrlSerializer


class DocumentViewSet(
    ListModelMixin,
    RetrieveModelMixin,
    CreateModelMixin,
    DestroyModelMixin,
    GenericViewSet,
):
    serializer_class = DocumentSerializer
    queryset = Document.objects.all()

    def get_queryset(self):
        # Nested under companies: company comes from the URL, always present.
        return super().get_queryset().filter(company_id=self.kwargs["company_pk"])

    @extend_schema(
        request=DocumentCreateSerializer,
        responses={201: DocumentWithUploadUrlSerializer},
    )
    def create(self, request, *args, **kwargs):
        body = DocumentCreateSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        doc, upload_url = services.create_document_with_upload_url(
            company_id=int(self.kwargs["company_pk"]),
            **body.validated_data,
        )
        doc.upload_url = upload_url  # non-model field consumed by the serializer
        return Response(
            DocumentWithUploadUrlSerializer(doc).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        request=None,
        responses={202: OpenApiResponse(response=DocumentSerializer)},
    )
    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None, company_pk=None):
        doc = services.start_processing(self.get_object())
        return Response(self.get_serializer(doc).data, status=status.HTTP_202_ACCEPTED)

    @extend_schema(request=None, responses=DocumentViewUrlSerializer)
    @action(detail=True, methods=["get"], url_path="view-url")
    def view_url(self, request, pk=None, company_pk=None):
        url = services.get_view_url(self.get_object())
        return Response(DocumentViewUrlSerializer({"url": url}).data)

    def perform_destroy(self, instance):
        services.delete_document(instance)
```

- [ ] **Step 7: Update endpoint-test patch targets**

In `backend/collateral_ai/documents/tests/api/test_views.py`, replace every occurrence of:
- `"collateral_ai.documents.api.views.gcs.` → `"collateral_ai.documents.services.gcs.`
- `"collateral_ai.documents.api.views.trigger_processing"` → `"collateral_ai.documents.services.trigger_processing"`

- [ ] **Step 8: Run the app's full test suite**

Run: `just pytest collateral_ai/documents -v`
Expected: all pass. The 400-body tests (`test_create_rejects_non_pdf`, `test_create_rejects_overlong_file_name`) assert only the status code, which the serializer still produces; the 503 test posts a valid body so the validation-first ordering doesn't change its outcome (this ordering swap is the only behavior change on this endpoint, covered by approved deviation 2).

- [ ] **Step 9: Commit**

```bash
git add backend/collateral_ai/documents
git commit -m "refactor(documents): move upload/processing/cleanup logic to services, validate via serializer

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: Materials — services + serializer-driven create + thin views

**Files:**
- Create: `backend/collateral_ai/materials/services.py`
- Create: `backend/collateral_ai/materials/tests/test_services.py`
- Modify: `backend/collateral_ai/materials/api/serializers.py` (add `create()` to `MaterialCreateSerializer` + one import)
- Modify: `backend/collateral_ai/materials/api/views.py` (strip business logic; keep filtering as-is until Task 5)
- Modify: `backend/collateral_ai/materials/tests/api/test_material_views.py:26` (TRIGGER constant)

**Interfaces:**
- Consumes: `GenerationInProgressError` (Task 1); `materials.worker_trigger.trigger_generation(material) -> str`.
- Produces: `materials.services.create_material(**validated_data) -> MarketingMaterial`; `materials.services.dispatch_generation(material) -> None`; `materials.services.regenerate_material(material, *, prompt: str | None = None) -> MarketingMaterial` raising `GenerationInProgressError`; `materials.services.STALE_AFTER` (moves from views.py).

- [ ] **Step 1: Write the failing service tests**

`backend/collateral_ai/materials/tests/test_services.py`:

```python
import datetime
from unittest import mock

import pytest
from django.utils import timezone

from collateral_ai.core.exceptions import GenerationInProgressError
from collateral_ai.materials import services
from collateral_ai.materials.models import MarketingMaterial
from collateral_ai.materials.statuses import GenerationStatus
from collateral_ai.materials.statuses import ReviewStatus
from collateral_ai.materials.tests.factories import MarketingMaterialFactory

pytestmark = pytest.mark.django_db

TRIGGER = "collateral_ai.materials.services.trigger_generation"


def test_dispatch_failure_marks_failed_with_generic_message():
    material = MarketingMaterialFactory(generation_status=GenerationStatus.QUEUED)
    with mock.patch(TRIGGER, side_effect=RuntimeError("job boom")):
        services.dispatch_generation(material)
    material.refresh_from_db()
    assert material.generation_status == GenerationStatus.FAILED
    assert material.error_message == (
        "Generation could not be started. Please try again."
    )


def test_dispatch_success_stores_operation_name():
    material = MarketingMaterialFactory(generation_status=GenerationStatus.QUEUED)
    with mock.patch(TRIGGER, return_value="operations/abc"):
        services.dispatch_generation(material)
    material.refresh_from_db()
    assert material.job_operation_name == "operations/abc"
    assert material.generation_status == GenerationStatus.QUEUED


def test_regenerate_conflicts_while_fresh_run_is_active():
    material = MarketingMaterialFactory(
        generation_status=GenerationStatus.PROCESSING,
    )
    with pytest.raises(GenerationInProgressError):
        services.regenerate_material(material)


def test_regenerate_takes_over_stale_run():
    material = MarketingMaterialFactory(
        generation_status=GenerationStatus.PROCESSING,
    )
    stale = timezone.now() - services.STALE_AFTER - datetime.timedelta(minutes=1)
    MarketingMaterial.objects.filter(pk=material.pk).update(updated_at=stale)
    with mock.patch(TRIGGER, return_value="") as trigger:
        result = services.regenerate_material(material)
    trigger.assert_called_once()
    assert result.generation_status == GenerationStatus.QUEUED


def test_regenerate_resets_fields_and_applies_prompt():
    material = MarketingMaterialFactory(
        generation_status=GenerationStatus.COMPLETED,
        review_status=ReviewStatus.APPROVED,
        output_json={"headline": "old"},
        error_message="old error",
        job_operation_name="operations/old",
    )
    with mock.patch(TRIGGER, return_value=""):
        result = services.regenerate_material(material, prompt="new prompt")
    assert result.prompt == "new prompt"
    assert result.generation_status == GenerationStatus.QUEUED
    assert result.review_status == ReviewStatus.PENDING
    assert result.output_json is None
    assert result.error_message == ""
    assert result.job_operation_name == ""
    assert result.completed_at is None


def test_create_material_creates_row_and_dispatches():
    template = MarketingMaterialFactory().template
    seed = MarketingMaterialFactory()  # supplies sender/receiver companies
    with mock.patch(TRIGGER, return_value="operations/abc"):
        material = services.create_material(
            title="T",
            sender_company=seed.sender_company,
            receiver_company=seed.receiver_company,
            template=template,
            prompt="p",
        )
    assert material.pk is not None
    assert material.job_operation_name == "operations/abc"
```

If `MarketingMaterialFactory` requires different field names, mirror whatever `collateral_ai/materials/tests/factories.py` actually defines — read it first; do not guess.

- [ ] **Step 2: Run tests to verify they fail**

Run: `just pytest collateral_ai/materials/tests/test_services.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'collateral_ai.materials.services'`

- [ ] **Step 3: Implement the service**

`backend/collateral_ai/materials/services.py`:

```python
"""Business operations for marketing materials: create, dispatch, regenerate."""

from __future__ import annotations

import datetime
import logging

from django.db import transaction
from django.utils import timezone

from collateral_ai.core.exceptions import GenerationInProgressError
from collateral_ai.materials.models import MarketingMaterial
from collateral_ai.materials.statuses import GenerationStatus
from collateral_ai.materials.statuses import ReviewStatus
from collateral_ai.materials.worker_trigger import trigger_generation

logger = logging.getLogger(__name__)

# User-facing failure text. The real exception (which may leak infra details
# like internal hostnames) is logged server-side, never surfaced to the client.
_GENERIC_DISPATCH_ERROR = "Generation could not be started. Please try again."

# A queued/processing row older than this is considered stranded (crashed job)
# and may be regenerated (spec §5.2). Comfortably above the 600s job timeout.
STALE_AFTER = datetime.timedelta(minutes=15)


def create_material(**validated_data) -> MarketingMaterial:
    """Create the row, dispatch generation, return the refreshed row."""
    material = MarketingMaterial.objects.create(**validated_data)
    dispatch_generation(material)
    material.refresh_from_db()
    return material


def dispatch_generation(material: MarketingMaterial) -> None:
    """Trigger the worker inside its own savepoint (spec §5.5).

    The request runs under ATOMIC_REQUESTS; the inner atomic() means a
    failing trigger (or a poisoned inline run) can't take the created row
    down with it — we mark the material failed and the caller still returns
    success.
    """
    try:
        with transaction.atomic():
            operation_name = trigger_generation(material)
    except Exception:  # any trigger failure → failed row, generic client message
        logger.exception("Material %s generation dispatch failed", material.pk)
        MarketingMaterial.objects.filter(pk=material.pk).update(
            generation_status=GenerationStatus.FAILED,
            error_message=_GENERIC_DISPATCH_ERROR,
            updated_at=timezone.now(),
        )
    else:
        if operation_name:
            MarketingMaterial.objects.filter(pk=material.pk).update(
                job_operation_name=operation_name,
                updated_at=timezone.now(),
            )


def regenerate_material(
    material: MarketingMaterial,
    *,
    prompt: str | None = None,
) -> MarketingMaterial:
    """Reset a material and re-queue generation; returns the refreshed row.

    Raises GenerationInProgressError while a fresh (non-stale) run is active. The
    locked re-fetch guards the read-modify-write against a concurrent worker
    completion.
    """
    with transaction.atomic():
        material = MarketingMaterial.objects.select_for_update().get(
            pk=material.pk,
        )
        is_active = material.generation_status in {
            GenerationStatus.QUEUED,
            GenerationStatus.PROCESSING,
        }
        is_stale = material.updated_at < timezone.now() - STALE_AFTER
        if is_active and not is_stale:
            raise GenerationInProgressError
        # Apply an edited prompt in the same locked txn so the row that gets
        # re-queued is the one the new prompt will generate from.
        if prompt is not None:
            material.prompt = prompt
        material.generation_status = GenerationStatus.QUEUED
        material.review_status = ReviewStatus.PENDING
        material.output_json = None
        material.validation_result = None
        material.retrieved_context = None
        material.error_message = ""
        material.job_operation_name = ""
        material.completed_at = None
        material.save()
        material.sources.all().delete()
    dispatch_generation(material)
    material.refresh_from_db()
    return material
```

- [ ] **Step 4: Run service tests to verify they pass**

Run: `just pytest collateral_ai/materials/tests/test_services.py -v`
Expected: 6 PASS

- [ ] **Step 5: Route creation through the serializer**

In `backend/collateral_ai/materials/api/serializers.py`, add the import (with the other `collateral_ai.materials` imports):

```python
from collateral_ai.materials import services
```

and add a `create()` method to `MaterialCreateSerializer` (after its `validate()`):

```python
    def create(self, validated_data: dict) -> MarketingMaterial:
        return services.create_material(**validated_data)
```

- [ ] **Step 6: Strip business logic from the views**

Replace the entire contents of `backend/collateral_ai/materials/api/views.py` with (filtering stays hand-rolled in this task — Task 5 replaces it):

```python
from django.db.models import Q
from drf_spectacular.utils import OpenApiParameter
from drf_spectacular.utils import OpenApiResponse
from drf_spectacular.utils import extend_schema
from drf_spectacular.utils import extend_schema_view
from rest_framework import filters
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.mixins import CreateModelMixin
from rest_framework.mixins import DestroyModelMixin
from rest_framework.mixins import ListModelMixin
from rest_framework.mixins import RetrieveModelMixin
from rest_framework.mixins import UpdateModelMixin
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from collateral_ai.materials import services
from collateral_ai.materials.models import MarketingMaterial
from collateral_ai.materials.models import Template

from .serializers import MaterialCreateSerializer
from .serializers import MaterialDetailSerializer
from .serializers import MaterialListSerializer
from .serializers import MaterialRegenerateSerializer
from .serializers import MaterialUpdateSerializer
from .serializers import TemplateSerializer

LIST_FILTER_PARAMS = [
    OpenApiParameter("company", int, description="Sender OR receiver company id"),
    OpenApiParameter("sender", int),
    OpenApiParameter("receiver", int),
    OpenApiParameter("generation_status", str),
    OpenApiParameter("review_status", str),
]


def _int_param(value: str | None) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


class TemplateViewSet(
    ListModelMixin,
    RetrieveModelMixin,
    CreateModelMixin,
    GenericViewSet,
):
    """Templates are create-only in MVP: no update/delete (spec §5.1)."""

    serializer_class = TemplateSerializer
    queryset = Template.objects.all()


@extend_schema_view(list=extend_schema(parameters=LIST_FILTER_PARAMS))
class MaterialViewSet(
    ListModelMixin,
    RetrieveModelMixin,
    CreateModelMixin,
    UpdateModelMixin,
    DestroyModelMixin,
    GenericViewSet,
):
    queryset = MarketingMaterial.objects.select_related(
        "sender_company",
        "receiver_company",
        "template",
    ).all()
    serializer_class = MaterialDetailSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ["title"]

    def get_serializer_class(self):
        if self.action == "list":
            return MaterialListSerializer
        if self.action == "create":
            return MaterialCreateSerializer
        if self.action in {"update", "partial_update"}:
            return MaterialUpdateSerializer
        return MaterialDetailSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        if (company := _int_param(params.get("company"))) is not None:
            qs = qs.filter(
                Q(sender_company_id=company) | Q(receiver_company_id=company),
            )
        if (sender := _int_param(params.get("sender"))) is not None:
            qs = qs.filter(sender_company_id=sender)
        if (receiver := _int_param(params.get("receiver"))) is not None:
            qs = qs.filter(receiver_company_id=receiver)
        if generation_status := params.get("generation_status"):
            qs = qs.filter(generation_status=generation_status)
        if review_status := params.get("review_status"):
            qs = qs.filter(review_status=review_status)
        return qs

    @extend_schema(
        request=MaterialCreateSerializer,
        responses={201: MaterialDetailSerializer},
    )
    def create(self, request, *args, **kwargs):
        # Overridden only to render the detail shape at 201 (wire contract);
        # creation itself runs through the serializer → services.create_material.
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        material = serializer.save()
        return Response(
            MaterialDetailSerializer(material, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        request=MaterialRegenerateSerializer,
        responses={
            202: MaterialDetailSerializer,
            409: OpenApiResponse(description="Generation already in progress"),
        },
    )
    @action(detail=True, methods=["post"])
    def regenerate(self, request, pk=None):
        # get_object() first so DRF's 404/permission checks still apply.
        material = self.get_object()
        body = MaterialRegenerateSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        material = services.regenerate_material(
            material,
            prompt=body.validated_data.get("prompt"),
        )
        return Response(
            MaterialDetailSerializer(material, context={"request": request}).data,
            status=status.HTTP_202_ACCEPTED,
        )
```

Removed relative to the old file: `_dispatch`, `STALE_AFTER`, `_GENERIC_DISPATCH_ERROR`, the `logger`, and the `datetime`/`logging`/`transaction`/`timezone`/statuses/worker_trigger imports.

- [ ] **Step 7: Update the endpoint-test patch target**

In `backend/collateral_ai/materials/tests/api/test_material_views.py` line 26:

```python
TRIGGER = "collateral_ai.materials.services.trigger_generation"
```

- [ ] **Step 8: Run the app's full test suite**

Run: `just pytest collateral_ai/materials -v`
Expected: all pass — the regenerate 409 body (`{"detail": "Generation is already in progress."}`) now comes from `GenerationInProgressError` via the exception handler, byte-identical.

- [ ] **Step 9: Commit**

```bash
git add backend/collateral_ai/materials
git commit -m "refactor(materials): move dispatch/regenerate/create logic to services

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: Materials filtering via django-filter

**Files:**
- Modify: `backend/pyproject.toml` (new dependency, via `uv add`)
- Modify: `backend/config/settings/base.py:72-83` (THIRD_PARTY_APPS)
- Create: `backend/collateral_ai/materials/api/filters.py`
- Modify: `backend/collateral_ai/materials/api/views.py` (swap hand-rolled filtering for FilterSet)
- Modify: `backend/collateral_ai/materials/tests/api/test_material_views.py` (add one test)

**Interfaces:**
- Consumes: `MaterialViewSet` from Task 4.
- Produces: `materials.api.filters.MaterialFilter` (FilterSet with `company`, `sender`, `receiver`, `generation_status`, `review_status`).

- [ ] **Step 1: Add the dependency**

```bash
cd backend && docker compose run --rm django uv add django-filter
```

If the container path fails, run `uv add django-filter` on the host from `backend/` (uv is a host prerequisite for this repo). Then open `pyproject.toml`, find the line uv wrote (e.g. `"django-filter>=25.1",`), and change `>=` to `==` to match the file's exact-pin style, then run `uv lock` to re-lock. Rebuild the test image so the container has the package: `just build`.

- [ ] **Step 2: Register the app**

In `backend/config/settings/base.py`, add to `THIRD_PARTY_APPS` (after `"drf_spectacular",`):

```python
    "django_filters",
```

- [ ] **Step 3: Write the failing tests** (one new behavior test + rely on existing filter tests)

Add to `backend/collateral_ai/materials/tests/api/test_material_views.py` (after `test_list_status_and_search_filters`):

```python
def test_list_rejects_non_numeric_company_filter(auth_client):
    # Approved wire deviation: garbage numeric filters are now a 400 instead
    # of being silently ignored (which returned the full unfiltered list).
    MarketingMaterialFactory()
    resp = auth_client.get(URL, {"sender": "abc"})
    assert resp.status_code == HTTPStatus.BAD_REQUEST
```

- [ ] **Step 4: Run new test to verify it fails**

Run: `just pytest collateral_ai/materials/tests/api/test_material_views.py::test_list_rejects_non_numeric_company_filter -v`
Expected: FAIL — currently returns 200 (value silently ignored)

- [ ] **Step 5: Create the FilterSet**

`backend/collateral_ai/materials/api/filters.py`:

```python
from django.db.models import Q
from django_filters import rest_framework as df

from collateral_ai.materials.models import MarketingMaterial


class MaterialFilter(df.FilterSet):
    """List filters; ``company`` matches sender OR receiver.

    Statuses are CharFilters (not ChoiceFilters) on purpose: an unknown status
    string filters to an empty list, exactly like the pre-django-filter
    behavior, instead of becoming a 400.
    """

    company = df.NumberFilter(method="filter_company")
    sender = df.NumberFilter(field_name="sender_company_id")
    receiver = df.NumberFilter(field_name="receiver_company_id")
    generation_status = df.CharFilter()
    review_status = df.CharFilter()

    class Meta:
        model = MarketingMaterial
        fields = [
            "company",
            "sender",
            "receiver",
            "generation_status",
            "review_status",
        ]

    def filter_company(self, queryset, name, value):
        return queryset.filter(
            Q(sender_company_id=value) | Q(receiver_company_id=value),
        )
```

- [ ] **Step 6: Wire it into the ViewSet**

In `backend/collateral_ai/materials/api/views.py`:

1. Delete: the `LIST_FILTER_PARAMS` list, the `_int_param` function, the whole `get_queryset` method, the `@extend_schema_view(...)` decorator on `MaterialViewSet`, and the now-unused imports `Q`, `OpenApiParameter`, `extend_schema_view`.
2. Add imports:

```python
from django_filters.rest_framework import DjangoFilterBackend

from .filters import MaterialFilter
```

3. Change the ViewSet attributes:

```python
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_class = MaterialFilter
```

(drf-spectacular introspects `filterset_class` natively once `django_filters` is installed — the five query params reappear in the schema automatically.)

- [ ] **Step 7: Run the app's full test suite**

Run: `just pytest collateral_ai/materials -v`
Expected: all pass — including `test_list_company_filter_matches_sender_or_receiver`, `test_list_status_and_search_filters`, and the new 400 test.

- [ ] **Step 8: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock backend/config/settings/base.py backend/collateral_ai/materials
git commit -m "refactor(materials): declarative list filtering via django-filter

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: Dashboard — read aggregates into selectors

**Files:**
- Create: `backend/collateral_ai/dashboard/selectors.py`
- Create: `backend/collateral_ai/dashboard/tests/test_selectors.py`
- Modify: `backend/collateral_ai/dashboard/api/views.py` (rewrite)

**Interfaces:**
- Produces: `dashboard.selectors.get_dashboard_stats() -> dict[str, int]` with keys `companies_count`, `documents_processed`, `documents_processing`, `materials_generated`, `materials_needs_review`.

- [ ] **Step 1: Write the failing test**

`backend/collateral_ai/dashboard/tests/test_selectors.py`:

```python
import pytest

from collateral_ai.companies.tests.factories import CompanyFactory
from collateral_ai.dashboard import selectors
from collateral_ai.documents.statuses import DocumentStatus
from collateral_ai.documents.tests.factories import DocumentFactory
from collateral_ai.materials.statuses import GenerationStatus
from collateral_ai.materials.statuses import ReviewStatus
from collateral_ai.materials.tests.factories import MarketingMaterialFactory

pytestmark = pytest.mark.django_db


def test_get_dashboard_stats_counts():
    CompanyFactory()
    DocumentFactory(status=DocumentStatus.PROCESSED)
    DocumentFactory(status=DocumentStatus.PROCESSING)
    MarketingMaterialFactory(
        generation_status=GenerationStatus.COMPLETED,
        review_status=ReviewStatus.PENDING,
    )
    stats = selectors.get_dashboard_stats()
    # Factories above create extra companies via SubFactories, so only the
    # non-company counts are exact.
    assert stats["companies_count"] >= 1
    assert stats["documents_processed"] == 1
    assert stats["documents_processing"] == 1
    assert stats["materials_generated"] == 1
    assert stats["materials_needs_review"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `just pytest collateral_ai/dashboard/tests/test_selectors.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'collateral_ai.dashboard.selectors'`

- [ ] **Step 3: Implement**

`backend/collateral_ai/dashboard/selectors.py`:

```python
"""Read-side aggregates powering the dashboard's stat cards."""

from __future__ import annotations

from collateral_ai.companies.models import Company
from collateral_ai.documents.models import Document
from collateral_ai.documents.statuses import DocumentStatus
from collateral_ai.materials.models import MarketingMaterial
from collateral_ai.materials.statuses import GenerationStatus
from collateral_ai.materials.statuses import ReviewStatus


def get_dashboard_stats() -> dict[str, int]:
    return {
        "companies_count": Company.objects.count(),
        "documents_processed": Document.objects.filter(
            status=DocumentStatus.PROCESSED,
        ).count(),
        "documents_processing": Document.objects.filter(
            status=DocumentStatus.PROCESSING,
        ).count(),
        "materials_generated": MarketingMaterial.objects.filter(
            generation_status=GenerationStatus.COMPLETED,
        ).count(),
        "materials_needs_review": MarketingMaterial.objects.filter(
            review_status=ReviewStatus.PENDING,
        ).count(),
    }
```

Replace the entire contents of `backend/collateral_ai/dashboard/api/views.py` with:

```python
from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from collateral_ai.dashboard import selectors

from .serializers import DashboardStatsSerializer


class DashboardStatsView(APIView):
    """Aggregate counts powering the dashboard's stat cards."""

    @extend_schema(responses=DashboardStatsSerializer)
    def get(self, request: Request) -> Response:
        return Response(
            DashboardStatsSerializer(selectors.get_dashboard_stats()).data,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `just pytest collateral_ai/dashboard -v`
Expected: all pass (selector test + existing endpoint tests).

- [ ] **Step 5: Commit**

```bash
git add backend/collateral_ai/dashboard
git commit -m "refactor(dashboard): move stat aggregation into selectors

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 7: Full verification sweep

**Files:**
- No new files; possibly small fixes surfaced by lint/schema diff.

**Interfaces:**
- Consumes: everything above.

- [ ] **Step 1: Full test suite**

Run: `just pytest`
Expected: all pass.

- [ ] **Step 2: Lint gates (these block CI merges)**

```bash
cd <repo root>
uv run --project backend pre-commit run --all-files
```

(or `pre-commit run --all-files` if installed globally — use whatever this repo's README/CI uses; check `.github/workflows` if unsure). Expected: clean. Fix anything ruff flags (PLC0415 import placement, EM101 message variables, unused imports in rewritten views).

- [ ] **Step 3: Schema diff**

```bash
cd backend
just manage spectacular --file /app/schema-new.yml
diff /tmp/schema-baseline.yml schema-new.yml | head -200
rm schema-new.yml
```

Expected diff contents — ONLY:
- Component renames: `DocumentCreateRequest`/`DocumentCreateResponse`/`DocumentViewUrl` inline components → `DocumentCreate`/`DocumentWithUploadUrl`/`DocumentViewUrl` named serializer components; `LogoUploadUrlRequest`/`LogoUploadUrl` → `LogoUploadUrlRequest`/`LogoUploadUrlResponse` serializer components.
- Materials list params now generated from `MaterialFilter` (same five names/types; `description` text on `company` may differ, and numeric params may gain `format: decimal` from NumberFilter).
- Request-body content types on the two rewritten POST bodies may list DRF parser types identically to other endpoints.

Anything else (changed response *shapes*, missing endpoints, changed status codes) = refactor bug → fix before proceeding.

- [ ] **Step 4: Local stack smoke test**

From the **main checkout** (`~/dev/CollateralAI/backend` — worktree containers collide) after merging or by checking out this branch there:

```bash
just up
# UI or curl with a token: create company → POST /api/companies/logo-upload-url/
# → POST /api/companies/{id}/documents/ → POST /api/materials/ → POST /api/materials/{id}/regenerate/
just down
```

Expected: 200/201/202 responses matching pre-refactor behavior. (If running the smoke from the worktree instead, stop the main stack first.)

- [ ] **Step 5: Frontend typed-client regen (confirm only renames)**

```bash
cd frontend && pnpm gen:api && pnpm exec tsc --noEmit
```

Expected: regenerated types compile; any frontend references to renamed schema components (e.g. `DocumentCreateResponse`) need a mechanical rename — commit those with the regen if any.

- [ ] **Step 6: Final commit (if steps 2-5 produced fixes)**

```bash
git add -A
git commit -m "chore: verification fixes for views refactor (lint/schema/frontend regen)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```
