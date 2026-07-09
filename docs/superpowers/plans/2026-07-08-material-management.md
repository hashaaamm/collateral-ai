# Material Management & Generation Worker — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the materials feature end-to-end: a `materials` Django app (Template/MarketingMaterial/GenerationSource models + APIs), worker 2 (single-pass Vertex Gemini generation with deterministic validation + repair), and five frontend pages (company Generated Materials tab, global `/materials` list, material detail, create wizard, templates list + builder).

**Architecture:** Mirrors worker 1's shape exactly: DRF viewsets on the existing `/api/` router, a management command triggered inline locally / via Cloud Run Job in prod, pgvector retrieval reusing the documents `EmbeddingService`, and a Vite+React SPA consuming OpenAPI-typed hooks. Spec: `docs/superpowers/specs/2026-07-08-material-management-design.md` (authoritative for all behavior).

**Tech Stack:** Django 6 + DRF + drf-spectacular + pgvector + google-genai (Vertex ADC) + pytest/factory-boy; React 19 + TanStack Router/Query + openapi-fetch + Tailwind v4 + vitest.

## Global Constraints

- Backend tests run from the **repo root**: `docker compose -f docker-compose.local.yml run --rm django pytest <path> -q` (CI does exactly this). `makemigrations`/`manage.py` commands run the same way.
- Frontend commands run from `frontend/`: `pnpm test`, `pnpm typecheck`, `pnpm lint`, `pnpm gen:api` (gen:api needs the backend up: `docker compose -f docker-compose.local.yml up -d django postgres`).
- All API endpoints: `IsAuthenticated` (global default), **no pagination** (codebase convention), drf-spectacular annotations on custom actions.
- GenAI is **Vertex-only** ADC: `genai.Client(vertexai=True, project=settings.GOOGLE_CLOUD_PROJECT, location=settings.VERTEX_LOCATION)` — never an API key.
- Two status fields: `generation_status` (`queued → processing → completed | failed`) and `review_status` (`pending → approved | rejected`). The worker never touches `review_status`.
- Output JSON contract (spec §4): `{template_id, theme, article: {headline, subheadline, body_sections: [{title, text}], cta}, image_slots: [{slot_id, description, source}], source_references: [{source_id, used_fact}]}`. `template_id` (= template slug) and `theme` are **stamped server-side after every model response**; body sections use `title` (never `heading`); no `word_count` fields.
- Template constraint bounds (spec §5.1): `headline_max_words`/`subheadline_max_words`/`cta_max_words` 1–60, `body_section_count` 1–10, `body_section_max_words` 1–300.
- Validator categories exactly: `structure`, `word_limit`, `image_slot`, `source` (no `theme` category).
- New settings all default so CI/tests need no env: `MATERIAL_GENERATOR_JOB=""` (inline), `MATERIAL_GENERATOR_REGION="us-central1"`, `MATERIAL_LLM_MODEL="gemini-2.5-flash"`, `MATERIAL_GENERATION_TEMPERATURE=0.2`, `MATERIAL_GENERATION_MAX_OUTPUT_TOKENS=4096`, `MATERIAL_RETRIEVAL_TOP_K=8`, `MATERIAL_MAX_REPAIR_ATTEMPTS=2`.
- Icons: Phosphor (`@phosphor-icons/react`), never lucide. Colors: use the `@theme` token utilities from `frontend/src/index.css` (`brand`, `hairline`, `surface`, `ink`, `body`, `mute`, `success`/`-soft`, `warning`/`-soft`, `danger`/`-soft`, plus new `review`/`review-soft`).
- Commit after every task (imperative conventional-commit messages, `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>` trailer).

## File Map (what gets created/modified where)

**Backend — new app `backend/collateral_ai/materials/`:**
`apps.py`, `statuses.py`, `models.py`, `worker_trigger.py`, `migrations/` (0001 schema, 0002 seed, 0003 material models), `api/serializers.py`, `api/views.py`, `generation/` (`retrieval.py`, `schema.py`, `prompts.py`, `llm.py`, `validation.py`, `repair.py`, `service.py`), `management/commands/generate_material.py`, `tests/` (`factories.py`, `test_models.py`, `api/test_template_views.py`, `api/test_material_views.py`, `test_worker_trigger.py`, `generation/test_schema.py`, `generation/test_validation.py`, `generation/test_retrieval.py`, `generation/test_llm_and_repair.py`, `generation/test_service.py`).

**Backend — modified:** `config/settings/base.py` (LOCAL_APPS + MATERIAL_* settings), `config/api_router.py` (templates + materials routes), `collateral_ai/documents/gcs.py` (re-export `signed_get_url`), `collateral_ai/documents/api/views.py` (view-url action), `.github/workflows/cd.yml` (generator job).

**Frontend — new:** `src/lib/api/materials.ts` (+`.test.ts`), `src/lib/api/templates.ts` (+`.test.ts`), `src/components/materials-tab.tsx`, `src/components/newsletter-preview.tsx`, `src/components/material-json.tsx`, `src/components/material-sources.tsx`, `src/routes/material-detail.tsx`, `src/routes/template-new.tsx`, `src/components/status-pill.test.ts`.

**Frontend — modified:** `src/lib/api/schema.d.ts` (regenerated), `src/lib/api/documents.ts` (view-url fetcher), `src/components/status-pill.tsx`, `src/index.css` (review tokens), `src/routes/company-detail.tsx` (wire tab), `src/routes/materials.tsx`, `src/routes/create.tsx`, `src/routes/templates.tsx` (replace stubs), `src/router.tsx` (2 new routes).

---

### Task 1: Materials app, statuses, Template model + seed

**Files:**
- Create: `backend/collateral_ai/materials/__init__.py` (empty)
- Create: `backend/collateral_ai/materials/apps.py`
- Create: `backend/collateral_ai/materials/statuses.py`
- Create: `backend/collateral_ai/materials/models.py`
- Create: `backend/collateral_ai/materials/migrations/__init__.py` (empty), `0001_initial.py` (generated), `0002_seed_default_template.py`
- Create: `backend/collateral_ai/materials/tests/__init__.py` (empty), `backend/collateral_ai/materials/tests/factories.py`
- Test: `backend/collateral_ai/materials/tests/test_models.py`
- Modify: `backend/config/settings/base.py` (LOCAL_APPS, around line 85)

**Interfaces:**
- Consumes: nothing new.
- Produces: `Template` model (fields: `name`, `slug` auto-generated snake_case unique, `description`, `constraints: dict`, `image_slots: list`, `theme: dict`, `is_active`, `created_at`, `updated_at`; ordering `["created_at"]`); constants `GenerationStatus.{QUEUED,PROCESSING,COMPLETED,FAILED,CHOICES}`, `ReviewStatus.{PENDING,APPROVED,REJECTED,CHOICES}`, `SourceRole.{SENDER,RECEIVER,CHOICES}`; `TemplateFactory`; seeded row with slug `newsletter_article_v1`.

- [ ] **Step 1: Register the app and write statuses + model**

`backend/collateral_ai/materials/apps.py`:

```python
from django.apps import AppConfig


class MaterialsConfig(AppConfig):
    name = "collateral_ai.materials"
    verbose_name = "Materials"
```

In `backend/config/settings/base.py`, extend `LOCAL_APPS` (keep existing entries, append):

```python
LOCAL_APPS = [
    "collateral_ai.users",
    "collateral_ai.companies",
    "collateral_ai.documents",
    "collateral_ai.materials",
]
```

`backend/collateral_ai/materials/statuses.py`:

```python
class GenerationStatus:
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

    CHOICES = [
        (QUEUED, "Queued"),
        (PROCESSING, "Processing"),
        (COMPLETED, "Completed"),
        (FAILED, "Failed"),
    ]


class ReviewStatus:
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

    CHOICES = [
        (PENDING, "Pending"),
        (APPROVED, "Approved"),
        (REJECTED, "Rejected"),
    ]


class SourceRole:
    SENDER = "sender"
    RECEIVER = "receiver"

    CHOICES = [
        (SENDER, "Sender"),
        (RECEIVER, "Receiver"),
    ]
```

`backend/collateral_ai/materials/models.py`:

```python
from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

DEFAULT_TEMPLATE_SLUG = "newsletter_article_v1"


class Template(models.Model):
    """A publishing layout: the fixed newsletter contract parameterized by constraints.

    There is no schema_json — the structured-output schema is built in code and
    parameterized by `constraints` / `image_slots` (spec §3.1).
    """

    name = models.CharField(_("name"), max_length=255)
    slug = models.SlugField(_("slug"), max_length=255, unique=True, blank=True)
    description = models.TextField(_("description"), blank=True)
    # {headline_max_words, subheadline_max_words, body_section_count,
    #  body_section_max_words, cta_max_words}
    constraints = models.JSONField(_("constraints"), default=dict)
    # [{slot_id, label, spec, source}] — source ∈ sender|receiver|generated_placeholder
    image_slots = models.JSONField(_("image slots"), default=list)
    # {primary_color, accent_color} hex strings
    theme = models.JSONField(_("theme"), default=dict)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("template")
        verbose_name_plural = _("templates")
        # Oldest first: the seeded default is always first, the wizard pre-selects it.
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"{self.name} ({self.slug})"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._unique_slug(self.name)
        super().save(*args, **kwargs)

    @staticmethod
    def _unique_slug(name: str) -> str:
        base = slugify(name).replace("-", "_") or "template"
        slug = base
        n = 2
        while Template.objects.filter(slug=slug).exists():
            slug = f"{base}_{n}"
            n += 1
        return slug
```

- [ ] **Step 2: Generate the schema migration and write the seed migration**

Run:

```bash
docker compose -f docker-compose.local.yml run --rm django python manage.py makemigrations materials
```

Expected: `materials/migrations/0001_initial.py` created with the `Template` model.

`backend/collateral_ai/materials/migrations/0002_seed_default_template.py`:

```python
from django.db import migrations

DEFAULT_CONSTRAINTS = {
    "headline_max_words": 10,
    "subheadline_max_words": 22,
    "body_section_count": 2,
    "body_section_max_words": 80,
    "cta_max_words": 15,
}
DEFAULT_IMAGE_SLOTS = [
    {
        "slot_id": "hero_image",
        "label": "Hero image",
        "spec": "1200×630",
        "source": "generated_placeholder",
    },
    {
        "slot_id": "sender_logo",
        "label": "Sender logo",
        "spec": "SVG/PNG",
        "source": "sender",
    },
]
DEFAULT_THEME = {"primary_color": "#5b5bd6", "accent_color": "#0f172a"}


def seed(apps, schema_editor):
    template = apps.get_model("materials", "Template")
    template.objects.get_or_create(
        slug="newsletter_article_v1",
        defaults={
            "name": "Newsletter Article",
            "description": "Short tailored B2B newsletter article.",
            "constraints": DEFAULT_CONSTRAINTS,
            "image_slots": DEFAULT_IMAGE_SLOTS,
            "theme": DEFAULT_THEME,
        },
    )


def unseed(apps, schema_editor):
    template = apps.get_model("materials", "Template")
    template.objects.filter(slug="newsletter_article_v1").delete()


class Migration(migrations.Migration):
    dependencies = [("materials", "0001_initial")]
    operations = [migrations.RunPython(seed, unseed)]
```

- [ ] **Step 3: Write factory + failing model tests**

`backend/collateral_ai/materials/tests/factories.py`:

```python
from __future__ import annotations

from factory import Faker
from factory import LazyFunction
from factory.django import DjangoModelFactory

from collateral_ai.materials.models import Template


def default_constraints() -> dict:
    return {
        "headline_max_words": 10,
        "subheadline_max_words": 22,
        "body_section_count": 2,
        "body_section_max_words": 80,
        "cta_max_words": 15,
    }


def default_image_slots() -> list[dict]:
    return [
        {
            "slot_id": "hero_image",
            "label": "Hero image",
            "spec": "1200×630",
            "source": "generated_placeholder",
        },
        {
            "slot_id": "sender_logo",
            "label": "Sender logo",
            "spec": "SVG/PNG",
            "source": "sender",
        },
    ]


class TemplateFactory(DjangoModelFactory[Template]):
    name = Faker("catch_phrase")
    constraints = LazyFunction(default_constraints)
    image_slots = LazyFunction(default_image_slots)
    theme = LazyFunction(
        lambda: {"primary_color": "#5b5bd6", "accent_color": "#0f172a"},
    )

    class Meta:
        model = Template
```

`backend/collateral_ai/materials/tests/test_models.py`:

```python
from __future__ import annotations

import pytest

from collateral_ai.materials.models import DEFAULT_TEMPLATE_SLUG
from collateral_ai.materials.models import Template
from collateral_ai.materials.tests.factories import TemplateFactory

pytestmark = pytest.mark.django_db


def test_default_template_is_seeded():
    seeded = Template.objects.get(slug=DEFAULT_TEMPLATE_SLUG)
    assert seeded.name == "Newsletter Article"
    assert seeded.constraints["body_section_count"] == 2
    assert [s["slot_id"] for s in seeded.image_slots] == ["hero_image", "sender_logo"]
    assert seeded.theme == {"primary_color": "#5b5bd6", "accent_color": "#0f172a"}
    assert seeded.is_active


def test_slug_is_generated_snake_case_and_unique():
    a = TemplateFactory(name="Product Spotlight V1")
    b = TemplateFactory(name="Product Spotlight V1")
    assert a.slug == "product_spotlight_v1"
    assert b.slug == "product_spotlight_v1_2"


def test_ordering_is_oldest_first_with_seed_first():
    TemplateFactory(name="Later Template")
    slugs = list(Template.objects.values_list("slug", flat=True))
    assert slugs[0] == DEFAULT_TEMPLATE_SLUG
```

- [ ] **Step 4: Run tests, expect failure before migrations exist / pass after**

Run:

```bash
docker compose -f docker-compose.local.yml run --rm django pytest collateral_ai/materials -q
```

Expected: PASS (3 tests). If `0001_initial.py` was not generated in Step 2, this fails with `no such table` — fix migrations first.

- [ ] **Step 5: Commit**

```bash
git add backend/collateral_ai/materials backend/config/settings/base.py
git commit -m "feat(materials): app scaffold, statuses, Template model + seeded default"
```

---

### Task 2: MarketingMaterial + GenerationSource models

**Files:**
- Modify: `backend/collateral_ai/materials/models.py` (append two models)
- Create: `backend/collateral_ai/materials/migrations/0003_marketingmaterial_generationsource.py` (generated)
- Modify: `backend/collateral_ai/materials/tests/factories.py` (append factories)
- Test: `backend/collateral_ai/materials/tests/test_models.py` (append tests)

**Interfaces:**
- Consumes: `Template`, `GenerationStatus`/`ReviewStatus`/`SourceRole` (Task 1); `companies.Company`, `documents.Document`, `documents.DocumentChunk`.
- Produces: `MarketingMaterial` (all spec §3.2 fields; `related_name` `materials_as_sender`/`materials_as_receiver`; template `related_name="materials"`, PROTECT), `GenerationSource` (spec §3.3; `related_name="sources"`; chunk SET_NULL), `MarketingMaterialFactory`, `GenerationSourceFactory`.

- [ ] **Step 1: Append the models**

Append to `backend/collateral_ai/materials/models.py` (add these imports at the top: `from collateral_ai.materials.statuses import GenerationStatus`, `from collateral_ai.materials.statuses import ReviewStatus`, `from collateral_ai.materials.statuses import SourceRole`):

```python
class MarketingMaterial(models.Model):
    """A generation request + its result, targeted sender → receiver."""

    title = models.CharField(_("title"), max_length=255)
    description = models.TextField(_("description"), blank=True)
    sender_company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="materials_as_sender",
    )
    receiver_company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="materials_as_receiver",
    )
    template = models.ForeignKey(
        Template,
        on_delete=models.PROTECT,
        related_name="materials",
    )
    prompt = models.TextField(_("prompt"))
    tone = models.CharField(_("tone"), max_length=32, default="professional")
    cta_style = models.CharField(_("cta style"), max_length=32, default="soft")
    language = models.CharField(_("language"), max_length=32, default="english")
    generation_status = models.CharField(
        _("generation status"),
        max_length=16,
        choices=GenerationStatus.CHOICES,
        default=GenerationStatus.QUEUED,
    )
    review_status = models.CharField(
        _("review status"),
        max_length=16,
        choices=ReviewStatus.CHOICES,
        default=ReviewStatus.PENDING,
    )
    output_json = models.JSONField(null=True, blank=True)
    validation_result = models.JSONField(null=True, blank=True)
    retrieved_context = models.JSONField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    job_operation_name = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = _("marketing material")
        verbose_name_plural = _("marketing materials")
        ordering = ["-created_at"]
        # FK columns are auto-indexed; generation_status powers list filters.
        indexes = [models.Index(fields=["generation_status"])]

    def __str__(self) -> str:
        return f"{self.title} ({self.generation_status}/{self.review_status})"


class GenerationSource(models.Model):
    """A retrieved chunk the LLM cited — the rows behind the Sources tab."""

    material = models.ForeignKey(
        MarketingMaterial,
        on_delete=models.CASCADE,
        related_name="sources",
    )
    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="generation_sources",
    )
    document = models.ForeignKey(
        "documents.Document",
        on_delete=models.CASCADE,
        related_name="generation_sources",
    )
    # Worker 1 deletes + recreates chunks on document reprocess, so this may dangle;
    # page_number/snippet are denormalized for exactly that reason (spec §3.3).
    chunk = models.ForeignKey(
        "documents.DocumentChunk",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="generation_sources",
    )
    source_role = models.CharField(
        max_length=16,
        choices=SourceRole.CHOICES,
    )
    page_number = models.PositiveIntegerField(null=True, blank=True)
    snippet = models.TextField(blank=True)
    used_fact = models.CharField(max_length=1000, blank=True)
    relevance_score = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("generation source")
        verbose_name_plural = _("generation sources")
        ordering = ["material_id", "id"]

    def __str__(self) -> str:
        return f"material={self.material_id} {self.source_role} doc={self.document_id}"
```

- [ ] **Step 2: Generate migration**

```bash
docker compose -f docker-compose.local.yml run --rm django python manage.py makemigrations materials
```

Expected: `0003_marketingmaterial_generationsource.py` created.

- [ ] **Step 3: Append factories**

Append to `backend/collateral_ai/materials/tests/factories.py` (add imports: `from factory import SubFactory`, `from collateral_ai.companies.tests.factories import CompanyFactory`, `from collateral_ai.documents.tests.factories import DocumentFactory`, `from collateral_ai.materials.models import GenerationSource`, `from collateral_ai.materials.models import MarketingMaterial`, `from collateral_ai.materials.statuses import SourceRole`):

```python
class MarketingMaterialFactory(DjangoModelFactory[MarketingMaterial]):
    title = Faker("sentence", nb_words=4)
    sender_company = SubFactory(CompanyFactory)
    receiver_company = SubFactory(CompanyFactory)
    template = SubFactory(TemplateFactory)
    prompt = Faker("paragraph")

    class Meta:
        model = MarketingMaterial


class GenerationSourceFactory(DjangoModelFactory[GenerationSource]):
    material = SubFactory(MarketingMaterialFactory)
    document = SubFactory(DocumentFactory)
    source_role = SourceRole.SENDER
    page_number = 1
    snippet = "quoted snippet"
    used_fact = "a fact that was used"
    relevance_score = 0.12

    class Meta:
        model = GenerationSource

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        # company defaults to the document's company when not given
        kwargs.setdefault("company", kwargs["document"].company)
        return super()._create(model_class, *args, **kwargs)
```

- [ ] **Step 4: Append failing tests, run, implement fixes if needed**

Append to `backend/collateral_ai/materials/tests/test_models.py` (add imports: `from django.db.models import ProtectedError`, `from collateral_ai.materials.statuses import GenerationStatus`, `from collateral_ai.materials.statuses import ReviewStatus`, `from collateral_ai.materials.tests.factories import GenerationSourceFactory`, `from collateral_ai.materials.tests.factories import MarketingMaterialFactory`):

```python
def test_material_defaults():
    material = MarketingMaterialFactory()
    assert material.generation_status == GenerationStatus.QUEUED
    assert material.review_status == ReviewStatus.PENDING
    assert material.tone == "professional"
    assert material.cta_style == "soft"
    assert material.language == "english"
    assert material.output_json is None
    assert material.completed_at is None


def test_template_delete_is_protected_by_materials():
    material = MarketingMaterialFactory()
    with pytest.raises(ProtectedError):
        material.template.delete()


def test_source_chunk_nulls_on_chunk_delete():
    from collateral_ai.documents.tests.factories import DocumentChunkFactory

    chunk = DocumentChunkFactory()
    source = GenerationSourceFactory(
        document=chunk.document,
        chunk=chunk,
        page_number=chunk.page_number,
    )
    chunk.delete()
    source.refresh_from_db()
    assert source.chunk is None
    assert source.page_number == 1  # denormalized value survives


def test_material_delete_cascades_sources():
    source = GenerationSourceFactory()
    source.material.delete()
    from collateral_ai.materials.models import GenerationSource

    assert not GenerationSource.objects.filter(pk=source.pk).exists()
```

Run:

```bash
docker compose -f docker-compose.local.yml run --rm django pytest collateral_ai/materials -q
```

Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/collateral_ai/materials
git commit -m "feat(materials): MarketingMaterial + GenerationSource models"
```

---

### Task 3: Template API

**Files:**
- Create: `backend/collateral_ai/materials/api/__init__.py` (empty)
- Create: `backend/collateral_ai/materials/api/serializers.py`
- Create: `backend/collateral_ai/materials/api/views.py`
- Modify: `backend/config/api_router.py`
- Create: `backend/collateral_ai/materials/tests/api/__init__.py` (empty)
- Test: `backend/collateral_ai/materials/tests/api/test_template_views.py`

**Interfaces:**
- Consumes: `Template`, `TemplateFactory` (Task 1).
- Produces: `TemplateSerializer` (spectacular schema name `Template`; fields `id, name, slug, description, constraints, image_slots, theme, is_active, created_at`; read-only `id, slug, is_active, created_at`), `TemplateViewSet` at `/api/templates/` (list/retrieve/create), module constants `CONSTRAINT_BOUNDS`, `SLOT_SOURCES`, `HEX_COLOR_RE` reused by later tasks.

- [ ] **Step 1: Write failing API tests**

`backend/collateral_ai/materials/tests/api/test_template_views.py`:

```python
from __future__ import annotations

from http import HTTPStatus

import pytest
from rest_framework.test import APIClient

from collateral_ai.materials.models import DEFAULT_TEMPLATE_SLUG
from collateral_ai.materials.models import Template
from collateral_ai.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db

URL = "/api/templates/"


@pytest.fixture
def auth_client() -> APIClient:
    client = APIClient()
    client.force_authenticate(user=UserFactory())
    return client


def valid_body() -> dict:
    return {
        "name": "Product Spotlight",
        "description": "One-pager",
        "constraints": {
            "headline_max_words": 8,
            "subheadline_max_words": 20,
            "body_section_count": 3,
            "body_section_max_words": 90,
            "cta_max_words": 12,
        },
        "image_slots": [
            {
                "slot_id": "hero_image",
                "label": "Hero image",
                "spec": "1200×630",
                "source": "generated_placeholder",
            },
        ],
        "theme": {"primary_color": "#112233", "accent_color": "#abcdef"},
    }


def test_list_requires_auth():
    assert APIClient().get(URL).status_code == HTTPStatus.FORBIDDEN


def test_list_returns_seed_first(auth_client):
    resp = auth_client.get(URL)
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()[0]["slug"] == DEFAULT_TEMPLATE_SLUG


def test_create_generates_slug(auth_client):
    resp = auth_client.post(URL, valid_body(), format="json")
    assert resp.status_code == HTTPStatus.CREATED
    assert resp.json()["slug"] == "product_spotlight"
    assert Template.objects.filter(slug="product_spotlight").exists()


def test_create_uniquifies_slug(auth_client):
    auth_client.post(URL, valid_body(), format="json")
    resp = auth_client.post(URL, valid_body(), format="json")
    assert resp.status_code == HTTPStatus.CREATED
    assert resp.json()["slug"] == "product_spotlight_2"


@pytest.mark.parametrize(
    ("patch", "expected_error_field"),
    [
        ({"constraints": {"headline_max_words": 8}}, "constraints"),  # missing keys
        (
            {
                "constraints": {
                    "headline_max_words": 8,
                    "subheadline_max_words": 20,
                    "body_section_count": 40,  # > 10
                    "body_section_max_words": 90,
                    "cta_max_words": 12,
                },
            },
            "constraints",
        ),
        (
            {
                "image_slots": [
                    {"slot_id": "Bad Id!", "label": "x", "spec": "", "source": "sender"},
                ],
            },
            "image_slots",
        ),
        (
            {
                "image_slots": [
                    {"slot_id": "a", "label": "x", "spec": "", "source": "sender"},
                    {"slot_id": "a", "label": "y", "spec": "", "source": "sender"},
                ],
            },
            "image_slots",
        ),
        ({"theme": {"primary_color": "blue", "accent_color": "#abcdef"}}, "theme"),
    ],
)
def test_create_validation_errors(auth_client, patch, expected_error_field):
    body = {**valid_body(), **patch}
    resp = auth_client.post(URL, body, format="json")
    assert resp.status_code == HTTPStatus.BAD_REQUEST
    assert expected_error_field in resp.json()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
docker compose -f docker-compose.local.yml run --rm django pytest collateral_ai/materials/tests/api -q
```

Expected: FAIL — 404s (`/api/templates/` not routed yet).

- [ ] **Step 3: Implement serializer, viewset, route**

`backend/collateral_ai/materials/api/serializers.py`:

```python
from __future__ import annotations

import re

from rest_framework import serializers

from collateral_ai.materials.models import Template

# (min, max) for each required constraint key — spec §5.1.
CONSTRAINT_BOUNDS: dict[str, tuple[int, int]] = {
    "headline_max_words": (1, 60),
    "subheadline_max_words": (1, 60),
    "body_section_count": (1, 10),
    "body_section_max_words": (1, 300),
    "cta_max_words": (1, 60),
}
SLOT_SOURCES = {"sender", "receiver", "generated_placeholder"}
SLOT_ID_RE = re.compile(r"^[a-z0-9_]+$")
HEX_COLOR_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
MAX_IMAGE_SLOTS = 8


class TemplateSerializer(serializers.ModelSerializer[Template]):
    class Meta:
        model = Template
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "constraints",
            "image_slots",
            "theme",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["id", "slug", "is_active", "created_at"]

    def validate_constraints(self, value: dict) -> dict:
        if not isinstance(value, dict):
            msg = "constraints must be an object."
            raise serializers.ValidationError(msg)
        for key, (lo, hi) in CONSTRAINT_BOUNDS.items():
            v = value.get(key)
            if not isinstance(v, int) or isinstance(v, bool) or not lo <= v <= hi:
                msg = f"constraints.{key} must be an integer between {lo} and {hi}."
                raise serializers.ValidationError(msg)
        extra = set(value) - set(CONSTRAINT_BOUNDS)
        if extra:
            msg = f"Unknown constraint keys: {sorted(extra)}"
            raise serializers.ValidationError(msg)
        return value

    def validate_image_slots(self, value: list) -> list:
        if not isinstance(value, list) or len(value) > MAX_IMAGE_SLOTS:
            msg = f"image_slots must be a list of at most {MAX_IMAGE_SLOTS} slots."
            raise serializers.ValidationError(msg)
        seen: set[str] = set()
        for slot in value:
            if not isinstance(slot, dict):
                msg = "Each image slot must be an object."
                raise serializers.ValidationError(msg)
            slot_id = slot.get("slot_id", "")
            if not isinstance(slot_id, str) or not SLOT_ID_RE.match(slot_id):
                msg = f"Invalid slot_id: {slot_id!r} (lowercase letters, digits, _)."
                raise serializers.ValidationError(msg)
            if slot_id in seen:
                msg = f"Duplicate slot_id: {slot_id}"
                raise serializers.ValidationError(msg)
            seen.add(slot_id)
            if slot.get("source") not in SLOT_SOURCES:
                msg = f"slot {slot_id}: source must be one of {sorted(SLOT_SOURCES)}."
                raise serializers.ValidationError(msg)
            if not isinstance(slot.get("label", ""), str) or not slot.get("label"):
                msg = f"slot {slot_id}: label is required."
                raise serializers.ValidationError(msg)
            if not isinstance(slot.get("spec", ""), str):
                msg = f"slot {slot_id}: spec must be a string."
                raise serializers.ValidationError(msg)
        return value

    def validate_theme(self, value: dict) -> dict:
        if not isinstance(value, dict):
            msg = "theme must be an object."
            raise serializers.ValidationError(msg)
        for key in ("primary_color", "accent_color"):
            if not HEX_COLOR_RE.match(str(value.get(key, ""))):
                msg = f"theme.{key} must be a hex color like #5b5bd6."
                raise serializers.ValidationError(msg)
        return value
```

`backend/collateral_ai/materials/api/views.py`:

```python
from rest_framework.mixins import CreateModelMixin
from rest_framework.mixins import ListModelMixin
from rest_framework.mixins import RetrieveModelMixin
from rest_framework.viewsets import GenericViewSet

from collateral_ai.materials.models import Template

from .serializers import TemplateSerializer


class TemplateViewSet(
    ListModelMixin,
    RetrieveModelMixin,
    CreateModelMixin,
    GenericViewSet,
):
    """Templates are create-only in MVP: no update/delete (spec §5.1)."""

    serializer_class = TemplateSerializer
    queryset = Template.objects.all()
```

In `backend/config/api_router.py`, add the import and registration (after the companies registration):

```python
from collateral_ai.materials.api.views import TemplateViewSet

router.register("templates", TemplateViewSet, basename="template")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
docker compose -f docker-compose.local.yml run --rm django pytest collateral_ai/materials -q
```

Expected: PASS (all task 1–3 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/collateral_ai/materials backend/config/api_router.py
git commit -m "feat(materials): template API (list/retrieve/create with constraint validation)"
```

---

### Task 4: Document view-url endpoint

**Files:**
- Modify: `backend/collateral_ai/documents/gcs.py` (re-export `signed_get_url`)
- Modify: `backend/collateral_ai/documents/api/views.py` (new action)
- Test: `backend/collateral_ai/documents/tests/api/test_views.py` (append)

**Interfaces:**
- Consumes: `collateral_ai.companies.gcs.signed_get_url(object_path) -> str` (exists).
- Produces: `GET /api/companies/{company_pk}/documents/{id}/view-url/` → `{"url": "<signed GET url>"}`; 503 when GCS unconfigured, 404 when `storage_path` is blank. Frontend Sources tab and Documents tab both use it.

- [ ] **Step 1: Write failing tests**

Append to `backend/collateral_ai/documents/tests/api/test_views.py`:

```python
def test_view_url_returns_signed_get_url(auth_client):
    doc = DocumentFactory(storage_path="media/companies/1/documents/1/doc.pdf")
    with (
        mock.patch(
            "collateral_ai.documents.api.views.gcs.is_configured",
            return_value=True,
        ),
        mock.patch(
            "collateral_ai.documents.api.views.gcs.signed_get_url",
            return_value="https://signed-get",
        ),
    ):
        resp = auth_client.get(f"{docs_url(doc.company_id)}{doc.pk}/view-url/")
    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == {"url": "https://signed-get"}


def test_view_url_503_when_unconfigured(auth_client):
    doc = DocumentFactory()
    with mock.patch(
        "collateral_ai.documents.api.views.gcs.is_configured",
        return_value=False,
    ):
        resp = auth_client.get(f"{docs_url(doc.company_id)}{doc.pk}/view-url/")
    assert resp.status_code == HTTPStatus.SERVICE_UNAVAILABLE


def test_view_url_404_when_no_storage_path(auth_client):
    doc = DocumentFactory(storage_path="")
    with mock.patch(
        "collateral_ai.documents.api.views.gcs.is_configured",
        return_value=True,
    ):
        resp = auth_client.get(f"{docs_url(doc.company_id)}{doc.pk}/view-url/")
    assert resp.status_code == HTTPStatus.NOT_FOUND
```

- [ ] **Step 2: Run to verify failure**

```bash
docker compose -f docker-compose.local.yml run --rm django pytest collateral_ai/documents/tests/api -q
```

Expected: FAIL — 404 (route doesn't exist), and `signed_get_url` missing from `documents.gcs`.

- [ ] **Step 3: Implement**

In `backend/collateral_ai/documents/gcs.py`, add to the re-export block:

```python
from collateral_ai.companies.gcs import signed_get_url  # noqa: F401  (re-exported)
```

In `backend/collateral_ai/documents/api/views.py`, append this action to `DocumentViewSet` (after `complete`):

```python
    @extend_schema(
        request=None,
        responses=inline_serializer(
            name="DocumentViewUrl",
            fields={"url": serializers.URLField()},
        ),
    )
    @action(detail=True, methods=["get"], url_path="view-url")
    def view_url(self, request, pk=None, company_pk=None):
        """Signed GET URL so the browser can open the stored PDF (spec §5.3)."""
        doc = self.get_object()
        if not gcs.is_configured():
            return Response(
                {"detail": "Document viewing is not configured in this environment."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        if not doc.storage_path:
            return Response(
                {"detail": "Document has no stored file."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response({"url": gcs.signed_get_url(doc.storage_path)})
```

- [ ] **Step 4: Run to verify pass**

```bash
docker compose -f docker-compose.local.yml run --rm django pytest collateral_ai/documents -q
```

Expected: PASS (all documents tests, incl. 3 new).

- [ ] **Step 5: Commit**

```bash
git add backend/collateral_ai/documents
git commit -m "feat(documents): signed view-url endpoint for opening stored PDFs"
```

---

### Task 5: Material API — create/list/detail + worker trigger + settings

**Files:**
- Modify: `backend/config/settings/base.py` (append MATERIAL_* block)
- Create: `backend/collateral_ai/materials/worker_trigger.py`
- Modify: `backend/collateral_ai/materials/api/serializers.py` (append material serializers)
- Modify: `backend/collateral_ai/materials/api/views.py` (append `MaterialViewSet`)
- Modify: `backend/config/api_router.py` (register materials)
- Test: `backend/collateral_ai/materials/tests/test_worker_trigger.py`, `backend/collateral_ai/materials/tests/api/test_material_views.py`

**Interfaces:**
- Consumes: models + factories (Tasks 1–2), `TemplateSerializer` (Task 3), `DocumentStatus.PROCESSED`, `CompanyFactory`, `DocumentFactory`.
- Produces:
  - `trigger_generation(material) -> str` (operation name, `""` inline) in `materials/worker_trigger.py`.
  - Serializers (spectacular names): `CompanySummary` `{id, name, logo_url}`, `SourceDocument` `{id, file_name, company}`, `GenerationSource` (nested `document`), `MaterialList`, `MaterialDetail`, `MaterialCreate`, `MaterialUpdate`.
  - `MaterialViewSet` at `/api/materials/` — GET list (filters `company`/`sender`/`receiver`/`generation_status`/`review_status`/`search`), POST create (validations + trigger + 201 detail payload), GET detail. (PATCH/regenerate/DELETE arrive in Task 6 — the viewset created here already includes the mixins so Task 6 only adds serializer rules + the action.)
  - Settings: the seven `MATERIAL_*` values from Global Constraints.

- [ ] **Step 1: Add settings**

Append to `backend/config/settings/base.py` after the `DOCUMENT_PROCESSOR_REGION` line:

```python
# Material generation (worker 2)
# ------------------------------------------------------------------------------
# When set (prod), material create/regenerate executes this Cloud Run Job instead
# of running the worker inline.
MATERIAL_GENERATOR_JOB = env("MATERIAL_GENERATOR_JOB", default="")
MATERIAL_GENERATOR_REGION = env("MATERIAL_GENERATOR_REGION", default="us-central1")
MATERIAL_LLM_MODEL = env("MATERIAL_LLM_MODEL", default="gemini-2.5-flash")
MATERIAL_GENERATION_TEMPERATURE = env.float(
    "MATERIAL_GENERATION_TEMPERATURE",
    default=0.2,
)
MATERIAL_GENERATION_MAX_OUTPUT_TOKENS = env.int(
    "MATERIAL_GENERATION_MAX_OUTPUT_TOKENS",
    default=4096,
)
MATERIAL_RETRIEVAL_TOP_K = env.int("MATERIAL_RETRIEVAL_TOP_K", default=8)
MATERIAL_MAX_REPAIR_ATTEMPTS = env.int("MATERIAL_MAX_REPAIR_ATTEMPTS", default=2)
```

- [ ] **Step 2: Write the trigger wrapper + its failing tests**

`backend/collateral_ai/materials/worker_trigger.py`:

```python
"""Trigger material generation: inline command locally, Cloud Run Job in prod."""

from __future__ import annotations

from django.conf import settings
from django.core.management import call_command


def trigger_generation(material) -> str:
    """Dispatch worker 2 for `material`. Returns the Cloud Run operation name ('' inline).

    Unlike documents' trigger, callers must NOT suppress exceptions from this
    function — the view marks the material failed instead (spec §5.5).
    """
    job = getattr(settings, "MATERIAL_GENERATOR_JOB", "")
    if not job:
        # Local/dev/test: run the management command inline (synchronous).
        call_command("generate_material", material_id=material.pk)
        return ""

    from google.cloud import run_v2

    name = (
        f"projects/{settings.GOOGLE_CLOUD_PROJECT}"
        f"/locations/{settings.MATERIAL_GENERATOR_REGION}/jobs/{job}"
    )
    overrides = run_v2.RunJobRequest.Overrides(
        container_overrides=[
            run_v2.RunJobRequest.Overrides.ContainerOverride(
                args=[
                    "manage.py",
                    "generate_material",
                    "--material-id",
                    str(material.pk),
                ],
            ),
        ],
    )
    operation = run_v2.JobsClient().run_job(
        request=run_v2.RunJobRequest(name=name, overrides=overrides),
    )
    return getattr(getattr(operation, "operation", None), "name", "") or ""
```

`backend/collateral_ai/materials/tests/test_worker_trigger.py`:

```python
from __future__ import annotations

from unittest import mock

import pytest

from collateral_ai.materials.tests.factories import MarketingMaterialFactory
from collateral_ai.materials.worker_trigger import trigger_generation

pytestmark = pytest.mark.django_db


def test_inline_mode_runs_command(settings):
    settings.MATERIAL_GENERATOR_JOB = ""
    material = MarketingMaterialFactory()
    with mock.patch(
        "collateral_ai.materials.worker_trigger.call_command",
    ) as call_command:
        result = trigger_generation(material)
    call_command.assert_called_once_with("generate_material", material_id=material.pk)
    assert result == ""


def test_job_mode_runs_cloud_run_job(settings):
    settings.MATERIAL_GENERATOR_JOB = "matgen-job"
    settings.MATERIAL_GENERATOR_REGION = "us-central1"
    settings.GOOGLE_CLOUD_PROJECT = "proj-123"
    material = MarketingMaterialFactory()
    with mock.patch("google.cloud.run_v2.JobsClient") as jobs_client:
        operation = jobs_client.return_value.run_job.return_value
        operation.operation.name = "operations/abc"
        result = trigger_generation(material)
    request = jobs_client.return_value.run_job.call_args.kwargs["request"]
    assert request.name == "projects/proj-123/locations/us-central1/jobs/matgen-job"
    args = list(request.overrides.container_overrides[0].args)
    assert args == ["manage.py", "generate_material", "--material-id", str(material.pk)]
    assert result == "operations/abc"
```

Run:

```bash
docker compose -f docker-compose.local.yml run --rm django pytest collateral_ai/materials/tests/test_worker_trigger.py -q
```

Expected: PASS (2 tests) — the wrapper exists before the command does; inline mode is only exercised via the mock here.

- [ ] **Step 3: Write failing API tests for create/list/detail**

`backend/collateral_ai/materials/tests/api/test_material_views.py`:

```python
from __future__ import annotations

from http import HTTPStatus
from unittest import mock

import pytest
from rest_framework.test import APIClient

from collateral_ai.companies.tests.factories import CompanyFactory
from collateral_ai.documents.statuses import DocumentStatus
from collateral_ai.documents.tests.factories import DocumentFactory
from collateral_ai.materials.models import MarketingMaterial
from collateral_ai.materials.statuses import GenerationStatus
from collateral_ai.materials.statuses import ReviewStatus
from collateral_ai.materials.tests.factories import MarketingMaterialFactory
from collateral_ai.materials.tests.factories import TemplateFactory
from collateral_ai.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db

URL = "/api/materials/"
TRIGGER = "collateral_ai.materials.api.views.trigger_generation"


@pytest.fixture
def auth_client() -> APIClient:
    client = APIClient()
    client.force_authenticate(user=UserFactory())
    return client


def companies_with_docs() -> tuple:
    sender, receiver = CompanyFactory(), CompanyFactory()
    DocumentFactory(company=sender, status=DocumentStatus.PROCESSED)
    DocumentFactory(company=receiver, status=DocumentStatus.PROCESSED)
    return sender, receiver


def create_body(sender, receiver, template) -> dict:
    return {
        "title": "AI for Smarter Logistics",
        "sender_company": sender.pk,
        "receiver_company": receiver.pk,
        "template": template.pk,
        "prompt": "Pitch our AI to improve warehouse efficiency.",
    }


def test_list_requires_auth():
    assert APIClient().get(URL).status_code == HTTPStatus.FORBIDDEN


def test_create_queues_and_triggers(auth_client):
    sender, receiver = companies_with_docs()
    template = TemplateFactory()
    with mock.patch(TRIGGER, return_value="operations/abc") as trigger:
        resp = auth_client.post(
            URL,
            create_body(sender, receiver, template),
            format="json",
        )
    assert resp.status_code == HTTPStatus.CREATED
    trigger.assert_called_once()
    body = resp.json()
    assert body["generation_status"] == GenerationStatus.QUEUED
    assert body["review_status"] == ReviewStatus.PENDING
    assert body["sender_company"]["id"] == sender.pk
    assert body["template"]["slug"] == template.slug
    material = MarketingMaterial.objects.get(pk=body["id"])
    assert material.job_operation_name == "operations/abc"


def test_create_trigger_failure_marks_failed_but_returns_201(auth_client):
    sender, receiver = companies_with_docs()
    template = TemplateFactory()
    with mock.patch(TRIGGER, side_effect=RuntimeError("job boom")):
        resp = auth_client.post(
            URL,
            create_body(sender, receiver, template),
            format="json",
        )
    assert resp.status_code == HTTPStatus.CREATED
    body = resp.json()
    assert body["generation_status"] == GenerationStatus.FAILED
    assert "job boom" in body["error_message"]


def test_create_rejects_same_sender_and_receiver(auth_client):
    sender, _ = companies_with_docs()
    template = TemplateFactory()
    body = create_body(sender, sender, template)
    with mock.patch(TRIGGER) as trigger:
        resp = auth_client.post(URL, body, format="json")
    assert resp.status_code == HTTPStatus.BAD_REQUEST
    trigger.assert_not_called()


def test_create_rejects_company_without_processed_docs(auth_client):
    sender = CompanyFactory()  # no documents
    receiver = CompanyFactory()
    DocumentFactory(company=receiver, status=DocumentStatus.PROCESSED)
    template = TemplateFactory()
    with mock.patch(TRIGGER):
        resp = auth_client.post(
            URL,
            create_body(sender, receiver, template),
            format="json",
        )
    assert resp.status_code == HTTPStatus.BAD_REQUEST
    assert "sender_company" in resp.json()


def test_create_rejects_inactive_template(auth_client):
    sender, receiver = companies_with_docs()
    template = TemplateFactory(is_active=False)
    with mock.patch(TRIGGER):
        resp = auth_client.post(
            URL,
            create_body(sender, receiver, template),
            format="json",
        )
    assert resp.status_code == HTTPStatus.BAD_REQUEST


def test_list_company_filter_matches_sender_or_receiver(auth_client):
    company = CompanyFactory()
    as_sender = MarketingMaterialFactory(sender_company=company)
    as_receiver = MarketingMaterialFactory(receiver_company=company)
    MarketingMaterialFactory()  # unrelated
    resp = auth_client.get(URL, {"company": company.pk})
    ids = {m["id"] for m in resp.json()}
    assert ids == {as_sender.pk, as_receiver.pk}


def test_list_status_and_search_filters(auth_client):
    done = MarketingMaterialFactory(
        title="Warehouse AI",
        generation_status=GenerationStatus.COMPLETED,
    )
    MarketingMaterialFactory(title="Other", generation_status=GenerationStatus.FAILED)
    resp = auth_client.get(URL, {"generation_status": "completed"})
    assert [m["id"] for m in resp.json()] == [done.pk]
    resp = auth_client.get(URL, {"search": "warehouse"})
    assert [m["id"] for m in resp.json()] == [done.pk]


def test_detail_includes_template_sources_and_companies(auth_client):
    from collateral_ai.materials.tests.factories import GenerationSourceFactory

    material = MarketingMaterialFactory()
    source = GenerationSourceFactory(material=material)
    resp = auth_client.get(f"{URL}{material.pk}/")
    assert resp.status_code == HTTPStatus.OK
    body = resp.json()
    assert body["template"]["constraints"]["body_section_count"] == 2
    assert body["sender_company"]["name"] == material.sender_company.name
    assert body["sources"][0]["document"]["file_name"] == source.document.file_name
```

Run:

```bash
docker compose -f docker-compose.local.yml run --rm django pytest collateral_ai/materials/tests/api/test_material_views.py -q
```

Expected: FAIL — 404s (no route).

- [ ] **Step 4: Implement serializers**

Append to `backend/collateral_ai/materials/api/serializers.py` (add imports at top: `from collateral_ai.companies import gcs as companies_gcs`, `from collateral_ai.companies.models import Company`, `from collateral_ai.documents.models import Document`, `from collateral_ai.documents.statuses import DocumentStatus`, `from collateral_ai.materials.models import GenerationSource`, `from collateral_ai.materials.models import MarketingMaterial`):

```python
class CompanySummarySerializer(serializers.ModelSerializer[Company]):
    logo_url = serializers.SerializerMethodField()

    class Meta:
        model = Company
        fields = ["id", "name", "logo_url"]

    def get_logo_url(self, obj: Company) -> str | None:
        if obj.logo and companies_gcs.is_configured():
            return companies_gcs.signed_get_url(obj.logo)
        return None


class SourceDocumentSerializer(serializers.ModelSerializer[Document]):
    class Meta:
        model = Document
        fields = ["id", "file_name", "company"]


class GenerationSourceSerializer(serializers.ModelSerializer[GenerationSource]):
    document = SourceDocumentSerializer(read_only=True)

    class Meta:
        model = GenerationSource
        fields = [
            "id",
            "source_role",
            "page_number",
            "snippet",
            "used_fact",
            "relevance_score",
            "document",
        ]


class MaterialListSerializer(serializers.ModelSerializer[MarketingMaterial]):
    sender_company = CompanySummarySerializer(read_only=True)
    receiver_company = CompanySummarySerializer(read_only=True)
    template_slug = serializers.CharField(source="template.slug", read_only=True)

    class Meta:
        model = MarketingMaterial
        fields = [
            "id",
            "title",
            "sender_company",
            "receiver_company",
            "template_slug",
            "generation_status",
            "review_status",
            "created_at",
            "completed_at",
        ]


class MaterialDetailSerializer(MaterialListSerializer):
    template = TemplateSerializer(read_only=True)
    sources = GenerationSourceSerializer(many=True, read_only=True)

    class Meta(MaterialListSerializer.Meta):
        fields = [
            *MaterialListSerializer.Meta.fields,
            "description",
            "prompt",
            "tone",
            "cta_style",
            "language",
            "template",
            "output_json",
            "validation_result",
            "error_message",
            "updated_at",
            "sources",
        ]


class MaterialCreateSerializer(serializers.ModelSerializer[MarketingMaterial]):
    class Meta:
        model = MarketingMaterial
        fields = [
            "id",
            "title",
            "description",
            "sender_company",
            "receiver_company",
            "template",
            "prompt",
            "tone",
            "cta_style",
            "language",
        ]
        read_only_fields = ["id"]

    def validate(self, attrs: dict) -> dict:
        sender = attrs["sender_company"]
        receiver = attrs["receiver_company"]
        if sender == receiver:
            msg = "Sender and receiver must be different companies."
            raise serializers.ValidationError({"receiver_company": msg})
        if not attrs["template"].is_active:
            msg = "This template is not active."
            raise serializers.ValidationError({"template": msg})
        for field, company in (
            ("sender_company", sender),
            ("receiver_company", receiver),
        ):
            has_docs = Document.objects.filter(
                company=company,
                status=DocumentStatus.PROCESSED,
            ).exists()
            if not has_docs:
                msg = (
                    f"{company.name} has no processed documents — upload and "
                    "process documents before generating."
                )
                raise serializers.ValidationError({field: msg})
        return attrs


class MaterialUpdateSerializer(serializers.ModelSerializer[MarketingMaterial]):
    class Meta:
        model = MarketingMaterial
        fields = ["id", "title", "description", "prompt", "review_status"]
        read_only_fields = ["id"]

    def validate_review_status(self, value: str) -> str:
        from collateral_ai.materials.statuses import GenerationStatus

        if (
            self.instance is not None
            and self.instance.generation_status != GenerationStatus.COMPLETED
        ):
            msg = "Review status can only change once generation is completed."
            raise serializers.ValidationError(msg)
        return value
```

- [ ] **Step 5: Implement the viewset + route**

Replace the imports at the top of `backend/collateral_ai/materials/api/views.py` and extend it with `MaterialViewSet` (final file shape — `TemplateViewSet` from Task 3 stays as-is):

```python
import datetime

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
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

from collateral_ai.materials.models import MarketingMaterial
from collateral_ai.materials.models import Template
from collateral_ai.materials.statuses import GenerationStatus
from collateral_ai.materials.statuses import ReviewStatus
from collateral_ai.materials.worker_trigger import trigger_generation

from .serializers import MaterialCreateSerializer
from .serializers import MaterialDetailSerializer
from .serializers import MaterialListSerializer
from .serializers import MaterialUpdateSerializer
from .serializers import TemplateSerializer

# A queued/processing row older than this is considered stranded (crashed job)
# and may be regenerated (spec §5.2). Comfortably above the 600s job timeout.
STALE_AFTER = datetime.timedelta(minutes=15)

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
```

(`TemplateViewSet` unchanged, then:)

```python
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
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        material = serializer.save()
        self._dispatch(material)
        material.refresh_from_db()
        return Response(
            MaterialDetailSerializer(material, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    def _dispatch(self, material) -> None:
        """Trigger the worker inside its own savepoint (spec §5.5).

        The request runs under ATOMIC_REQUESTS; the inner atomic() means a
        failing trigger (or a poisoned inline run) can't take the created row
        down with it — we mark the material failed and still return 201.
        """
        try:
            with transaction.atomic():
                operation_name = trigger_generation(material)
        except Exception as exc:  # noqa: BLE001 — any trigger failure → failed row
            MarketingMaterial.objects.filter(pk=material.pk).update(
                generation_status=GenerationStatus.FAILED,
                error_message=str(exc),
                updated_at=timezone.now(),
            )
        else:
            if operation_name:
                MarketingMaterial.objects.filter(pk=material.pk).update(
                    job_operation_name=operation_name,
                    updated_at=timezone.now(),
                )
```

Register in `backend/config/api_router.py` (next to the templates registration):

```python
from collateral_ai.materials.api.views import MaterialViewSet

router.register("materials", MaterialViewSet, basename="material")
```

- [ ] **Step 6: Run tests to verify pass**

```bash
docker compose -f docker-compose.local.yml run --rm django pytest collateral_ai/materials -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/collateral_ai/materials backend/config
git commit -m "feat(materials): material API (create/list/detail), worker trigger, settings"
```

---

### Task 6: Material API — PATCH rules, regenerate, delete

**Files:**
- Modify: `backend/collateral_ai/materials/api/views.py` (regenerate action)
- Test: `backend/collateral_ai/materials/tests/api/test_material_views.py` (append)

**Interfaces:**
- Consumes: `MaterialViewSet`, `MaterialUpdateSerializer`, `STALE_AFTER`, `trigger_generation` (Task 5).
- Produces: `POST /api/materials/{id}/regenerate/` (202 detail payload | 409 while fresh-active), PATCH review-status gating verified, DELETE cascade verified.

- [ ] **Step 1: Write failing tests**

Append to `backend/collateral_ai/materials/tests/api/test_material_views.py`:

```python
def test_patch_review_status_requires_completed(auth_client):
    material = MarketingMaterialFactory(generation_status=GenerationStatus.QUEUED)
    resp = auth_client.patch(
        f"{URL}{material.pk}/",
        {"review_status": ReviewStatus.APPROVED},
        format="json",
    )
    assert resp.status_code == HTTPStatus.BAD_REQUEST


def test_patch_approves_completed_material(auth_client):
    material = MarketingMaterialFactory(generation_status=GenerationStatus.COMPLETED)
    resp = auth_client.patch(
        f"{URL}{material.pk}/",
        {"review_status": ReviewStatus.APPROVED},
        format="json",
    )
    assert resp.status_code == HTTPStatus.OK
    material.refresh_from_db()
    assert material.review_status == ReviewStatus.APPROVED


def test_patch_prompt_does_not_regenerate(auth_client):
    material = MarketingMaterialFactory(generation_status=GenerationStatus.COMPLETED)
    with mock.patch(TRIGGER) as trigger:
        resp = auth_client.patch(
            f"{URL}{material.pk}/",
            {"prompt": "new prompt"},
            format="json",
        )
    assert resp.status_code == HTTPStatus.OK
    trigger.assert_not_called()


def test_regenerate_conflicts_while_fresh_processing(auth_client):
    material = MarketingMaterialFactory(generation_status=GenerationStatus.PROCESSING)
    with mock.patch(TRIGGER) as trigger:
        resp = auth_client.post(f"{URL}{material.pk}/regenerate/")
    assert resp.status_code == HTTPStatus.CONFLICT
    trigger.assert_not_called()


def test_regenerate_allowed_when_processing_is_stale(auth_client):
    import datetime

    from django.utils import timezone

    material = MarketingMaterialFactory(generation_status=GenerationStatus.PROCESSING)
    MarketingMaterial.objects.filter(pk=material.pk).update(
        updated_at=timezone.now() - datetime.timedelta(minutes=16),
    )
    with mock.patch(TRIGGER, return_value="") as trigger:
        resp = auth_client.post(f"{URL}{material.pk}/regenerate/")
    assert resp.status_code == HTTPStatus.ACCEPTED
    trigger.assert_called_once()


def test_regenerate_resets_output_review_and_sources(auth_client):
    from collateral_ai.materials.models import GenerationSource
    from collateral_ai.materials.tests.factories import GenerationSourceFactory

    material = MarketingMaterialFactory(
        generation_status=GenerationStatus.COMPLETED,
        review_status=ReviewStatus.APPROVED,
        output_json={"template_id": "x"},
        error_message="old",
    )
    GenerationSourceFactory(material=material)
    with mock.patch(TRIGGER, return_value=""):
        resp = auth_client.post(f"{URL}{material.pk}/regenerate/")
    assert resp.status_code == HTTPStatus.ACCEPTED
    material.refresh_from_db()
    assert material.generation_status == GenerationStatus.QUEUED
    assert material.review_status == ReviewStatus.PENDING
    assert material.output_json is None
    assert material.error_message == ""
    assert not GenerationSource.objects.filter(material=material).exists()


def test_delete_material(auth_client):
    material = MarketingMaterialFactory()
    resp = auth_client.delete(f"{URL}{material.pk}/")
    assert resp.status_code == HTTPStatus.NO_CONTENT
    assert not MarketingMaterial.objects.filter(pk=material.pk).exists()
```

Run — expected: the regenerate tests FAIL with 404 (no action yet); PATCH/DELETE tests may already pass (mixins from Task 5).

- [ ] **Step 2: Implement the regenerate action**

Append to `MaterialViewSet` in `backend/collateral_ai/materials/api/views.py`:

```python
    @extend_schema(
        request=None,
        responses={
            202: MaterialDetailSerializer,
            409: OpenApiResponse(description="Generation already in progress"),
        },
    )
    @action(detail=True, methods=["post"])
    def regenerate(self, request, pk=None):
        material = self.get_object()
        is_active = material.generation_status in {
            GenerationStatus.QUEUED,
            GenerationStatus.PROCESSING,
        }
        is_stale = material.updated_at < timezone.now() - STALE_AFTER
        if is_active and not is_stale:
            return Response(
                {"detail": "Generation is already in progress."},
                status=status.HTTP_409_CONFLICT,
            )
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
        self._dispatch(material)
        material.refresh_from_db()
        return Response(
            MaterialDetailSerializer(material, context={"request": request}).data,
            status=status.HTTP_202_ACCEPTED,
        )
```

- [ ] **Step 3: Run tests to verify pass**

```bash
docker compose -f docker-compose.local.yml run --rm django pytest collateral_ai/materials -q
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/collateral_ai/materials
git commit -m "feat(materials): review-status rules, regenerate with staleness escape hatch, delete"
```

---

### Task 7: Generation — response schema builder + output validator

**Files:**
- Create: `backend/collateral_ai/materials/generation/__init__.py` (empty)
- Create: `backend/collateral_ai/materials/generation/schema.py`
- Create: `backend/collateral_ai/materials/generation/validation.py`
- Create: `backend/collateral_ai/materials/tests/generation/__init__.py` (empty)
- Test: `backend/collateral_ai/materials/tests/generation/test_schema.py`, `backend/collateral_ai/materials/tests/generation/test_validation.py`

**Interfaces:**
- Consumes: nothing (pure functions over dicts — no DB, no Django models).
- Produces: `build_response_schema(*, constraints: dict, image_slots: list[dict]) -> dict` (Vertex structured-output schema, **excludes** `template_id`/`theme` — those are server-stamped); `ValidationResult` dataclass (`is_valid: bool`, `errors: list[dict]`, `.to_dict()`); `OutputValidator.validate(*, output: dict, constraints: dict, image_slots: list[dict], allowed_source_ids: set[str]) -> ValidationResult` with error categories exactly `structure | word_limit | image_slot | source`.

- [ ] **Step 1: Write failing validator tests**

`backend/collateral_ai/materials/tests/generation/test_validation.py`:

```python
from __future__ import annotations

from collateral_ai.materials.generation.validation import OutputValidator

CONSTRAINTS = {
    "headline_max_words": 5,
    "subheadline_max_words": 8,
    "body_section_count": 2,
    "body_section_max_words": 10,
    "cta_max_words": 4,
}
IMAGE_SLOTS = [
    {"slot_id": "hero_image", "label": "Hero", "spec": "1200×630", "source": "generated_placeholder"},
    {"slot_id": "sender_logo", "label": "Logo", "spec": "SVG", "source": "sender"},
]
ALLOWED = {"SENDER_SOURCE_1", "RECEIVER_SOURCE_1"}


def valid_output() -> dict:
    return {
        "article": {
            "headline": "Smart warehouses now",
            "subheadline": "AI planning for modern logistics teams",
            "body_sections": [
                {"title": "The Challenge", "text": "Manual planning wastes hours weekly."},
                {"title": "The Solution", "text": "Predictive AI removes the guesswork."},
            ],
            "cta": "Book a demo",
        },
        "image_slots": [
            {"slot_id": "hero_image", "description": "warehouse", "source": "generated_placeholder"},
            {"slot_id": "sender_logo", "description": "logo", "source": "sender"},
        ],
        "source_references": [
            {"source_id": "SENDER_SOURCE_1", "used_fact": "AI planning claim"},
        ],
    }


def validate(output: dict):
    return OutputValidator().validate(
        output=output,
        constraints=CONSTRAINTS,
        image_slots=IMAGE_SLOTS,
        allowed_source_ids=ALLOWED,
    )


def categories(result) -> set[str]:
    return {e["category"] for e in result.errors}


def test_valid_output_passes():
    result = validate(valid_output())
    assert result.is_valid, result.errors
    assert result.to_dict() == {"is_valid": True, "errors": []}


def test_missing_article_field_is_structure_error():
    output = valid_output()
    del output["article"]["cta"]
    result = validate(output)
    assert not result.is_valid
    assert categories(result) == {"structure"}


def test_word_limit_violations():
    output = valid_output()
    output["article"]["headline"] = "one two three four five six"  # 6 > 5
    result = validate(output)
    assert categories(result) == {"word_limit"}


def test_wrong_body_section_count_is_word_limit_category():
    output = valid_output()
    output["article"]["body_sections"].append({"title": "Extra", "text": "x"})
    result = validate(output)
    assert not result.is_valid
    assert "word_limit" in categories(result)


def test_missing_and_mismatched_image_slots():
    output = valid_output()
    output["image_slots"] = [
        {"slot_id": "hero_image", "description": "x", "source": "sender"},  # wrong source
    ]
    result = validate(output)
    assert categories(result) == {"image_slot"}


def test_unknown_source_id_and_empty_references():
    output = valid_output()
    output["source_references"] = [{"source_id": "NOPE_9", "used_fact": "x"}]
    assert categories(validate(output)) == {"source"}
    output["source_references"] = []
    assert categories(validate(output)) == {"source"}
```

- [ ] **Step 2: Write failing schema-builder tests**

`backend/collateral_ai/materials/tests/generation/test_schema.py`:

```python
from __future__ import annotations

from collateral_ai.materials.generation.schema import build_response_schema

CONSTRAINTS = {
    "headline_max_words": 10,
    "subheadline_max_words": 22,
    "body_section_count": 2,
    "body_section_max_words": 80,
    "cta_max_words": 15,
}
SLOTS = [
    {"slot_id": "hero_image", "label": "Hero", "spec": "1200×630", "source": "generated_placeholder"},
    {"slot_id": "sender_logo", "label": "Logo", "spec": "SVG", "source": "sender"},
]


def test_schema_shape_and_slot_enum():
    schema = build_response_schema(constraints=CONSTRAINTS, image_slots=SLOTS)
    assert set(schema["properties"]) == {"article", "image_slots", "source_references"}
    assert schema["required"] == ["article", "image_slots", "source_references"]
    # template_id and theme are server-stamped — never model-generated (spec §4)
    assert "template_id" not in schema["properties"]
    assert "theme" not in schema["properties"]
    slots = schema["properties"]["image_slots"]
    assert slots["minItems"] == 2
    assert slots["maxItems"] == 2
    assert slots["items"]["properties"]["slot_id"]["enum"] == [
        "hero_image",
        "sender_logo",
    ]
    body = schema["properties"]["article"]["properties"]["body_sections"]
    assert body["minItems"] == 2
    assert body["maxItems"] == 2
```

Run:

```bash
docker compose -f docker-compose.local.yml run --rm django pytest collateral_ai/materials/tests/generation -q
```

Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement schema.py**

`backend/collateral_ai/materials/generation/schema.py`:

```python
"""Structured-output schema for Vertex Gemini, parameterized by the template.

The dict uses Vertex's OpenAPI-subset schema (uppercase types, camelCase
minItems/maxItems — google-genai's types.Schema accepts these aliases).
minItems/maxItems are best-effort hints; OutputValidator is the enforcement
backstop when the model ignores them.

template_id and theme are deliberately absent: both are stamped server-side
from the template after every model response (spec §4).
"""

from __future__ import annotations

from typing import Any

SLOT_SOURCE_VALUES = ["sender", "receiver", "generated_placeholder"]


def build_response_schema(
    *,
    constraints: dict,
    image_slots: list[dict],
) -> dict[str, Any]:
    section_count = int(constraints["body_section_count"])
    slot_ids = [slot["slot_id"] for slot in image_slots]
    return {
        "type": "OBJECT",
        "properties": {
            "article": {
                "type": "OBJECT",
                "properties": {
                    "headline": {"type": "STRING"},
                    "subheadline": {"type": "STRING"},
                    "body_sections": {
                        "type": "ARRAY",
                        "minItems": section_count,
                        "maxItems": section_count,
                        "items": {
                            "type": "OBJECT",
                            "properties": {
                                "title": {"type": "STRING"},
                                "text": {"type": "STRING"},
                            },
                            "required": ["title", "text"],
                        },
                    },
                    "cta": {"type": "STRING"},
                },
                "required": ["headline", "subheadline", "body_sections", "cta"],
            },
            "image_slots": {
                "type": "ARRAY",
                "minItems": len(slot_ids),
                "maxItems": len(slot_ids),
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "slot_id": {"type": "STRING", "enum": slot_ids},
                        "description": {"type": "STRING"},
                        "source": {"type": "STRING", "enum": SLOT_SOURCE_VALUES},
                    },
                    "required": ["slot_id", "description", "source"],
                },
            },
            "source_references": {
                "type": "ARRAY",
                "minItems": 1,
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "source_id": {"type": "STRING"},
                        "used_fact": {"type": "STRING"},
                    },
                    "required": ["source_id", "used_fact"],
                },
            },
        },
        "required": ["article", "image_slots", "source_references"],
    }
```

- [ ] **Step 4: Implement validation.py**

`backend/collateral_ai/materials/generation/validation.py`:

```python
"""Deterministic validation of generated output against template constraints.

Error categories map one-to-one onto the detail page's Quality checks
(spec §6.4): structure, word_limit, image_slot, source. There is no theme
category — theme is server-stamped, never validated here.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from typing import Any

STRUCTURE = "structure"
WORD_LIMIT = "word_limit"
IMAGE_SLOT = "image_slot"
SOURCE = "source"


def _word_count(value: str) -> int:
    return len(value.split()) if value else 0


@dataclass
class ValidationResult:
    is_valid: bool
    errors: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"is_valid": self.is_valid, "errors": self.errors}


class OutputValidator:
    def validate(
        self,
        *,
        output: dict,
        constraints: dict,
        image_slots: list[dict],
        allowed_source_ids: set[str],
    ) -> ValidationResult:
        errors: list[dict[str, str]] = []
        self._check_structure(output, errors)
        if not errors:
            self._check_word_limits(output, constraints, errors)
            self._check_image_slots(output, image_slots, errors)
            self._check_sources(output, allowed_source_ids, errors)
        return ValidationResult(is_valid=not errors, errors=errors)

    def _add(self, errors: list, category: str, message: str) -> None:
        errors.append({"category": category, "message": message})

    def _check_structure(self, output: dict, errors: list) -> None:
        if not isinstance(output, dict):
            self._add(errors, STRUCTURE, "Output must be a JSON object.")
            return
        article = output.get("article")
        if not isinstance(article, dict):
            self._add(errors, STRUCTURE, "article must be an object.")
            return
        for key in ("headline", "subheadline", "cta"):
            if not isinstance(article.get(key), str) or not article.get(key):
                self._add(errors, STRUCTURE, f"article.{key} must be a non-empty string.")
        sections = article.get("body_sections")
        if not isinstance(sections, list):
            self._add(errors, STRUCTURE, "article.body_sections must be a list.")
        else:
            for i, section in enumerate(sections, start=1):
                if (
                    not isinstance(section, dict)
                    or not section.get("title")
                    or not section.get("text")
                ):
                    self._add(
                        errors,
                        STRUCTURE,
                        f"body_sections[{i}] needs non-empty title and text.",
                    )
        if not isinstance(output.get("image_slots"), list):
            self._add(errors, STRUCTURE, "image_slots must be a list.")
        if not isinstance(output.get("source_references"), list):
            self._add(errors, STRUCTURE, "source_references must be a list.")

    def _check_word_limits(self, output: dict, constraints: dict, errors: list) -> None:
        article = output["article"]
        limits = [
            ("article.headline", article["headline"], constraints["headline_max_words"]),
            (
                "article.subheadline",
                article["subheadline"],
                constraints["subheadline_max_words"],
            ),
            ("article.cta", article["cta"], constraints["cta_max_words"]),
        ]
        for name, value, max_words in limits:
            count = _word_count(value)
            if count > max_words:
                self._add(
                    errors,
                    WORD_LIMIT,
                    f"{name} has {count} words, max {max_words}.",
                )
        sections = article["body_sections"]
        expected = constraints["body_section_count"]
        if len(sections) != expected:
            self._add(
                errors,
                WORD_LIMIT,
                f"Expected {expected} body sections, got {len(sections)}.",
            )
        for i, section in enumerate(sections, start=1):
            count = _word_count(section.get("text", ""))
            if count > constraints["body_section_max_words"]:
                self._add(
                    errors,
                    WORD_LIMIT,
                    f"body_sections[{i}].text has {count} words, "
                    f"max {constraints['body_section_max_words']}.",
                )

    def _check_image_slots(self, output: dict, image_slots: list, errors: list) -> None:
        expected = {slot["slot_id"]: slot["source"] for slot in image_slots}
        returned = {
            slot.get("slot_id"): slot.get("source")
            for slot in output["image_slots"]
            if isinstance(slot, dict)
        }
        for slot_id, source in expected.items():
            if slot_id not in returned:
                self._add(errors, IMAGE_SLOT, f"Missing required image slot: {slot_id}.")
            elif returned[slot_id] != source:
                self._add(
                    errors,
                    IMAGE_SLOT,
                    f"Slot {slot_id} source must be {source!r}, got {returned[slot_id]!r}.",
                )
        for slot_id in returned:
            if slot_id not in expected:
                self._add(errors, IMAGE_SLOT, f"Unknown image slot: {slot_id}.")

    def _check_sources(self, output: dict, allowed: set[str], errors: list) -> None:
        references = output["source_references"]
        if not references:
            self._add(errors, SOURCE, "At least one source reference is required.")
            return
        for i, ref in enumerate(references, start=1):
            if not isinstance(ref, dict) or not ref.get("source_id"):
                self._add(errors, SOURCE, f"source_references[{i}] needs a source_id.")
                continue
            if ref["source_id"] not in allowed:
                self._add(
                    errors,
                    SOURCE,
                    f"source_references[{i}].source_id is unknown: {ref['source_id']}.",
                )
            if not ref.get("used_fact"):
                self._add(errors, SOURCE, f"source_references[{i}].used_fact is required.")
```

- [ ] **Step 5: Run tests to verify pass, commit**

```bash
docker compose -f docker-compose.local.yml run --rm django pytest collateral_ai/materials/tests/generation -q
git add backend/collateral_ai/materials
git commit -m "feat(materials): template-derived response schema + deterministic output validator"
```

Expected: PASS (8 tests).

---

### Task 8: Generation — retrieval service

**Files:**
- Create: `backend/collateral_ai/materials/generation/retrieval.py`
- Test: `backend/collateral_ai/materials/tests/generation/test_retrieval.py`

**Interfaces:**
- Consumes: `DocumentChunk` (pgvector `CosineDistance`), `documents.processing.embeddings.EmbeddingService` (only for the type; the query embedding is computed by the caller).
- Produces: `RetrievedChunk` frozen dataclass (`source_id, chunk_id: int, document_id: int, company_id: int, file_name: str, page_number: int, chunk_type: str, content: str, relevance_score: float, source_role: str`, method `to_prompt_dict()` → the subset `{source_id, file_name, page_number, chunk_type, content}`); `RetrievalService.retrieve(*, company_id: int, query_embedding: list[float], source_role: str, source_prefix: str, top_k: int) -> list[RetrievedChunk]`.

- [ ] **Step 1: Write failing tests**

`backend/collateral_ai/materials/tests/generation/test_retrieval.py`:

```python
from __future__ import annotations

import pytest

from collateral_ai.companies.tests.factories import CompanyFactory
from collateral_ai.documents.tests.factories import DocumentChunkFactory
from collateral_ai.documents.tests.factories import DocumentFactory
from collateral_ai.materials.generation.retrieval import RetrievalService
from collateral_ai.materials.statuses import SourceRole

pytestmark = pytest.mark.django_db


def embedding(first: float) -> list[float]:
    vec = [0.0] * 768
    vec[0] = first
    return vec


def test_retrieve_orders_by_cosine_distance_and_labels_sources():
    company = CompanyFactory()
    doc = DocumentFactory(company=company, file_name="brochure.pdf")
    far = DocumentChunkFactory(document=doc, content="far", embedding=embedding(-1.0))
    near = DocumentChunkFactory(
        document=doc,
        content="near",
        page_number=3,
        embedding=embedding(1.0),
    )
    results = RetrievalService().retrieve(
        company_id=company.pk,
        query_embedding=embedding(1.0),
        source_role=SourceRole.SENDER,
        source_prefix="SENDER_SOURCE",
        top_k=2,
    )
    assert [r.chunk_id for r in results] == [near.pk, far.pk]
    first = results[0]
    assert first.source_id == "SENDER_SOURCE_1"
    assert first.file_name == "brochure.pdf"
    assert first.page_number == 3
    assert first.source_role == SourceRole.SENDER
    assert first.to_prompt_dict() == {
        "source_id": "SENDER_SOURCE_1",
        "file_name": "brochure.pdf",
        "page_number": 3,
        "chunk_type": "text",
        "content": "near",
    }


def test_retrieve_scopes_to_company_and_respects_top_k():
    company, other = CompanyFactory(), CompanyFactory()
    doc = DocumentFactory(company=company)
    for i in range(3):
        DocumentChunkFactory(document=doc, content=f"c{i}", embedding=embedding(0.5))
    DocumentChunkFactory(
        document=DocumentFactory(company=other),
        embedding=embedding(1.0),
    )
    results = RetrievalService().retrieve(
        company_id=company.pk,
        query_embedding=embedding(1.0),
        source_role=SourceRole.RECEIVER,
        source_prefix="RECEIVER_SOURCE",
        top_k=2,
    )
    assert len(results) == 2
    assert all(r.company_id == company.pk for r in results)


def test_retrieve_returns_empty_for_company_without_chunks():
    company = CompanyFactory()
    results = RetrievalService().retrieve(
        company_id=company.pk,
        query_embedding=embedding(1.0),
        source_role=SourceRole.SENDER,
        source_prefix="SENDER_SOURCE",
        top_k=8,
    )
    assert results == []
```

Run — expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 2: Implement**

`backend/collateral_ai/materials/generation/retrieval.py`:

```python
"""pgvector retrieval of company document chunks for generation grounding."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pgvector.django import CosineDistance

from collateral_ai.documents.models import DocumentChunk


@dataclass(frozen=True)
class RetrievedChunk:
    source_id: str
    chunk_id: int
    document_id: int
    company_id: int
    file_name: str
    page_number: int
    chunk_type: str
    content: str
    relevance_score: float
    source_role: str

    def to_prompt_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "file_name": self.file_name,
            "page_number": self.page_number,
            "chunk_type": self.chunk_type,
            "content": self.content,
        }


class RetrievalService:
    def retrieve(
        self,
        *,
        company_id: int,
        query_embedding: list[float],
        source_role: str,
        source_prefix: str,
        top_k: int,
    ) -> list[RetrievedChunk]:
        # `embedding` is non-nullable — every persisted chunk has one (spec §6.3).
        chunks = (
            DocumentChunk.objects.filter(company_id=company_id)
            .select_related("document")
            .annotate(distance=CosineDistance("embedding", query_embedding))
            .order_by("distance")[:top_k]
        )
        return [
            RetrievedChunk(
                source_id=f"{source_prefix}_{index}",
                chunk_id=chunk.pk,
                document_id=chunk.document_id,
                company_id=chunk.company_id,
                file_name=chunk.document.file_name,
                page_number=chunk.page_number,
                chunk_type=chunk.chunk_type,
                content=chunk.content,
                relevance_score=float(chunk.distance),
                source_role=source_role,
            )
            for index, chunk in enumerate(chunks, start=1)
        ]
```

- [ ] **Step 3: Run tests to verify pass, commit**

```bash
docker compose -f docker-compose.local.yml run --rm django pytest collateral_ai/materials/tests/generation/test_retrieval.py -q
git add backend/collateral_ai/materials
git commit -m "feat(materials): pgvector retrieval service for generation grounding"
```

---

### Task 9: Generation — prompts, LLM client, repair

**Files:**
- Create: `backend/collateral_ai/materials/generation/prompts.py`
- Create: `backend/collateral_ai/materials/generation/llm.py`
- Create: `backend/collateral_ai/materials/generation/repair.py`
- Test: `backend/collateral_ai/materials/tests/generation/test_llm_and_repair.py`

**Interfaces:**
- Consumes: `RetrievedChunk.to_prompt_dict()` (Task 8), `MATERIAL_*` settings (Task 5).
- Produces:
  - `prompts.SYSTEM_INSTRUCTION: str`, `prompts.REPAIR_SYSTEM_INSTRUCTION: str`
  - `prompts.build_retrieval_query(material) -> str`
  - `prompts.build_generation_payload(*, material, sender_chunks, receiver_chunks) -> str` (JSON string)
  - `prompts.build_repair_payload(*, output, errors, constraints, image_slots, allowed_source_ids) -> str`
  - `llm.GenerationClient.generate_json(*, system_instruction: str, user_input: str, response_schema: dict) -> dict`
  - `repair.OutputRepairService(client).repair(*, output, errors, constraints, image_slots, allowed_source_ids, response_schema) -> dict`

- [ ] **Step 1: Write failing tests**

`backend/collateral_ai/materials/tests/generation/test_llm_and_repair.py`:

```python
from __future__ import annotations

import json
from unittest import mock

import pytest

from collateral_ai.materials.generation.llm import GenerationClient
from collateral_ai.materials.generation.prompts import build_generation_payload
from collateral_ai.materials.generation.prompts import build_retrieval_query
from collateral_ai.materials.generation.repair import OutputRepairService
from collateral_ai.materials.generation.retrieval import RetrievedChunk
from collateral_ai.materials.statuses import SourceRole
from collateral_ai.materials.tests.factories import MarketingMaterialFactory

pytestmark = pytest.mark.django_db


def chunk(source_id: str, role: str) -> RetrievedChunk:
    return RetrievedChunk(
        source_id=source_id,
        chunk_id=1,
        document_id=1,
        company_id=1,
        file_name="doc.pdf",
        page_number=2,
        chunk_type="text",
        content="Acme reduces planning time by 40%.",
        relevance_score=0.1,
        source_role=role,
    )


def test_retrieval_query_mentions_prompt_and_companies():
    material = MarketingMaterialFactory(prompt="Pitch warehouse AI")
    query = build_retrieval_query(material)
    assert "Pitch warehouse AI" in query
    assert material.sender_company.name in query
    assert material.receiver_company.name in query


def test_generation_payload_is_json_with_context_and_constraints():
    material = MarketingMaterialFactory()
    payload = json.loads(
        build_generation_payload(
            material=material,
            sender_chunks=[chunk("SENDER_SOURCE_1", SourceRole.SENDER)],
            receiver_chunks=[chunk("RECEIVER_SOURCE_1", SourceRole.RECEIVER)],
        ),
    )
    assert payload["material_prompt"] == material.prompt
    assert payload["template"]["constraints"] == material.template.constraints
    assert payload["sender_context"][0]["source_id"] == "SENDER_SOURCE_1"
    assert payload["receiver_context"][0]["source_id"] == "RECEIVER_SOURCE_1"
    # theme is server-stamped, so the model has no reason to see or echo it
    assert "theme" not in payload["template"]


def test_generation_client_parses_json_response(settings):
    settings.GOOGLE_CLOUD_PROJECT = "proj"
    fake_response = mock.Mock(text='{"ok": true}')
    with mock.patch("google.genai.Client") as client_cls:
        client_cls.return_value.models.generate_content.return_value = fake_response
        result = GenerationClient().generate_json(
            system_instruction="sys",
            user_input="{}",
            response_schema={"type": "OBJECT"},
        )
    assert result == {"ok": True}
    config = client_cls.return_value.models.generate_content.call_args.kwargs["config"]
    assert config.response_mime_type == "application/json"


def test_generation_client_raises_on_empty_and_invalid_json(settings):
    settings.GOOGLE_CLOUD_PROJECT = "proj"
    for text in ("", "not json"):
        fake_response = mock.Mock(text=text)
        with mock.patch("google.genai.Client") as client_cls:
            client_cls.return_value.models.generate_content.return_value = fake_response
            with pytest.raises(ValueError, match="Gemini"):
                GenerationClient().generate_json(
                    system_instruction="sys",
                    user_input="{}",
                    response_schema={"type": "OBJECT"},
                )


def test_repair_calls_client_with_errors_and_same_schema():
    client = mock.Mock()
    client.generate_json.return_value = {"fixed": True}
    schema = {"type": "OBJECT"}
    result = OutputRepairService(client).repair(
        output={"bad": True},
        errors=[{"category": "word_limit", "message": "too long"}],
        constraints={"headline_max_words": 10},
        image_slots=[],
        allowed_source_ids=["SENDER_SOURCE_1"],
        response_schema=schema,
    )
    assert result == {"fixed": True}
    kwargs = client.generate_json.call_args.kwargs
    assert kwargs["response_schema"] is schema
    assert "too long" in kwargs["user_input"]
```

Run — expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 2: Implement prompts.py**

`backend/collateral_ai/materials/generation/prompts.py`:

```python
"""Prompt construction for material generation (spec §6.3 step 3)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collateral_ai.materials.generation.retrieval import RetrievedChunk
    from collateral_ai.materials.models import MarketingMaterial

SYSTEM_INSTRUCTION = """
You are a senior B2B marketing strategist and a strict structured JSON \
generation system.

Rules:
- Generate tailored B2B marketing material from the sender to the receiver.
- Use ONLY the provided sender_context and receiver_context. No external \
knowledge, no unsupported claims.
- Think through the receiver's pain points and pick one sharp campaign angle \
before writing.
- Respect every constraint in template.constraints (word limits are hard \
limits, counted by whitespace-separated words).
- image_slots: return one entry per slot listed in template.image_slots, with \
the same slot_id and source; write a short description of the ideal asset.
- source_references: cite only source_id values that appear in sender_context \
or receiver_context, and explain the fact used.
- Keep the tone professional, credible, and specific.
""".strip()

REPAIR_SYSTEM_INSTRUCTION = """
You repair invalid JSON for a marketing layout system.

Rules:
- Return valid JSON only, matching the schema.
- Fix ONLY what the validation errors list; keep everything else unchanged.
- Do not add unsupported claims.
- Respect all word limits (whitespace-separated words).
- Use only allowed source IDs.
""".strip()


def build_retrieval_query(material: MarketingMaterial) -> str:
    return (
        f"Marketing request: {material.prompt}\n"
        f"Sender company: {material.sender_company.name}\n"
        f"Receiver company: {material.receiver_company.name}\n"
        f"Tone: {material.tone}\n"
        "Find relevant products, positioning, benefits, industry, pain points, "
        "and proof points."
    )


def build_generation_payload(
    *,
    material: MarketingMaterial,
    sender_chunks: list[RetrievedChunk],
    receiver_chunks: list[RetrievedChunk],
) -> str:
    template = material.template
    payload = {
        "task": "Generate a short tailored B2B marketing article.",
        "material_prompt": material.prompt,
        "tone": material.tone,
        "cta_style": material.cta_style,
        "language": material.language,
        "sender_company": _company_dict(material.sender_company),
        "receiver_company": _company_dict(material.receiver_company),
        "template": {
            "name": template.name,
            "constraints": template.constraints,
            "image_slots": template.image_slots,
        },
        "sender_context": [c.to_prompt_dict() for c in sender_chunks],
        "receiver_context": [c.to_prompt_dict() for c in receiver_chunks],
    }
    return json.dumps(payload, indent=2)


def build_repair_payload(
    *,
    output: dict,
    errors: list[dict],
    constraints: dict,
    image_slots: list[dict],
    allowed_source_ids: list[str],
) -> str:
    return json.dumps(
        {
            "invalid_output_json": output,
            "validation_errors": errors,
            "template_constraints": constraints,
            "template_image_slots": image_slots,
            "allowed_source_ids": allowed_source_ids,
            "instruction": (
                "Fix the JSON so it passes validation. Respect word limits, "
                "required fields, image slots, and source references."
            ),
        },
        indent=2,
    )


def _company_dict(company) -> dict:
    return {
        "id": company.pk,
        "name": company.name,
        "industry": company.industry,
        "description": company.description,
    }
```

- [ ] **Step 3: Implement llm.py and repair.py**

`backend/collateral_ai/materials/generation/llm.py`:

```python
"""Gemini structured-output generation via Vertex AI (keyless ADC).

Same client pattern as documents.processing.embeddings.EmbeddingService.
"""

from __future__ import annotations

import json

from django.conf import settings


class GenerationClient:
    def __init__(self) -> None:
        self.model = settings.MATERIAL_LLM_MODEL
        self.temperature = float(settings.MATERIAL_GENERATION_TEMPERATURE)
        self.max_output_tokens = int(settings.MATERIAL_GENERATION_MAX_OUTPUT_TOKENS)

    def _client(self):
        from google import genai

        return genai.Client(
            vertexai=True,
            project=settings.GOOGLE_CLOUD_PROJECT,
            location=settings.VERTEX_LOCATION,
        )

    def generate_json(
        self,
        *,
        system_instruction: str,
        user_input: str,
        response_schema: dict,
    ) -> dict:
        from google.genai import types

        response = self._client().models.generate_content(
            model=self.model,
            contents=user_input,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=self.temperature,
                max_output_tokens=self.max_output_tokens,
                response_mime_type="application/json",
                response_schema=response_schema,
            ),
        )
        text = getattr(response, "text", None)
        if not text:
            msg = "Gemini returned an empty response."
            raise ValueError(msg)
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            msg = f"Gemini returned invalid JSON: {text[:500]}"
            raise ValueError(msg) from exc
```

`backend/collateral_ai/materials/generation/repair.py`:

```python
"""Corrective LLM call: invalid JSON + validation errors → fixed JSON (spec §6.3 step 5)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from collateral_ai.materials.generation.prompts import REPAIR_SYSTEM_INSTRUCTION
from collateral_ai.materials.generation.prompts import build_repair_payload

if TYPE_CHECKING:
    from collateral_ai.materials.generation.llm import GenerationClient


class OutputRepairService:
    def __init__(self, client: GenerationClient) -> None:
        self.client = client

    def repair(
        self,
        *,
        output: dict,
        errors: list[dict],
        constraints: dict,
        image_slots: list[dict],
        allowed_source_ids: list[str],
        response_schema: dict,
    ) -> dict:
        return self.client.generate_json(
            system_instruction=REPAIR_SYSTEM_INSTRUCTION,
            user_input=build_repair_payload(
                output=output,
                errors=errors,
                constraints=constraints,
                image_slots=image_slots,
                allowed_source_ids=allowed_source_ids,
            ),
            response_schema=response_schema,
        )
```

- [ ] **Step 4: Run tests to verify pass, commit**

```bash
docker compose -f docker-compose.local.yml run --rm django pytest collateral_ai/materials/tests/generation -q
git add backend/collateral_ai/materials
git commit -m "feat(materials): generation prompts, Vertex Gemini client, repair service"
```

---

### Task 10: Generation — orchestrator service + management command

**Files:**
- Create: `backend/collateral_ai/materials/generation/service.py`
- Create: `backend/collateral_ai/materials/management/__init__.py`, `backend/collateral_ai/materials/management/commands/__init__.py` (empty)
- Create: `backend/collateral_ai/materials/management/commands/generate_material.py`
- Test: `backend/collateral_ai/materials/tests/generation/test_service.py`

**Interfaces:**
- Consumes: everything from Tasks 7–9, `EmbeddingService.embed_query` (documents app), models/statuses.
- Produces: `MaterialGenerationService(embedder=None, retriever=None, client=None, repairer=None).generate(material_id: int, *, force: bool = False, top_k: int | None = None) -> bool` (False = skipped claim, exit 0); command `python manage.py generate_material --material-id N [--force] [--top-k K]`.

- [ ] **Step 1: Implement service.py** (service first here — the test needs its injection seams to exist to be meaningful; the tests in Step 3 are the acceptance gate)

`backend/collateral_ai/materials/generation/service.py`:

```python
"""Worker 2 orchestration: claim → retrieve → generate → validate/repair → save.

State machine rules (spec §6.3): claim is its own short transaction so the row
lock is never held during the multi-minute pipeline; completed/processing
without --force skip with exit 0; review_status is never touched here.
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from collateral_ai.documents.processing.embeddings import EmbeddingService
from collateral_ai.materials.generation.llm import GenerationClient
from collateral_ai.materials.generation.prompts import SYSTEM_INSTRUCTION
from collateral_ai.materials.generation.prompts import build_generation_payload
from collateral_ai.materials.generation.prompts import build_retrieval_query
from collateral_ai.materials.generation.repair import OutputRepairService
from collateral_ai.materials.generation.retrieval import RetrievalService
from collateral_ai.materials.generation.schema import build_response_schema
from collateral_ai.materials.generation.validation import OutputValidator
from collateral_ai.materials.models import GenerationSource
from collateral_ai.materials.models import MarketingMaterial
from collateral_ai.materials.statuses import GenerationStatus
from collateral_ai.materials.statuses import SourceRole

logger = logging.getLogger(__name__)


class MaterialGenerationService:
    def __init__(
        self,
        *,
        embedder: EmbeddingService | None = None,
        retriever: RetrievalService | None = None,
        client: GenerationClient | None = None,
        repairer: OutputRepairService | None = None,
    ) -> None:
        self.embedder = embedder or EmbeddingService()
        self.retriever = retriever or RetrievalService()
        self.client = client or GenerationClient()
        self.repairer = repairer or OutputRepairService(self.client)
        self.validator = OutputValidator()
        self.default_top_k = int(settings.MATERIAL_RETRIEVAL_TOP_K)
        self.max_repair_attempts = int(settings.MATERIAL_MAX_REPAIR_ATTEMPTS)

    def generate(
        self,
        material_id: int,
        *,
        force: bool = False,
        top_k: int | None = None,
    ) -> bool:
        material = self._claim(material_id, force=force)
        if material is None:
            return False
        try:
            self._run_pipeline(material, top_k=top_k or self.default_top_k)
        except Exception as exc:
            logger.exception("generation failed material=%s", material_id)
            MarketingMaterial.objects.filter(pk=material.pk).update(
                generation_status=GenerationStatus.FAILED,
                error_message=str(exc),
                updated_at=timezone.now(),
            )
            raise
        return True

    def _claim(self, material_id: int, *, force: bool) -> MarketingMaterial | None:
        """Short standalone transaction: lock → check → set processing → commit.

        The command runs outside ATOMIC_REQUESTS, so select_for_update needs
        this explicit atomic block. Generation runs OUTSIDE it — the row lock
        must not be held for the whole pipeline.
        """
        with transaction.atomic():
            material = (
                MarketingMaterial.objects.select_for_update()
                .select_related("sender_company", "receiver_company", "template")
                .get(pk=material_id)
            )
            claimable = {GenerationStatus.QUEUED, GenerationStatus.FAILED}
            if not force and material.generation_status not in claimable:
                # Duplicate execution racing a running job, or an already-done
                # row: skip quietly (exit 0) so Cloud Run doesn't retry.
                logger.info(
                    "skipping material=%s status=%s (use --force to override)",
                    material_id,
                    material.generation_status,
                )
                return None
            material.generation_status = GenerationStatus.PROCESSING
            material.error_message = ""
            material.save(
                update_fields=["generation_status", "error_message", "updated_at"],
            )
        return material

    def _run_pipeline(self, material: MarketingMaterial, *, top_k: int) -> None:
        template = material.template
        query_embedding = self.embedder.embed_query(build_retrieval_query(material))
        sender_chunks = self.retriever.retrieve(
            company_id=material.sender_company_id,
            query_embedding=query_embedding,
            source_role=SourceRole.SENDER,
            source_prefix="SENDER_SOURCE",
            top_k=top_k,
        )
        receiver_chunks = self.retriever.retrieve(
            company_id=material.receiver_company_id,
            query_embedding=query_embedding,
            source_role=SourceRole.RECEIVER,
            source_prefix="RECEIVER_SOURCE",
            top_k=top_k,
        )
        for role, chunks, company in (
            ("sender", sender_chunks, material.sender_company),
            ("receiver", receiver_chunks, material.receiver_company),
        ):
            if not chunks:
                msg = (
                    f"No processed document chunks for {role} company "
                    f"{company.name!r} — upload and process documents first."
                )
                raise ValueError(msg)

        source_map = {c.source_id: c for c in [*sender_chunks, *receiver_chunks]}
        allowed_ids = set(source_map)
        response_schema = build_response_schema(
            constraints=template.constraints,
            image_slots=template.image_slots,
        )

        output = self.client.generate_json(
            system_instruction=SYSTEM_INSTRUCTION,
            user_input=build_generation_payload(
                material=material,
                sender_chunks=sender_chunks,
                receiver_chunks=receiver_chunks,
            ),
            response_schema=response_schema,
        )
        output = self._stamp(output, template)
        result = self._validate(output, template, allowed_ids)

        attempts = 0
        while not result.is_valid and attempts < self.max_repair_attempts:
            attempts += 1
            logger.warning(
                "validation failed material=%s attempt=%s errors=%s",
                material.pk,
                attempts,
                result.errors,
            )
            output = self.repairer.repair(
                output=output,
                errors=result.errors,
                constraints=template.constraints,
                image_slots=template.image_slots,
                allowed_source_ids=sorted(allowed_ids),
                response_schema=response_schema,
            )
            output = self._stamp(output, template)
            result = self._validate(output, template, allowed_ids)

        context_snapshot = {
            "sender_context": [c.to_prompt_dict() for c in sender_chunks],
            "receiver_context": [c.to_prompt_dict() for c in receiver_chunks],
        }
        if not result.is_valid:
            # Persist the evidence for debugging (JSON tab), then fail loudly.
            MarketingMaterial.objects.filter(pk=material.pk).update(
                output_json=output,
                validation_result=result.to_dict(),
                retrieved_context=context_snapshot,
                updated_at=timezone.now(),
            )
            msg = f"Generated output failed validation: {result.errors}"
            raise ValueError(msg)

        self._save_completed(material, output, result, context_snapshot, source_map)

    def _stamp(self, output: dict, template) -> dict:
        """template_id and theme are template-owned — never trusted from the model."""
        output["template_id"] = template.slug
        output["theme"] = dict(template.theme)
        return output

    def _validate(self, output, template, allowed_ids):
        return self.validator.validate(
            output=output,
            constraints=template.constraints,
            image_slots=template.image_slots,
            allowed_source_ids=allowed_ids,
        )

    @transaction.atomic
    def _save_completed(
        self,
        material,
        output: dict,
        result,
        context_snapshot: dict,
        source_map: dict,
    ) -> None:
        now = timezone.now()
        MarketingMaterial.objects.filter(pk=material.pk).update(
            generation_status=GenerationStatus.COMPLETED,
            output_json=output,
            validation_result=result.to_dict(),
            retrieved_context=context_snapshot,
            error_message="",
            completed_at=now,
            updated_at=now,
        )
        GenerationSource.objects.filter(material=material).delete()
        # Strict source validation (Task 7) guarantees every cited id maps.
        GenerationSource.objects.bulk_create(
            [
                GenerationSource(
                    material=material,
                    company_id=source_map[ref["source_id"]].company_id,
                    document_id=source_map[ref["source_id"]].document_id,
                    chunk_id=source_map[ref["source_id"]].chunk_id,
                    source_role=source_map[ref["source_id"]].source_role,
                    page_number=source_map[ref["source_id"]].page_number,
                    snippet=source_map[ref["source_id"]].content[:500],
                    used_fact=ref["used_fact"][:1000],
                    relevance_score=source_map[ref["source_id"]].relevance_score,
                )
                for ref in output["source_references"]
            ],
        )
```

- [ ] **Step 2: Implement the management command**

`backend/collateral_ai/materials/management/commands/generate_material.py`:

```python
import time

from django.core.management.base import BaseCommand
from django.core.management.base import CommandError

from collateral_ai.materials.generation.service import MaterialGenerationService
from collateral_ai.materials.models import MarketingMaterial


class Command(BaseCommand):
    help = "Generate marketing material JSON from sender/receiver company context."

    def add_arguments(self, parser):
        parser.add_argument("--material-id", required=True, type=int)
        parser.add_argument("--force", action="store_true")
        parser.add_argument("--top-k", type=int, default=None)

    def handle(self, *args, **options):
        material_id = options["material_id"]
        started = time.monotonic()
        self.stdout.write(f"timing: worker alive (material={material_id})")
        try:
            processed = MaterialGenerationService().generate(
                material_id,
                force=options["force"],
                top_k=options["top_k"],
            )
        except MarketingMaterial.DoesNotExist as exc:
            msg = f"Marketing material not found: {material_id}"
            raise CommandError(msg) from exc
        except Exception as exc:
            msg = f"generate_material failed for {material_id}: {exc}"
            raise CommandError(msg) from exc
        if not processed:
            # Duplicate/late execution: exit 0 so Cloud Run doesn't retry.
            self.stdout.write(f"generate_material skipped for {material_id}")
            return
        self.stdout.write(f"timing: pipeline total {time.monotonic() - started:.2f}s")
        self.stdout.write(
            self.style.SUCCESS(f"generate_material completed for {material_id}"),
        )
```

- [ ] **Step 3: Write the service/command tests**

`backend/collateral_ai/materials/tests/generation/test_service.py`:

```python
from __future__ import annotations

from io import StringIO
from unittest import mock

import pytest
from django.core.management import call_command

from collateral_ai.documents.statuses import DocumentStatus
from collateral_ai.documents.tests.factories import DocumentChunkFactory
from collateral_ai.documents.tests.factories import DocumentFactory
from collateral_ai.materials.generation.service import MaterialGenerationService
from collateral_ai.materials.models import GenerationSource
from collateral_ai.materials.statuses import GenerationStatus
from collateral_ai.materials.statuses import ReviewStatus
from collateral_ai.materials.tests.factories import MarketingMaterialFactory

pytestmark = pytest.mark.django_db


def material_with_chunks():
    material = MarketingMaterialFactory()
    for company in (material.sender_company, material.receiver_company):
        doc = DocumentFactory(company=company, status=DocumentStatus.PROCESSED)
        DocumentChunkFactory(document=doc, content=f"facts about {company.name}")
    return material


def valid_output() -> dict:
    return {
        "article": {
            "headline": "Smarter Warehouses, Powered by AI",
            "subheadline": "Predictive planning for modern logistics operations",
            "body_sections": [
                {"title": "The Challenge", "text": "Manual planning wastes hours."},
                {"title": "The Solution", "text": "Predictive AI removes guesswork."},
            ],
            "cta": "Book a 20-minute assessment",
        },
        "image_slots": [
            {"slot_id": "hero_image", "description": "warehouse", "source": "generated_placeholder"},
            {"slot_id": "sender_logo", "description": "logo", "source": "sender"},
        ],
        "source_references": [
            {"source_id": "SENDER_SOURCE_1", "used_fact": "sender fact"},
            {"source_id": "RECEIVER_SOURCE_1", "used_fact": "receiver fact"},
        ],
    }


def make_service(outputs: list[dict]) -> MaterialGenerationService:
    embedder = mock.Mock()
    embedder.embed_query.return_value = [0.0] * 768
    client = mock.Mock()
    client.generate_json.side_effect = list(outputs)
    repairer = mock.Mock()
    return MaterialGenerationService(
        embedder=embedder,
        client=client,
        repairer=repairer,
    )


def test_happy_path_completes_and_saves_sources():
    material = material_with_chunks()
    service = make_service([valid_output()])
    assert service.generate(material.pk) is True
    material.refresh_from_db()
    assert material.generation_status == GenerationStatus.COMPLETED
    assert material.review_status == ReviewStatus.PENDING  # untouched
    assert material.output_json["template_id"] == material.template.slug
    assert material.output_json["theme"] == material.template.theme
    assert material.validation_result == {"is_valid": True, "errors": []}
    assert material.completed_at is not None
    assert material.retrieved_context["sender_context"]
    sources = list(GenerationSource.objects.filter(material=material))
    assert {s.source_role for s in sources} == {"sender", "receiver"}
    assert sources[0].snippet


def test_repair_loop_recovers_invalid_output():
    material = material_with_chunks()
    bad = valid_output()
    bad["article"]["headline"] = " ".join(["word"] * 30)  # violates limit of 10
    service = make_service([bad])
    service.repairer.repair.return_value = valid_output()
    assert service.generate(material.pk) is True
    material.refresh_from_db()
    assert material.generation_status == GenerationStatus.COMPLETED
    service.repairer.repair.assert_called_once()


def test_validation_exhausted_fails_but_persists_output():
    material = material_with_chunks()
    bad = valid_output()
    bad["article"]["headline"] = " ".join(["word"] * 30)
    service = make_service([bad])
    service.repairer.repair.return_value = bad  # never gets better
    with pytest.raises(ValueError, match="failed validation"):
        service.generate(material.pk)
    material.refresh_from_db()
    assert material.generation_status == GenerationStatus.FAILED
    assert material.output_json is not None
    assert material.validation_result["is_valid"] is False
    assert not GenerationSource.objects.filter(material=material).exists()
    assert service.repairer.repair.call_count == 2  # MATERIAL_MAX_REPAIR_ATTEMPTS


def test_no_context_fails_with_actionable_error():
    material = MarketingMaterialFactory()  # companies without chunks
    service = make_service([valid_output()])
    with pytest.raises(ValueError, match="No processed document chunks"):
        service.generate(material.pk)
    material.refresh_from_db()
    assert material.generation_status == GenerationStatus.FAILED
    assert "sender" in material.error_message


def test_skips_completed_and_processing_without_force():
    for status_value in (GenerationStatus.COMPLETED, GenerationStatus.PROCESSING):
        material = MarketingMaterialFactory(generation_status=status_value)
        service = make_service([valid_output()])
        assert service.generate(material.pk) is False
        material.refresh_from_db()
        assert material.generation_status == status_value  # unchanged


def test_force_reruns_completed_material():
    material = material_with_chunks()
    material.generation_status = GenerationStatus.COMPLETED
    material.save(update_fields=["generation_status"])
    service = make_service([valid_output()])
    assert service.generate(material.pk, force=True) is True


def test_command_skip_exits_zero():
    material = MarketingMaterialFactory(generation_status=GenerationStatus.PROCESSING)
    out = StringIO()
    with mock.patch(
        "collateral_ai.materials.management.commands.generate_material"
        ".MaterialGenerationService",
    ) as service_cls:
        service_cls.return_value.generate.return_value = False
        call_command("generate_material", material_id=material.pk, stdout=out)
    assert "skipped" in out.getvalue()
```

- [ ] **Step 4: Run tests to verify pass**

```bash
docker compose -f docker-compose.local.yml run --rm django pytest collateral_ai/materials -q
```

Expected: PASS (all materials tests).

- [ ] **Step 5: Commit**

```bash
git add backend/collateral_ai/materials
git commit -m "feat(materials): worker 2 orchestrator service + generate_material command"
```

---

### Task 11: Deploy config — Cloud Run generator job

**Files:**
- Modify: `.github/workflows/cd.yml`

**Interfaces:**
- Consumes: the `generate_material` command (Task 10), `MATERIAL_GENERATOR_JOB`/`MATERIAL_GENERATOR_REGION` settings (Task 5).
- Produces: prod wiring — the web service knows the job name; the job exists with `--max-retries 0`.

- [ ] **Step 1: Add the job env var**

In `.github/workflows/cd.yml` `env:` block, after `DOCPROC_JOB`:

```yaml
  MATGEN_JOB: collateral-ai-backend-matgen
```

- [ ] **Step 2: Pass the job name to the web service**

In the `Deploy backend to Cloud Run` step, extend the `--set-env-vars` string — append to the end (before the closing quote):

```
@MATERIAL_GENERATOR_REGION=$REGION@MATERIAL_GENERATOR_JOB=$MATGEN_JOB
```

- [ ] **Step 3: Add the generator job deploy step**

After the `Deploy document-processor Cloud Run Job` step, add:

```yaml
      - name: Deploy material-generator Cloud Run Job
        # Worker 2: generates marketing material JSON. --max-retries 0 is deliberate
        # (unlike docproc): the command exits non-zero on deterministic failures like
        # validation exhaustion, and an automatic re-run would burn 3 more LLM calls
        # and flip a row the UI already shows as failed back to processing. Recovery
        # is the user-facing Regenerate button. (spec §6.6)
        run: |
          gcloud run jobs deploy $MATGEN_JOB \
            --image $AR_REPO/backend:${{ github.sha }} \
            --region $REGION \
            --service-account $RUN_SA_EMAIL \
            --vpc-connector collateral-ai-connector \
            --set-cloudsql-instances ${{ secrets.CLOUD_SQL_CONNECTION_NAME }} \
            --set-secrets DATABASE_URL=database-url:latest,DJANGO_SECRET_KEY=django-secret-key:latest \
            --set-env-vars "^@^DJANGO_SETTINGS_MODULE=config.settings.production@DJANGO_ALLOWED_HOSTS=${{ secrets.DJANGO_ALLOWED_HOSTS }}@DJANGO_ADMIN_URL=${{ secrets.DJANGO_ADMIN_URL }}@DJANGO_GCP_STORAGE_BUCKET_NAME=${{ secrets.DJANGO_GCP_STORAGE_BUCKET_NAME }}@GOOGLE_CLOUD_PROJECT=${{ secrets.GCP_PROJECT_ID }}@VERTEX_LOCATION=$REGION" \
            --command python \
            --args manage.py,generate_material \
            --cpu 1 --memory 1Gi --max-retries 0 --task-timeout 600
```

- [ ] **Step 4: Validate YAML + commit**

```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/cd.yml'))" && echo OK
git add .github/workflows/cd.yml
git commit -m "ci: deploy material-generator Cloud Run Job, wire MATERIAL_GENERATOR_* env"
```

Expected: `OK`.

---

### Task 12: Frontend API layer — schema regen, templates.ts, materials.ts

**Files:**
- Modify: `frontend/src/lib/api/schema.d.ts` (regenerated — never hand-edited)
- Create: `frontend/src/lib/api/templates.ts`
- Create: `frontend/src/lib/api/materials.ts`
- Modify: `frontend/src/lib/api/documents.ts` (append `fetchDocumentViewUrl`)
- Test: `frontend/src/lib/api/templates.test.ts`, `frontend/src/lib/api/materials.test.ts`

**Interfaces:**
- Consumes: backend endpoints (Tasks 3–6), `api` client, schema types.
- Produces (used by every page task):
  - `templates.ts`: `Template`, `TemplateWrite`, `TemplateConstraints`, `TemplateImageSlot`, `templateConstraints(t)`, `templateImageSlots(t)`, `useTemplates()`, `createTemplate(body)`, `useCreateTemplate()`
  - `materials.ts`: `MaterialList`, `MaterialDetail`, `OutputJson`, `ValidationResultJson`, `outputJson(m)`, `validationResult(m)`, `isGenerating(m)`, `MaterialFilters`, `useMaterials(filters)`, `useMaterial(id)`, `createMaterial(body)`, `useCreateMaterial()`, `useUpdateMaterial(id)`, `regenerateMaterial(id)`, `useRegenerateMaterial(id)`, `deleteMaterial(id)`, `useDeleteMaterial()`
  - `documents.ts`: `fetchDocumentViewUrl(companyId, id) -> Promise<string>`

- [ ] **Step 1: Regenerate the OpenAPI types**

```bash
docker compose -f docker-compose.local.yml up -d django postgres
cd frontend && pnpm gen:api
```

Expected: `src/lib/api/schema.d.ts` now contains `"/api/materials/"`, `"/api/templates/"`, `"/api/companies/{company_pk}/documents/{id}/view-url/"` paths and `MaterialList`/`MaterialDetail`/`MaterialCreate`/`Template` component schemas. If the paths are missing, the backend container is running stale code — restart it.

- [ ] **Step 2: Write failing tests**

`frontend/src/lib/api/templates.test.ts`:

```typescript
import { afterEach, describe, expect, it, vi } from "vitest";
import { createTemplate } from "./templates";
import { api } from "./client";

afterEach(() => vi.restoreAllMocks());

describe("createTemplate", () => {
  it("POSTs the template body", async () => {
    const post = vi.spyOn(api, "POST").mockResolvedValue({
      data: { id: 2, slug: "product_spotlight" },
      error: undefined,
    } as never);
    const body = {
      name: "Product Spotlight",
      constraints: {
        headline_max_words: 8,
        subheadline_max_words: 20,
        body_section_count: 2,
        body_section_max_words: 80,
        cta_max_words: 12,
      },
      image_slots: [],
      theme: { primary_color: "#112233", accent_color: "#abcdef" },
    };
    const created = await createTemplate(body);
    expect(post).toHaveBeenCalledWith("/api/templates/", { body });
    expect(created.slug).toBe("product_spotlight");
  });

  it("throws on error", async () => {
    vi.spyOn(api, "POST").mockResolvedValue({
      data: undefined,
      error: { name: ["required"] },
    } as never);
    await expect(createTemplate({} as never)).rejects.toBeTruthy();
  });
});
```

`frontend/src/lib/api/materials.test.ts`:

```typescript
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  createMaterial,
  deleteMaterial,
  isGenerating,
  regenerateMaterial,
} from "./materials";
import { api } from "./client";

afterEach(() => vi.restoreAllMocks());

describe("isGenerating", () => {
  it("is true for queued and processing, false for terminal states", () => {
    expect(isGenerating({ generation_status: "queued" })).toBe(true);
    expect(isGenerating({ generation_status: "processing" })).toBe(true);
    expect(isGenerating({ generation_status: "completed" })).toBe(false);
    expect(isGenerating({ generation_status: "failed" })).toBe(false);
  });
});

describe("createMaterial", () => {
  it("POSTs and returns the detail payload", async () => {
    const post = vi.spyOn(api, "POST").mockResolvedValue({
      data: { id: 9, generation_status: "queued" },
      error: undefined,
    } as never);
    const body = {
      title: "T",
      sender_company: 1,
      receiver_company: 2,
      template: 3,
      prompt: "p",
    };
    const material = await createMaterial(body);
    expect(post).toHaveBeenCalledWith("/api/materials/", { body });
    expect(material.id).toBe(9);
  });

  it("throws the DRF error body so forms can show field errors", async () => {
    vi.spyOn(api, "POST").mockResolvedValue({
      data: undefined,
      error: { receiver_company: ["Sender and receiver must be different companies."] },
    } as never);
    await expect(
      createMaterial({
        title: "T",
        sender_company: 1,
        receiver_company: 1,
        template: 3,
        prompt: "p",
      }),
    ).rejects.toHaveProperty("receiver_company");
  });
});

describe("regenerateMaterial / deleteMaterial", () => {
  it("POSTs the regenerate action", async () => {
    const post = vi.spyOn(api, "POST").mockResolvedValue({
      data: { id: 9, generation_status: "queued" },
      error: undefined,
    } as never);
    await regenerateMaterial(9);
    expect(post).toHaveBeenCalledWith("/api/materials/{id}/regenerate/", {
      params: { path: { id: 9 } },
    });
  });

  it("DELETEs the material", async () => {
    const del = vi
      .spyOn(api, "DELETE")
      .mockResolvedValue({ data: undefined, error: undefined } as never);
    await deleteMaterial(9);
    expect(del).toHaveBeenCalledWith("/api/materials/{id}/", {
      params: { path: { id: 9 } },
    });
  });
});
```

Run: `cd frontend && pnpm test` — expected: FAIL (modules don't exist).

- [ ] **Step 3: Implement templates.ts**

`frontend/src/lib/api/templates.ts`:

```typescript
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { components } from "./schema";
import { api } from "./client";

export type Template = components["schemas"]["Template"];

export type TemplateConstraints = {
  headline_max_words: number;
  subheadline_max_words: number;
  body_section_count: number;
  body_section_max_words: number;
  cta_max_words: number;
};

export type TemplateImageSlot = {
  slot_id: string;
  label: string;
  spec: string;
  source: "sender" | "receiver" | "generated_placeholder";
};

/** constraints/image_slots are loose JSON fields in the schema; cast through the contract. */
export function templateConstraints(t: Template): TemplateConstraints {
  return t.constraints as TemplateConstraints;
}

export function templateImageSlots(t: Template): TemplateImageSlot[] {
  return (t.image_slots ?? []) as TemplateImageSlot[];
}

export type TemplateWrite = {
  name: string;
  description?: string;
  constraints: TemplateConstraints;
  image_slots: TemplateImageSlot[] | [];
  theme: { primary_color: string; accent_color: string };
};

export function useTemplates() {
  return useQuery({
    queryKey: ["templates"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/templates/");
      if (error) throw error;
      return data;
    },
  });
}

export async function createTemplate(body: TemplateWrite): Promise<Template> {
  const { data, error } = await api.POST("/api/templates/", {
    // Same cast pattern as companies.ts: DRF's schema reuses the response
    // entity as the request body type.
    body: body as unknown as Template,
  });
  if (error || !data) throw error ?? new Error("create_failed");
  return data;
}

export function useCreateTemplate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createTemplate,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["templates"] }),
  });
}
```

- [ ] **Step 4: Implement materials.ts + the documents fetcher**

`frontend/src/lib/api/materials.ts`:

```typescript
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { components } from "./schema";
import { api } from "./client";

export type MaterialList = components["schemas"]["MaterialList"];
export type MaterialDetail = components["schemas"]["MaterialDetail"];

/** The output JSON contract (spec §4). output_json is loose JSON in the schema. */
export type OutputJson = {
  template_id: string;
  theme: { primary_color: string; accent_color: string };
  article: {
    headline: string;
    subheadline: string;
    body_sections: { title: string; text: string }[];
    cta: string;
  };
  image_slots: { slot_id: string; description: string; source: string }[];
  source_references: { source_id: string; used_fact: string }[];
};

export type ValidationResultJson = {
  is_valid: boolean;
  errors: { category: string; message: string }[];
};

export function outputJson(m: MaterialDetail): OutputJson | null {
  return (m.output_json as OutputJson | null) ?? null;
}

export function validationResult(m: MaterialDetail): ValidationResultJson | null {
  return (m.validation_result as ValidationResultJson | null) ?? null;
}

export function isGenerating(m: { generation_status: string }): boolean {
  return m.generation_status === "queued" || m.generation_status === "processing";
}

export type MaterialFilters = {
  company?: number;
  sender?: number;
  receiver?: number;
  generation_status?: string;
  review_status?: string;
  search?: string;
};

export function useMaterials(filters: MaterialFilters = {}) {
  return useQuery({
    queryKey: ["materials", filters],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/materials/", {
        params: { query: filters },
      });
      if (error) throw error;
      return data;
    },
    // Poll while anything is generating; stop on terminal states (spec §7.2).
    refetchInterval: (query) =>
      (query.state.data ?? []).some(isGenerating) ? 3000 : false,
  });
}

export function useMaterial(id: number) {
  return useQuery({
    queryKey: ["materials", id],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/materials/{id}/", {
        params: { path: { id } },
      });
      if (error) throw error;
      return data;
    },
    refetchInterval: (query) => {
      const material = query.state.data;
      return material && isGenerating(material) ? 3000 : false;
    },
  });
}

export type MaterialCreateBody = {
  title: string;
  description?: string;
  sender_company: number;
  receiver_company: number;
  template: number;
  prompt: string;
  tone?: string;
  cta_style?: string;
  language?: string;
};

export async function createMaterial(body: MaterialCreateBody): Promise<MaterialDetail> {
  const { data, error } = await api.POST("/api/materials/", {
    body: body as unknown as components["schemas"]["MaterialCreate"],
  });
  // Throw the DRF error body itself so the wizard can show field errors.
  if (error || !data) throw error ?? new Error("create_failed");
  return data as MaterialDetail;
}

export function useCreateMaterial() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createMaterial,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["materials"] }),
  });
}

export type MaterialUpdateBody = {
  title?: string;
  description?: string;
  prompt?: string;
  review_status?: "pending" | "approved" | "rejected";
};

export function useUpdateMaterial(id: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: MaterialUpdateBody) => {
      const { data, error } = await api.PATCH("/api/materials/{id}/", {
        params: { path: { id } },
        body: body as components["schemas"]["PatchedMaterialUpdate"],
      });
      if (error || !data) throw error ?? new Error("update_failed");
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["materials"] });
      qc.invalidateQueries({ queryKey: ["materials", id] });
    },
  });
}

export async function regenerateMaterial(id: number): Promise<MaterialDetail> {
  const { data, error } = await api.POST("/api/materials/{id}/regenerate/", {
    params: { path: { id } },
  });
  if (error || !data) throw error ?? new Error("regenerate_failed");
  return data as MaterialDetail;
}

export function useRegenerateMaterial(id: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => regenerateMaterial(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["materials"] });
      qc.invalidateQueries({ queryKey: ["materials", id] });
    },
  });
}

export async function deleteMaterial(id: number): Promise<void> {
  const { error } = await api.DELETE("/api/materials/{id}/", {
    params: { path: { id } },
  });
  if (error) throw new Error("delete_failed");
}

export function useDeleteMaterial() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteMaterial,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["materials"] }),
  });
}
```

Append to `frontend/src/lib/api/documents.ts`:

```typescript
export async function fetchDocumentViewUrl(companyId: number, id: number): Promise<string> {
  const { data, error } = await api.GET(
    "/api/companies/{company_pk}/documents/{id}/view-url/",
    { params: { path: { company_pk: companyId, id } } },
  );
  if (error || !data) throw new Error("view_url_failed");
  return data.url;
}
```

- [ ] **Step 5: Run tests + typecheck, commit**

```bash
cd frontend && pnpm test && pnpm typecheck
git add frontend/src/lib/api
git commit -m "feat(frontend): typed materials/templates API hooks + document view-url fetcher"
```

Expected: all vitest suites PASS, `tsc` clean.

---

### Task 13: Status pill — material states + review tokens

**Files:**
- Modify: `frontend/src/index.css` (two tokens)
- Modify: `frontend/src/components/status-pill.tsx`
- Test: `frontend/src/components/status-pill.test.ts`

**Interfaces:**
- Consumes: `generation_status`/`review_status` strings.
- Produces: `materialPillStatus(m: {generation_status: string; review_status: string}) -> "processing" | "failed" | "needs_review" | "approved" | "rejected"`; `StatusPill` renders all five; tokens `text-review` / `bg-review-soft`.

- [ ] **Step 1: Write failing test**

`frontend/src/components/status-pill.test.ts`:

```typescript
import { describe, expect, it } from "vitest";
import { materialPillStatus } from "./status-pill";

describe("materialPillStatus", () => {
  it.each([
    ["queued", "pending", "processing"],
    ["processing", "pending", "processing"],
    ["failed", "pending", "failed"],
    ["completed", "pending", "needs_review"],
    ["completed", "approved", "approved"],
    ["completed", "rejected", "rejected"],
  ])("(%s, %s) -> %s", (generation, review, expected) => {
    expect(
      materialPillStatus({ generation_status: generation, review_status: review }),
    ).toBe(expected);
  });
});
```

Run: `cd frontend && pnpm test` — expected: FAIL (`materialPillStatus` not exported).

- [ ] **Step 2: Implement**

In `frontend/src/index.css`, add inside the first `@theme` block (after `--color-danger-soft`):

```css
  --color-review: #7c3aed;       /* Needs-review pill (design violet) */
  --color-review-soft: #f1eafe;
```

Replace `frontend/src/components/status-pill.tsx` with:

```tsx
import { CheckCircle, CircleNotch, Flag, Prohibit, XCircle } from "@phosphor-icons/react";

const MAP: Record<string, { label: string; cls: string; Icon: typeof CheckCircle }> = {
  processed: { label: "Processed", cls: "text-success bg-success-soft", Icon: CheckCircle },
  processing: { label: "Processing", cls: "text-warning bg-warning-soft", Icon: CircleNotch },
  pending: { label: "Processing", cls: "text-warning bg-warning-soft", Icon: CircleNotch },
  failed: { label: "Failed", cls: "text-destructive bg-danger-soft", Icon: XCircle },
  needs_review: { label: "Needs review", cls: "text-review bg-review-soft", Icon: Flag },
  approved: { label: "Approved", cls: "text-success bg-success-soft", Icon: CheckCircle },
  rejected: { label: "Rejected", cls: "text-destructive bg-danger-soft", Icon: Prohibit },
};

/** Derived pill for materials (spec §3.2): two status fields → one pill. */
export function materialPillStatus(m: {
  generation_status: string;
  review_status: string;
}): "processing" | "failed" | "needs_review" | "approved" | "rejected" {
  if (m.generation_status === "failed") return "failed";
  if (m.generation_status !== "completed") return "processing";
  if (m.review_status === "approved") return "approved";
  if (m.review_status === "rejected") return "rejected";
  return "needs_review";
}

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

- [ ] **Step 3: Run tests, commit**

```bash
cd frontend && pnpm test && pnpm typecheck
git add frontend/src/index.css frontend/src/components/status-pill.tsx frontend/src/components/status-pill.test.ts
git commit -m "feat(frontend): material status pill states + review tokens"
```

---

### Task 14: Display components — newsletter preview, JSON view, sources

**Files:**
- Create: `frontend/src/components/newsletter-preview.tsx`
- Create: `frontend/src/components/material-json.tsx`
- Create: `frontend/src/components/material-sources.tsx`

**Interfaces:**
- Consumes: `MaterialDetail`, `OutputJson` (Task 12), `templateImageSlots` (Task 12), `fetchDocumentViewUrl` (Task 12), `CompanyLogo` (exists).
- Produces: `<NewsletterPreview material output />`, `<MaterialJson value />`, `<MaterialSources material />` — all pure display, assembled by Task 15.

- [ ] **Step 1: Implement the newsletter preview**

`frontend/src/components/newsletter-preview.tsx`:

```tsx
import { CalendarCheck } from "@phosphor-icons/react";

import { CompanyLogo } from "@/components/company-logo";
import type { MaterialDetail, OutputJson } from "@/lib/api/materials";
import { templateImageSlots } from "@/lib/api/templates";

/** Generic slot rendering (spec §7.3) so builder-created templates work:
 *  slots render in template order — the first generated_placeholder slot is the
 *  hero block; sender/receiver slots are floating CompanyLogo chips; any further
 *  generated_placeholder slots render as smaller striped blocks. */
export function NewsletterPreview({
  material,
  output,
}: {
  material: MaterialDetail;
  output: OutputJson;
}) {
  const theme = output.theme;
  const templateSlots = templateImageSlots(material.template);
  const slotMeta = new Map(templateSlots.map((s) => [s.slot_id, s]));
  const ordered = templateSlots
    .map((t) => output.image_slots.find((s) => s.slot_id === t.slot_id))
    .filter((s): s is OutputJson["image_slots"][number] => Boolean(s));

  const heroIndex = ordered.findIndex((s) => s.source === "generated_placeholder");
  const hero = heroIndex >= 0 ? ordered[heroIndex] : null;
  const logoSlots = ordered.filter((s) => s.source === "sender" || s.source === "receiver");
  const extras = ordered.filter(
    (s, i) => s.source === "generated_placeholder" && i !== heroIndex,
  );

  const stripe = {
    backgroundImage:
      "repeating-linear-gradient(45deg, #ececf0 0 10px, #f6f6f8 10px 20px)",
  };
  const slotCaption = (slotId: string) => {
    const meta = slotMeta.get(slotId);
    return meta ? `${meta.label} · ${meta.spec}` : slotId;
  };

  return (
    <div className="mx-auto max-w-[460px] overflow-hidden rounded-2xl border border-hairline bg-surface shadow-[0_8px_30px_-12px_rgba(20,20,40,0.25)]">
      {hero && (
        <div className="relative flex h-[170px] items-end justify-center" style={stripe}>
          <span className="mb-3 rounded-md bg-surface/90 px-2 py-1 text-[11px] text-mute">
            {slotCaption(hero.slot_id)}
          </span>
          {logoSlots.length > 0 && (
            <div className="absolute left-4 top-4 flex gap-2">
              {logoSlots.map((slot) => {
                const company =
                  slot.source === "sender" ? material.sender_company : material.receiver_company;
                return (
                  <span
                    key={slot.slot_id}
                    className="rounded-xl bg-surface p-1 shadow-sm"
                    title={slotCaption(slot.slot_id)}
                  >
                    <CompanyLogo name={company.name} logoUrl={company.logo_url} size={32} />
                  </span>
                );
              })}
            </div>
          )}
        </div>
      )}
      <div className="p-6">
        <div
          className="text-[11px] font-semibold uppercase tracking-wide"
          style={{ color: theme.primary_color }}
        >
          {material.sender_company.name} × {material.receiver_company.name}
        </div>
        <h2
          className="mt-2 text-[22px] font-bold leading-tight"
          style={{ color: theme.accent_color }}
        >
          {output.article.headline}
        </h2>
        <p className="mt-2 text-[13.5px] text-subtext">{output.article.subheadline}</p>
        {output.article.body_sections.map((section, i) => (
          <div key={i} className="mt-4">
            <h3 className="text-[13px] font-semibold text-ink">{section.title}</h3>
            <p className="mt-1 text-[13px] leading-relaxed text-body">{section.text}</p>
          </div>
        ))}
        {extras.map((slot) => (
          <div
            key={slot.slot_id}
            className="mt-4 flex h-[90px] items-center justify-center rounded-lg"
            style={stripe}
          >
            <span className="rounded-md bg-surface/90 px-2 py-1 text-[11px] text-mute">
              {slotCaption(slot.slot_id)}
            </span>
          </div>
        ))}
        <div
          className="mt-5 flex items-center gap-2 rounded-xl px-4 py-3 text-[13px] font-semibold"
          style={{ background: `${theme.primary_color}14`, color: theme.primary_color }}
        >
          <CalendarCheck size={16} weight="fill" />
          {output.article.cta}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Implement the JSON view**

`frontend/src/components/material-json.tsx`:

```tsx
import type { ReactNode } from "react";

// Design §7 Layout JSON coloring: keys #7c3aed, strings #15803d,
// numbers #b45309, booleans/null #0369a1.
const TOKEN_RE = /("(?:[^"\\]|\\.)*")(\s*:)?|\b(?:true|false|null)\b|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?/g;

function colorize(json: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  let last = 0;
  let key = 0;
  for (const match of json.matchAll(TOKEN_RE)) {
    const [full, str, colon] = match;
    const start = match.index ?? 0;
    if (start > last) nodes.push(json.slice(last, start));
    let color = "#0369a1";
    if (str) color = colon ? "#7c3aed" : "#15803d";
    else if (/^-?\d/.test(full)) color = "#b45309";
    nodes.push(
      <span key={key++} style={{ color }}>
        {str ?? full}
      </span>,
    );
    if (str && colon) nodes.push(colon);
    last = start + full.length;
  }
  nodes.push(json.slice(last));
  return nodes;
}

export function MaterialJson({ value }: { value: unknown }) {
  const json = JSON.stringify(value, null, 2) ?? "null";
  return (
    <pre className="overflow-x-auto rounded-xl bg-[#fbfbfd] p-4 font-mono text-[12px] leading-[1.75] text-body">
      {colorize(json)}
    </pre>
  );
}
```

- [ ] **Step 3: Implement the sources panel**

`frontend/src/components/material-sources.tsx`:

```tsx
import type { ReactNode } from "react";
import { ArrowDownLeft, ArrowSquareOut, ArrowUpRight, FilePdf } from "@phosphor-icons/react";

import { fetchDocumentViewUrl } from "@/lib/api/documents";
import type { MaterialDetail } from "@/lib/api/materials";

type Source = MaterialDetail["sources"][number];

async function openSource(source: Source) {
  try {
    const url = await fetchDocumentViewUrl(source.document.company, source.document.id);
    const suffix = source.page_number ? `#page=${source.page_number}` : "";
    window.open(url + suffix, "_blank", "noopener");
  } catch {
    // Viewing is unavailable when GCS isn't configured (503) — nothing to open.
  }
}

function SourceCard({ source }: { source: Source }) {
  return (
    <div className="rounded-[11px] border border-hairline p-3">
      <div className="flex items-center gap-2">
        <FilePdf size={16} className="shrink-0 text-danger" />
        <span className="min-w-0 truncate text-[12.5px] font-semibold text-ink">
          {source.document.file_name}
        </span>
        {source.page_number != null && (
          <span className="font-mono text-[11px] text-mute">p.{source.page_number}</span>
        )}
        <button
          type="button"
          onClick={() => void openSource(source)}
          className="ml-auto text-mute hover:text-brand"
          aria-label={`Open ${source.document.file_name}`}
        >
          <ArrowSquareOut size={15} />
        </button>
      </div>
      {source.snippet && (
        <p className="mt-2 text-[12px] italic leading-relaxed text-subtext">
          “{source.snippet}”
        </p>
      )}
      {source.used_fact && (
        <p className="mt-1 text-[11.5px] text-mute">Used: {source.used_fact}</p>
      )}
    </div>
  );
}

function SourceColumn({
  title,
  badge,
  sources,
}: {
  title: string;
  badge: ReactNode;
  sources: Source[];
}) {
  return (
    <div>
      <div className="mb-2 flex items-center gap-2 text-[12.5px] font-semibold text-ink">
        {badge}
        {title}
      </div>
      <div className="flex flex-col gap-2">
        {sources.length === 0 && <p className="text-[12px] text-mute">No sources cited.</p>}
        {sources.map((s) => (
          <SourceCard key={s.id} source={s} />
        ))}
      </div>
    </div>
  );
}

export function MaterialSources({ material }: { material: MaterialDetail }) {
  const sender = material.sources.filter((s) => s.source_role === "sender");
  const receiver = material.sources.filter((s) => s.source_role === "receiver");
  return (
    <div>
      <p className="mb-3 text-[12.5px] text-subtext">
        Every claim is grounded in these document excerpts.
      </p>
      <div className="grid grid-cols-2 gap-5">
        <SourceColumn
          title={`Sender — ${material.sender_company.name}`}
          badge={<ArrowUpRight size={14} className="text-brand" weight="bold" />}
          sources={sender}
        />
        <SourceColumn
          title={`Receiver — ${material.receiver_company.name}`}
          badge={<ArrowDownLeft size={14} className="text-review" weight="bold" />}
          sources={receiver}
        />
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Typecheck + lint, commit**

```bash
cd frontend && pnpm typecheck && pnpm lint
git add frontend/src/components
git commit -m "feat(frontend): newsletter preview, JSON view, sources components"
```

---

### Task 15: Material detail page (Result Detail)

**Files:**
- Create: `frontend/src/routes/material-detail.tsx`
- Modify: `frontend/src/router.tsx` (register `/materials/$materialId`)

**Interfaces:**
- Consumes: Tasks 12–14 exports; `AlertDialog` primitives; `useDebouncedValue` not needed here.
- Produces: `MaterialDetailPage` at `/materials/$materialId` (route id `/app/materials/$materialId`).

- [ ] **Step 1: Implement the page**

`frontend/src/routes/material-detail.tsx`:

```tsx
import { useState } from "react";
import { Link, useNavigate, useParams } from "@tanstack/react-router";
import {
  ArrowsClockwise,
  CaretRight,
  Check,
  CheckCircle,
  CircleNotch,
  Copy,
  PencilSimple,
  Prohibit,
  Trash,
  XCircle,
} from "@phosphor-icons/react";

import { MaterialJson } from "@/components/material-json";
import { MaterialSources } from "@/components/material-sources";
import { NewsletterPreview } from "@/components/newsletter-preview";
import { StatusPill, materialPillStatus } from "@/components/status-pill";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import {
  isGenerating,
  outputJson,
  useDeleteMaterial,
  useMaterial,
  useRegenerateMaterial,
  useUpdateMaterial,
  validationResult,
  type MaterialDetail,
} from "@/lib/api/materials";
import { templateConstraints } from "@/lib/api/templates";

const TABS = ["Preview", "Layout JSON", "Sources"] as const;
type Tab = (typeof TABS)[number];

const STALE_MS = 15 * 60 * 1000; // spec §5.2: stuck-row escape hatch

const words = (s: string) => (s ? s.trim().split(/\s+/).length : 0);

const QUALITY_CHECKS: [string, string][] = [
  ["structure", "JSON schema valid"],
  ["word_limit", "Word limits passed"],
  ["image_slot", "Image slots present"],
  ["source", "Sources attached"],
];

function RailCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-hairline bg-surface p-4">
      <h3 className="mb-3 text-[12px] font-semibold uppercase tracking-wide text-faint">
        {title}
      </h3>
      {children}
    </div>
  );
}

function QualityChecks({ material }: { material: MaterialDetail }) {
  const result = validationResult(material);
  if (!result) return <p className="text-[12px] text-mute">No validation run yet.</p>;
  const failing = new Set(result.errors.map((e) => e.category));
  return (
    <div className="flex flex-col gap-2">
      {QUALITY_CHECKS.map(([category, label]) => {
        const ok = !failing.has(category);
        return (
          <div key={category} className="flex items-center gap-2 text-[12.5px] text-body">
            {ok ? (
              <CheckCircle size={17} weight="fill" className="text-success" />
            ) : (
              <XCircle size={17} weight="fill" className="text-destructive" />
            )}
            {label}
          </div>
        );
      })}
    </div>
  );
}

function ConstraintMeters({ material }: { material: MaterialDetail }) {
  const output = outputJson(material);
  if (!output) return null;
  const constraints = templateConstraints(material.template);
  const meters = [
    { label: "Headline", used: words(output.article.headline), limit: constraints.headline_max_words },
    { label: "Subheadline", used: words(output.article.subheadline), limit: constraints.subheadline_max_words },
    ...output.article.body_sections.map((section) => ({
      label: `Body · ${section.title}`,
      used: words(section.text),
      limit: constraints.body_section_max_words,
    })),
    { label: "CTA", used: words(output.article.cta), limit: constraints.cta_max_words },
  ];
  return (
    <div className="flex flex-col gap-3">
      {meters.map((meter) => {
        const ratio = meter.limit ? meter.used / meter.limit : 0;
        const amber = ratio >= 2 / 3; // reproduces the design's examples (spec §7.3)
        return (
          <div key={meter.label}>
            <div className="mb-1 flex items-center justify-between text-[11.5px]">
              <span className={amber ? "text-warning" : "text-body"}>{meter.label}</span>
              <span className="font-mono text-mute">
                {meter.used}/{meter.limit}
              </span>
            </div>
            <div className="h-[5px] rounded-full bg-[#f0f0f2]">
              <div
                className={`h-full rounded-full ${amber ? "bg-[#e0a83b]" : "bg-success"}`}
                style={{ width: `${Math.min(100, ratio * 100)}%` }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function EditPromptDialog({ material }: { material: MaterialDetail }) {
  const [prompt, setPrompt] = useState(material.prompt);
  const update = useUpdateMaterial(material.id);
  return (
    <AlertDialog>
      <AlertDialogTrigger className="flex items-center gap-[7px] rounded-[10px] border border-field bg-surface px-[14px] py-[9px] text-[13px] font-semibold text-body hover:bg-subtle">
        <PencilSimple size={15} />
        Edit prompt
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Edit prompt</AlertDialogTitle>
          <AlertDialogDescription>
            Saving does not regenerate — use Regenerate afterwards to apply it.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          rows={5}
          className="w-full rounded-[10px] border border-field bg-subtle p-3 text-[13px] text-body outline-none focus:border-brand"
        />
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction onClick={() => update.mutate({ prompt })}>Save</AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

export function MaterialDetailPage() {
  const { materialId } = useParams({ from: "/app/materials/$materialId" });
  const { data: material, isLoading, isError } = useMaterial(Number(materialId));
  const navigate = useNavigate();
  const [tab, setTab] = useState<Tab>("Preview");
  const update = useUpdateMaterial(Number(materialId));
  const regenerate = useRegenerateMaterial(Number(materialId));
  const del = useDeleteMaterial();

  if (isLoading) {
    return <div className="mx-auto max-w-[1120px] px-10 pt-8 text-sm text-mute">Loading…</div>;
  }
  if (isError || !material) {
    return (
      <div className="mx-auto max-w-[1120px] px-10 pt-8">
        <p className="text-sm text-destructive">Material not found.</p>
        <Link to="/materials" className="mt-2 inline-block text-sm text-brand">
          Back to marketing requests
        </Link>
      </div>
    );
  }

  const output = outputJson(material);
  const generating = isGenerating(material);
  const stale = Date.now() - new Date(material.updated_at).getTime() > STALE_MS;
  const completed = material.generation_status === "completed";
  const copyJson = () =>
    void navigator.clipboard.writeText(JSON.stringify(material.output_json, null, 2));
  const setReview = (value: "approved" | "rejected") =>
    update.mutate({
      review_status: material.review_status === value ? "pending" : value,
    });

  return (
    <div className="mx-auto max-w-[1120px] px-10 pb-[60px] pt-8">
      <div className="mb-[18px] flex items-center gap-[7px] text-[12.5px] text-mute">
        <Link to="/materials" className="hover:text-brand">
          Marketing Requests
        </Link>
        <CaretRight size={11} />
        <span className="font-medium text-body">{material.title}</span>
      </div>

      <div className="mb-6 flex flex-wrap items-center gap-3">
        <h1 className="text-[23px] font-bold tracking-[-0.02em] text-ink">{material.title}</h1>
        <StatusPill status={materialPillStatus(material)} />
        <div className="ml-auto flex items-center gap-[9px]">
          <button
            type="button"
            disabled={(generating && !stale) || regenerate.isPending}
            onClick={() => regenerate.mutate()}
            className="flex items-center gap-[7px] rounded-[10px] border border-field bg-surface px-[14px] py-[9px] text-[13px] font-semibold text-body hover:bg-subtle disabled:opacity-50"
          >
            <ArrowsClockwise size={15} />
            Regenerate
          </button>
          <EditPromptDialog material={material} />
          {completed && (
            <>
              <button
                type="button"
                onClick={() => setReview("approved")}
                className={`flex items-center gap-[7px] rounded-[10px] px-[14px] py-[9px] text-[13px] font-semibold ${
                  material.review_status === "approved"
                    ? "bg-success text-white"
                    : "bg-[#16a34a] text-white hover:bg-[#128a3f]"
                }`}
              >
                <Check size={15} weight="bold" />
                {material.review_status === "approved" ? "Approved" : "Mark approved"}
              </button>
              <button
                type="button"
                onClick={() => setReview("rejected")}
                className="flex items-center gap-[7px] rounded-[10px] border border-field bg-surface px-[14px] py-[9px] text-[13px] font-semibold text-destructive hover:bg-subtle"
              >
                <Prohibit size={15} />
                {material.review_status === "rejected" ? "Rejected" : "Reject"}
              </button>
            </>
          )}
        </div>
      </div>
      <div className="-mt-4 mb-6 text-[12.5px] text-subtext">
        <span className="font-semibold text-body">{material.sender_company.name}</span>
        {" → "}
        <span className="font-semibold text-body">{material.receiver_company.name}</span>
        {" · "}
        <span className="font-mono">{material.template_slug}</span>
        {material.completed_at && ` · Generated ${new Date(material.completed_at).toLocaleString()}`}
      </div>

      {material.generation_status === "failed" && (
        <div className="mb-5 rounded-xl border border-danger/30 bg-danger-soft p-4 text-[13px] text-destructive">
          <strong>Generation failed:</strong> {material.error_message || "Unknown error."}
          {/* JSON tab stays accessible below when output_json exists (spec §7.3). */}
        </div>
      )}

      {generating ? (
        <div className="flex flex-col items-center gap-3 rounded-2xl border border-hairline bg-surface py-20">
          <CircleNotch size={28} className="animate-spin text-brand" />
          <p className="text-[13.5px] text-body">Generating material…</p>
          <p className="text-[12px] text-mute">
            This usually takes under a minute. The page updates automatically.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-[1fr_320px] items-start gap-[22px]">
          <div className="rounded-2xl border border-hairline bg-surface">
            <div className="flex items-center gap-5 border-b border-hairline px-5">
              {TABS.map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => setTab(t)}
                  className={`-mb-px border-b-2 py-[12px] text-[13px] font-medium ${
                    tab === t
                      ? "border-brand text-brand"
                      : "border-transparent text-mute hover:text-body"
                  }`}
                >
                  {t}
                </button>
              ))}
              {tab === "Layout JSON" && (
                <button
                  type="button"
                  onClick={copyJson}
                  className="ml-auto flex items-center gap-1 text-[12px] text-brand"
                >
                  <Copy size={13} /> Copy
                </button>
              )}
            </div>
            <div className="p-5">
              {tab === "Preview" &&
                (output ? (
                  <NewsletterPreview material={material} output={output} />
                ) : (
                  <p className="text-[13px] text-mute">No output to preview.</p>
                ))}
              {tab === "Layout JSON" &&
                (material.output_json ? (
                  <MaterialJson value={material.output_json} />
                ) : (
                  <p className="text-[13px] text-mute">No JSON stored.</p>
                ))}
              {tab === "Sources" && <MaterialSources material={material} />}
            </div>
          </div>

          <div className="flex flex-col gap-4">
            <RailCard title="Quality checks">
              <QualityChecks material={material} />
            </RailCard>
            {output && (
              <RailCard title="Constraint meters">
                <ConstraintMeters material={material} />
              </RailCard>
            )}
            <RailCard title="Actions">
              <div className="flex flex-col gap-2">
                <button
                  type="button"
                  onClick={copyJson}
                  disabled={!material.output_json}
                  className="flex items-center gap-[7px] rounded-[10px] border border-field bg-surface px-[14px] py-[9px] text-[13px] font-semibold text-body hover:bg-subtle disabled:opacity-50"
                >
                  <Copy size={15} />
                  Copy JSON
                </button>
                <AlertDialog>
                  <AlertDialogTrigger className="flex items-center gap-[7px] rounded-[10px] border border-field bg-surface px-[14px] py-[9px] text-[13px] font-semibold text-destructive hover:bg-subtle">
                    <Trash size={15} />
                    Delete material
                  </AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>Delete material?</AlertDialogTitle>
                      <AlertDialogDescription>
                        This removes the generated content, layout JSON and source
                        references. This can't be undone.
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel>Cancel</AlertDialogCancel>
                      <AlertDialogAction
                        onClick={() =>
                          del.mutate(material.id, {
                            onSuccess: () => navigate({ to: "/materials" }),
                          })
                        }
                      >
                        Delete
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              </div>
            </RailCard>
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Register the route**

In `frontend/src/router.tsx`: add `import { MaterialDetailPage } from "@/routes/material-detail";`, then after `materialsRoute`:

```tsx
const materialDetailRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/materials/$materialId",
  component: MaterialDetailPage,
});
```

and add `materialDetailRoute` to the `appRoute.addChildren([...])` array (after `materialsRoute`).

- [ ] **Step 3: Typecheck + lint + tests, commit**

```bash
cd frontend && pnpm typecheck && pnpm lint && pnpm test
git add frontend/src/routes/material-detail.tsx frontend/src/router.tsx
git commit -m "feat(frontend): material result detail page with preview/JSON/sources + review actions"
```

---

### Task 16: Generated Materials tab (company detail)

**Files:**
- Create: `frontend/src/components/materials-tab.tsx`
- Modify: `frontend/src/routes/company-detail.tsx` (replace "Coming soon")

**Interfaces:**
- Consumes: `useMaterials`, `MaterialList` (Task 12), `StatusPill`/`materialPillStatus` (Task 13), the `/materials/$materialId` route (Task 15 — must exist for the typed `Link` to typecheck).
- Produces: `<MaterialsTab companyId={number} />`.

- [ ] **Step 1: Implement the tab component**

`frontend/src/components/materials-tab.tsx`:

```tsx
import type { ReactNode } from "react";
import { Link } from "@tanstack/react-router";
import { ArrowDownLeft, ArrowUpRight } from "@phosphor-icons/react";

import { StatusPill, materialPillStatus } from "@/components/status-pill";
import { useMaterials, type MaterialList } from "@/lib/api/materials";

function MaterialCard({
  material,
  counterpart,
}: {
  material: MaterialList;
  counterpart: string;
}) {
  return (
    <Link
      to="/materials/$materialId"
      params={{ materialId: String(material.id) }}
      className="flex items-center justify-between gap-3 rounded-[11px] border border-hairline p-[13px] hover:border-[#d8d8f2] hover:bg-[#fbfbff]"
    >
      <div className="min-w-0">
        <div className="truncate text-[13.5px] font-semibold text-ink">{material.title}</div>
        <div className="mt-[2px] truncate text-[12px] text-subtext">{counterpart}</div>
      </div>
      <StatusPill status={materialPillStatus(material)} />
    </Link>
  );
}

function Column({
  title,
  tile,
  children,
}: {
  title: string;
  tile: ReactNode;
  children: ReactNode;
}) {
  return (
    <div>
      <div className="mb-3 flex items-center gap-[9px]">
        {tile}
        <h3 className="text-[13.5px] font-semibold text-ink">{title}</h3>
      </div>
      <div className="flex flex-col gap-2">{children}</div>
    </div>
  );
}

export function MaterialsTab({ companyId }: { companyId: number }) {
  const { data: materials, isLoading, isError } = useMaterials({ company: companyId });

  if (isLoading) return <p className="text-[13px] text-mute">Loading…</p>;
  if (isError) return <p className="text-[13px] text-destructive">Failed to load materials.</p>;

  const all = materials ?? [];
  const asSender = all.filter((m) => m.sender_company.id === companyId);
  const asReceiver = all.filter((m) => m.receiver_company.id === companyId);

  return (
    <div className="grid grid-cols-2 gap-6">
      <Column
        title="As Sender"
        tile={
          <span className="flex size-[26px] items-center justify-center rounded-lg bg-brand-soft text-brand">
            <ArrowUpRight size={14} weight="bold" />
          </span>
        }
      >
        {asSender.length === 0 && (
          <p className="text-[12.5px] text-mute">No materials sent by this company yet.</p>
        )}
        {asSender.map((m) => (
          <MaterialCard key={m.id} material={m} counterpart={`→ ${m.receiver_company.name}`} />
        ))}
      </Column>
      <Column
        title="As Receiver"
        tile={
          <span className="flex size-[26px] items-center justify-center rounded-lg bg-review-soft text-review">
            <ArrowDownLeft size={14} weight="bold" />
          </span>
        }
      >
        {asReceiver.length === 0 && (
          <p className="text-[12.5px] text-mute">No materials targeting this company yet.</p>
        )}
        {asReceiver.map((m) => (
          <MaterialCard key={m.id} material={m} counterpart={`${m.sender_company.name} →`} />
        ))}
      </Column>
    </div>
  );
}
```

- [ ] **Step 2: Wire it into the company detail page**

In `frontend/src/routes/company-detail.tsx`: add `import { MaterialsTab } from "@/components/materials-tab";` and replace

```tsx
      {tab === "Generated Materials" && (
        <p className="text-[13px] text-mute">Coming soon.</p>
      )}
```

with

```tsx
      {tab === "Generated Materials" && <MaterialsTab companyId={Number(companyId)} />}
```

- [ ] **Step 3: Typecheck + lint, commit**

```bash
cd frontend && pnpm typecheck && pnpm lint && pnpm test
git add frontend/src/components/materials-tab.tsx frontend/src/routes/company-detail.tsx
git commit -m "feat(frontend): Generated Materials tab on company detail"
```

---

### Task 17: Global Marketing Requests page (`/materials`)

**Files:**
- Modify: `frontend/src/routes/materials.tsx` (replace the stub; keep the `MaterialsPage` export name — `router.tsx` already imports it)

**Interfaces:**
- Consumes: `useMaterials`, `materialPillStatus`, `StatusPill`, `useDebouncedValue` (exists at `frontend/src/lib/use-debounced-value.ts`), `CompanyLogo`.
- Produces: the Marketing Requests table page. Chips filter client-side on the derived pill; search is server-side (`?search=`).

- [ ] **Step 1: Implement the page**

Replace the contents of `frontend/src/routes/materials.tsx` with:

```tsx
import { useState } from "react";
import { Link, useNavigate } from "@tanstack/react-router";
import { MagnifyingGlass, Plus } from "@phosphor-icons/react";

import { CompanyLogo } from "@/components/company-logo";
import { StatusPill, materialPillStatus } from "@/components/status-pill";
import { useMaterials, type MaterialList } from "@/lib/api/materials";
import { useDebouncedValue } from "@/lib/use-debounced-value";

// Chip set is derived-pill based — deliberate deviation from the design's chips,
// which predate the review workflow (spec §7.3).
const CHIPS = [
  ["all", "All"],
  ["needs_review", "Needs review"],
  ["approved", "Approved"],
  ["rejected", "Rejected"],
  ["processing", "Processing"],
  ["failed", "Failed"],
] as const;
type Chip = (typeof CHIPS)[number][0];

export function MaterialsPage() {
  const [search, setSearch] = useState("");
  const [chip, setChip] = useState<Chip>("all");
  const debounced = useDebouncedValue(search, 300);
  const { data: materials, isLoading } = useMaterials(
    debounced.trim() ? { search: debounced.trim() } : {},
  );
  const navigate = useNavigate();

  const all = materials ?? [];
  const count = (c: Chip) =>
    c === "all" ? all.length : all.filter((m) => materialPillStatus(m) === c).length;
  const rows = chip === "all" ? all : all.filter((m) => materialPillStatus(m) === chip);

  const companyCell = (company: MaterialList["sender_company"]) => (
    <span className="flex items-center gap-2">
      <CompanyLogo name={company.name} logoUrl={company.logo_url} size={24} />
      <span className="truncate text-[13px] text-body">{company.name}</span>
    </span>
  );

  return (
    <div className="mx-auto max-w-[1080px] px-10 pb-[60px] pt-8">
      <div className="mb-6 flex items-center">
        <div>
          <h1 className="text-[23px] font-bold tracking-[-0.02em] text-ink">
            Marketing Requests
          </h1>
          <p className="mt-1 text-[13px] text-subtext">
            Every generation request across companies.
          </p>
        </div>
        <Link
          to="/create"
          className="ml-auto flex items-center gap-[7px] rounded-[10px] bg-brand px-[14px] py-[9px] text-[13px] font-semibold text-white hover:bg-brand-hover"
        >
          <Plus size={15} weight="bold" />
          New Request
        </Link>
      </div>

      <div className="mb-4 flex items-center gap-2">
        {CHIPS.map(([value, label]) => (
          <button
            key={value}
            type="button"
            onClick={() => setChip(value)}
            className={`rounded-full px-[12px] py-[5px] text-[12px] font-semibold ${
              chip === value
                ? "bg-ink text-white"
                : "border border-hairline bg-surface text-subtext hover:text-body"
            }`}
          >
            {label} {count(value)}
          </button>
        ))}
        <div className="relative ml-auto">
          <MagnifyingGlass
            size={14}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-mute"
          />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search titles…"
            className="w-[220px] rounded-[10px] border border-field bg-subtle py-[8px] pl-8 pr-3 text-[13px] text-body outline-none focus:border-brand"
          />
        </div>
      </div>

      <div className="overflow-hidden rounded-2xl border border-hairline bg-surface">
        <table className="w-full text-left">
          <thead>
            <tr className="border-b border-hairline text-[11px] font-semibold uppercase tracking-wide text-faint">
              <th className="px-5 py-3">Title</th>
              <th className="px-5 py-3">Sender</th>
              <th className="px-5 py-3">Receiver</th>
              <th className="px-5 py-3">Status</th>
              <th className="px-5 py-3">Created</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr>
                <td colSpan={5} className="px-5 py-8 text-center text-[13px] text-mute">
                  Loading…
                </td>
              </tr>
            )}
            {!isLoading && rows.length === 0 && (
              <tr>
                <td colSpan={5} className="px-5 py-8 text-center text-[13px] text-mute">
                  No requests yet — create one to get started.
                </td>
              </tr>
            )}
            {rows.map((m) => (
              <tr
                key={m.id}
                onClick={() =>
                  navigate({
                    to: "/materials/$materialId",
                    params: { materialId: String(m.id) },
                  })
                }
                className="cursor-pointer border-b border-hairline last:border-0 hover:bg-[#fafafb]"
              >
                <td className="px-5 py-3 text-[13px] font-semibold text-ink">{m.title}</td>
                <td className="px-5 py-3">{companyCell(m.sender_company)}</td>
                <td className="px-5 py-3">{companyCell(m.receiver_company)}</td>
                <td className="px-5 py-3">
                  <StatusPill status={materialPillStatus(m)} />
                </td>
                <td className="px-5 py-3 text-[12.5px] text-subtext">
                  {new Date(m.created_at).toLocaleDateString()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Typecheck + lint, commit**

```bash
cd frontend && pnpm typecheck && pnpm lint
git add frontend/src/routes/materials.tsx
git commit -m "feat(frontend): global marketing requests page with pill filters"
```

---

### Task 18: Create Material wizard (`/create`)

**Files:**
- Modify: `frontend/src/routes/create.tsx` (replace the stub; keep the `CreatePage` export name — `router.tsx` already imports it)

**Interfaces:**
- Consumes: `useCompanies` (+ `Company` type), `useTemplates`/`templateConstraints`/`templateImageSlots`, `useCreateMaterial`, `useDebouncedValue`, `CompanyLogo`, `api` (for the per-company documents query).
- Produces: the 4-step wizard; on Generate → `POST /api/materials/` → navigate to the detail page (which polls). Deviations from the design, both deliberate: Step 3 adds Title + Description inputs (spec §7.3), and search-result rows show industry only — processed-doc counts appear in the grounding strip for the two *selected* companies (a per-row count would need one documents request per result row).

- [ ] **Step 1: Implement the wizard**

Replace the contents of `frontend/src/routes/create.tsx` with:

```tsx
import { useEffect, useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { Check, CheckCircle, MagicWand, MagnifyingGlass } from "@phosphor-icons/react";

import { CompanyLogo } from "@/components/company-logo";
import { api } from "@/lib/api/client";
import { useCompanies, type Company } from "@/lib/api/companies";
import { createMaterialErrorText, useCreateMaterial } from "@/lib/api/materials";
import { templateConstraints, templateImageSlots, useTemplates } from "@/lib/api/templates";
import { useDebouncedValue } from "@/lib/use-debounced-value";

const STEPS = ["Companies", "Template", "Prompt", "Generate"] as const;
const TONES = ["Professional", "Friendly", "Executive", "Technical"] as const;
const CTA_STYLES = ["Soft", "Direct"] as const;

/** Processed-doc count for a selected company (drives the grounding strip). */
function useProcessedDocCount(companyId: number | undefined) {
  return useQuery({
    queryKey: ["documents", companyId],
    enabled: companyId != null,
    queryFn: async () => {
      const { data, error } = await api.GET("/api/companies/{company_pk}/documents/", {
        params: { path: { company_pk: companyId as number } },
      });
      if (error) throw error;
      return data;
    },
    select: (docs) => docs.filter((d) => d.status === "processed").length,
  });
}

function Chip({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-full border px-[12px] py-[5px] text-[12px] font-semibold ${
        active
          ? "border-[#dcdcfb] bg-brand-soft text-brand"
          : "border-[#e6e6ea] bg-surface text-subtext hover:text-body"
      }`}
    >
      {label}
    </button>
  );
}

function CompanyPicker({
  label,
  selected,
  exclude,
  onSelect,
}: {
  label: string;
  selected: Company | null;
  exclude: number | undefined;
  onSelect: (company: Company) => void;
}) {
  const [search, setSearch] = useState("");
  const debounced = useDebouncedValue(search, 300);
  const { data: companies, isLoading } = useCompanies(debounced);
  const results = (companies ?? []).filter((c) => c.id !== exclude);
  return (
    <div>
      <div className="mb-2 text-[12px] font-semibold text-body">{label}</div>
      <div className="relative mb-2">
        <MagnifyingGlass
          size={14}
          className="absolute left-3 top-1/2 -translate-y-1/2 text-mute"
        />
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search companies…"
          className="w-full rounded-[10px] border border-field bg-subtle py-[8px] pl-8 pr-3 text-[13px] text-body outline-none focus:border-brand"
        />
      </div>
      <div className="max-h-[220px] overflow-y-auto rounded-xl border border-hairline">
        {isLoading && <p className="p-3 text-[12.5px] text-mute">Searching…</p>}
        {!isLoading && results.length === 0 && (
          <p className="p-3 text-[12.5px] text-mute">No companies found.</p>
        )}
        {results.map((company) => {
          const isSelected = selected?.id === company.id;
          return (
            <button
              key={company.id}
              type="button"
              onClick={() => onSelect(company)}
              className={`flex w-full items-center gap-3 border-b border-hairline p-3 text-left last:border-0 ${
                isSelected
                  ? "border-l-[3px] border-l-brand bg-[#f4f4fd]"
                  : "hover:bg-[#fafafb]"
              }`}
            >
              <CompanyLogo name={company.name} logoUrl={company.logo_url} size={30} />
              <span className="min-w-0 flex-1">
                <span className="block truncate text-[13px] font-semibold text-ink">
                  {company.name}
                </span>
                <span className="block truncate text-[11.5px] text-mute">
                  {company.industry || "—"}
                </span>
              </span>
              {isSelected && <CheckCircle size={18} weight="fill" className="text-brand" />}
            </button>
          );
        })}
      </div>
    </div>
  );
}

export function CreatePage() {
  const [step, setStep] = useState(0);
  const [sender, setSender] = useState<Company | null>(null);
  const [receiver, setReceiver] = useState<Company | null>(null);
  const [templateId, setTemplateId] = useState<number | null>(null);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [prompt, setPrompt] = useState("");
  const [tone, setTone] = useState<string>("Professional");
  const [ctaStyle, setCtaStyle] = useState<string>("Soft");
  const [language, setLanguage] = useState("English");
  const [error, setError] = useState<string | null>(null);

  const { data: templates } = useTemplates();
  const activeTemplates = (templates ?? []).filter((t) => t.is_active);
  // Pre-select the default (first active = the seed, oldest-first ordering, spec §7.3).
  useEffect(() => {
    if (templateId == null && activeTemplates.length > 0) {
      setTemplateId(activeTemplates[0].id);
    }
  }, [templateId, activeTemplates]);
  const template = activeTemplates.find((t) => t.id === templateId) ?? null;

  const senderDocs = useProcessedDocCount(sender?.id);
  const receiverDocs = useProcessedDocCount(receiver?.id);
  const create = useCreateMaterial();
  const navigate = useNavigate();

  const stepValid = [
    Boolean(
      sender &&
        receiver &&
        sender.id !== receiver.id &&
        (senderDocs.data ?? 0) > 0 &&
        (receiverDocs.data ?? 0) > 0,
    ),
    templateId != null,
    title.trim().length > 0 && prompt.trim().length > 0,
    true,
  ][step];

  const generate = () => {
    if (!sender || !receiver || templateId == null) return;
    setError(null);
    create.mutate(
      {
        title: title.trim(),
        description: description.trim() || undefined,
        sender_company: sender.id,
        receiver_company: receiver.id,
        template: templateId,
        prompt: prompt.trim(),
        tone: tone.toLowerCase(),
        cta_style: ctaStyle.toLowerCase(),
        language: language.toLowerCase(),
      },
      {
        onSuccess: (material) =>
          navigate({
            to: "/materials/$materialId",
            params: { materialId: String(material.id) },
          }),
        onError: (err) => setError(createMaterialErrorText(err)),
      },
    );
  };

  const summaryRows: [string, string][] = [
    ["Sender", sender?.name ?? "—"],
    ["Receiver", receiver?.name ?? "—"],
    ["Template", template?.name ?? "—"],
    ["Tone / CTA", `${tone} / ${ctaStyle}`],
    [
      "Grounding",
      `${(senderDocs.data ?? 0) + (receiverDocs.data ?? 0)} processed documents across both companies`,
    ],
  ];

  return (
    <div className="mx-auto max-w-[820px] px-10 pb-[60px] pt-8">
      <h1 className="text-[23px] font-bold tracking-[-0.02em] text-ink">Create Material</h1>
      <p className="mb-6 mt-1 text-[13px] text-subtext">
        Configure sender, receiver, template and campaign goal — then generate.
      </p>

      <div className="mb-7 flex items-center">
        {STEPS.map((label, i) => (
          <div key={label} className="flex flex-1 items-center last:flex-none">
            <div className="flex flex-col items-center">
              <div
                className={`flex size-[30px] items-center justify-center rounded-full text-[13px] font-semibold ${
                  i <= step ? "bg-brand text-white" : "bg-[#ececf0] text-faint"
                }`}
              >
                {i < step ? <Check size={14} weight="bold" /> : i + 1}
              </div>
              <span className="mt-1 text-[11px] text-subtext">{label}</span>
            </div>
            {i < STEPS.length - 1 && (
              <div
                className={`mx-2 mb-4 h-[2px] flex-1 ${i < step ? "bg-brand" : "bg-[#ececf0]"}`}
              />
            )}
          </div>
        ))}
      </div>

      <div className="min-h-[300px] rounded-2xl border border-hairline bg-surface p-6">
        {step === 0 && (
          <>
            <div className="grid grid-cols-2 gap-5">
              <CompanyPicker
                label="Sender"
                selected={sender}
                exclude={receiver?.id}
                onSelect={setSender}
              />
              <CompanyPicker
                label="Receiver"
                selected={receiver}
                exclude={sender?.id}
                onSelect={setReceiver}
              />
            </div>
            {sender && receiver && (
              <div className="mt-4 rounded-xl bg-brand-soft px-4 py-3 text-[12.5px] text-body">
                <strong>{sender.name}</strong> is pitching to <strong>{receiver.name}</strong>
                {" — grounding will draw from "}
                {(senderDocs.data ?? 0) + (receiverDocs.data ?? 0)} processed documents across
                both companies.
                {(senderDocs.data === 0 || receiverDocs.data === 0) && (
                  <span className="mt-1 block font-semibold text-destructive">
                    {senderDocs.data === 0 ? sender.name : receiver.name} has no processed
                    documents — upload and process documents first.
                  </span>
                )}
              </div>
            )}
          </>
        )}

        {step === 1 && (
          <div className="grid grid-cols-2 gap-4">
            {activeTemplates.map((t) => {
              const constraints = templateConstraints(t);
              const isSelected = t.id === templateId;
              return (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => setTemplateId(t.id)}
                  className={`relative rounded-xl border p-4 text-left ${
                    isSelected ? "border-[1.5px] border-brand" : "border-hairline hover:bg-subtle"
                  }`}
                >
                  {isSelected && (
                    <CheckCircle
                      size={18}
                      weight="fill"
                      className="absolute right-3 top-3 text-brand"
                    />
                  )}
                  <div className="text-[13.5px] font-semibold text-ink">{t.name}</div>
                  <div className="mb-2 font-mono text-[11px] text-mute">{t.slug}</div>
                  <ul className="text-[12px] leading-relaxed text-subtext">
                    <li>Headline ≤{constraints.headline_max_words} words</li>
                    <li>Subheadline ≤{constraints.subheadline_max_words} words</li>
                    <li>
                      Body {constraints.body_section_count} sections ≤
                      {constraints.body_section_max_words} words each
                    </li>
                    <li>CTA ≤{constraints.cta_max_words} words</li>
                    <li>{templateImageSlots(t).map((s) => s.label).join(" + ") || "No images"}</li>
                  </ul>
                </button>
              );
            })}
            <div className="rounded-xl border border-dashed border-hairline p-4 opacity-65">
              <div className="text-[13.5px] font-semibold text-ink">Brochure (Tri-fold)</div>
              <div className="text-[12px] text-mute">Coming soon</div>
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="flex flex-col gap-4">
            {/* Title + Description are deliberate additions to the design's step (spec §7.3) */}
            <div>
              <label className="mb-1 block text-[12px] font-semibold text-body">Title</label>
              <input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g. AI for Smarter Logistics"
                className="w-full rounded-[10px] border border-field bg-subtle px-3 py-[8px] text-[13px] text-body outline-none focus:border-brand"
              />
            </div>
            <div>
              <label className="mb-1 block text-[12px] font-semibold text-body">
                Description <span className="font-normal text-mute">(optional)</span>
              </label>
              <input
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                className="w-full rounded-[10px] border border-field bg-subtle px-3 py-[8px] text-[13px] text-body outline-none focus:border-brand"
              />
            </div>
            <div>
              <label className="mb-1 block text-[12px] font-semibold text-body">
                Campaign goal
              </label>
              <textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                rows={4}
                placeholder="e.g. Generate a short B2B article about how we can help the receiver improve warehouse efficiency."
                className="w-full rounded-[10px] border border-field bg-subtle p-3 text-[13px] text-body outline-none focus:border-brand"
              />
            </div>
            <div className="grid grid-cols-3 gap-4">
              <div>
                <div className="mb-2 text-[12px] font-semibold text-body">Tone</div>
                <div className="flex flex-wrap gap-2">
                  {TONES.map((t) => (
                    <Chip key={t} label={t} active={tone === t} onClick={() => setTone(t)} />
                  ))}
                </div>
              </div>
              <div>
                <div className="mb-2 text-[12px] font-semibold text-body">CTA style</div>
                <div className="flex gap-2">
                  {CTA_STYLES.map((c) => (
                    <Chip
                      key={c}
                      label={c}
                      active={ctaStyle === c}
                      onClick={() => setCtaStyle(c)}
                    />
                  ))}
                </div>
              </div>
              <div>
                <div className="mb-2 text-[12px] font-semibold text-body">Language</div>
                <select
                  value={language}
                  onChange={(e) => setLanguage(e.target.value)}
                  className="w-full rounded-[10px] border border-field bg-subtle px-3 py-[8px] text-[13px] text-body outline-none"
                >
                  <option>English</option>
                </select>
              </div>
            </div>
          </div>
        )}

        {step === 3 && (
          <div>
            <div className="mb-5 flex flex-col gap-2">
              {summaryRows.map(([label, value]) => (
                <div key={label} className="flex justify-between border-b border-hairline pb-2">
                  <span className="text-[12.5px] text-mute">{label}</span>
                  <span className="text-[13px] font-medium text-body">{value}</span>
                </div>
              ))}
            </div>
            {error && (
              <p className="mb-3 rounded-lg bg-danger-soft px-3 py-2 text-[12.5px] text-destructive">
                {error}
              </p>
            )}
            <button
              type="button"
              disabled={create.isPending}
              onClick={generate}
              className="flex w-full items-center justify-center gap-2 rounded-[10px] bg-brand py-[12px] text-[14px] font-semibold text-white hover:bg-brand-hover disabled:opacity-60"
            >
              <MagicWand size={17} weight="fill" />
              {create.isPending ? "Starting generation…" : "Generate Marketing Material"}
            </button>
          </div>
        )}
      </div>

      <div className="mt-5 flex justify-between">
        <button
          type="button"
          onClick={() => setStep(Math.max(0, step - 1))}
          disabled={step === 0}
          className="rounded-[10px] px-[14px] py-[9px] text-[13px] font-semibold text-subtext hover:text-body disabled:opacity-0"
        >
          Back
        </button>
        {step < 3 && (
          <button
            type="button"
            disabled={!stepValid}
            onClick={() => setStep(step + 1)}
            className="rounded-[10px] bg-ink px-[18px] py-[9px] text-[13px] font-semibold text-white disabled:opacity-40"
          >
            Continue
          </button>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Add the error-text helper to materials.ts**

Append to `frontend/src/lib/api/materials.ts`:

```typescript
/** DRF error body → first human-readable message (for the wizard). */
export function createMaterialErrorText(err: unknown): string {
  if (err && typeof err === "object") {
    for (const value of Object.values(err as Record<string, unknown>)) {
      if (Array.isArray(value) && value.length > 0) return String(value[0]);
      if (typeof value === "string") return value;
    }
  }
  return "Something went wrong. Please try again.";
}
```

- [ ] **Step 3: Typecheck + lint + tests, commit**

```bash
cd frontend && pnpm typecheck && pnpm lint && pnpm test
git add frontend/src/routes/create.tsx frontend/src/lib/api/materials.ts
git commit -m "feat(frontend): 4-step create material wizard with company search + grounding check"
```

---

### Task 19: Templates list + Create Template builder

**Files:**
- Modify: `frontend/src/routes/templates.tsx` (replace the stub; keep the `TemplatesPage` export)
- Create: `frontend/src/routes/template-new.tsx`
- Modify: `frontend/src/router.tsx` (register `/templates/new`)

**Interfaces:**
- Consumes: `useTemplates`, `useCreateTemplate`, `TemplateWrite`, `templateConstraints`, `templateImageSlots` (Task 12).
- Produces: `TemplatesPage`, `TemplateNewPage` at `/templates/new`. Builder rules (spec §7.3): all body rows share ONE word-limit value; row count → `body_section_count`; `slot_id` derived client-side by slugifying the label (uniquified `_2`, `_3`…); stepper bounds mirror the backend serializer bounds; **no drag-reorder**.

- [ ] **Step 1: Implement the templates list**

Replace the contents of `frontend/src/routes/templates.tsx` with:

```tsx
import { Link } from "@tanstack/react-router";
import { Newspaper, Plus } from "@phosphor-icons/react";

import { templateConstraints, templateImageSlots, useTemplates } from "@/lib/api/templates";

export function TemplatesPage() {
  const { data: templates, isLoading } = useTemplates();
  return (
    <div className="mx-auto max-w-[1080px] px-10 pb-[60px] pt-8">
      <div className="mb-6 flex items-center">
        <div>
          <h1 className="text-[23px] font-bold tracking-[-0.02em] text-ink">Templates</h1>
          <p className="mt-1 text-[13px] text-subtext">
            Publishing layouts and the constraints generations are validated against.
          </p>
        </div>
        <Link
          to="/templates/new"
          className="ml-auto flex items-center gap-[7px] rounded-[10px] bg-brand px-[14px] py-[9px] text-[13px] font-semibold text-white hover:bg-brand-hover"
        >
          <Plus size={15} weight="bold" />
          New Template
        </Link>
      </div>

      {isLoading && <p className="text-[13px] text-mute">Loading…</p>}

      <div className="grid grid-cols-[1.4fr_1fr] items-start gap-5">
        <div className="flex flex-col gap-4">
          {(templates ?? []).map((t) => {
            const constraints = templateConstraints(t);
            const slots = templateImageSlots(t);
            const theme = t.theme as { primary_color: string; accent_color: string };
            return (
              <div key={t.id} className="rounded-2xl border border-hairline bg-surface p-5">
                <div className="mb-4 flex items-center gap-3">
                  <span className="flex size-[34px] items-center justify-center rounded-lg bg-brand-soft text-brand">
                    <Newspaper size={17} />
                  </span>
                  <div>
                    <div className="text-[14px] font-semibold text-ink">{t.name}</div>
                    <div className="font-mono text-[11px] text-mute">{t.slug}</div>
                  </div>
                  {t.is_active && (
                    <span className="ml-auto rounded-full bg-success-soft px-[10px] py-[3px] text-[11.5px] font-semibold text-success">
                      Active
                    </span>
                  )}
                </div>
                <div className="grid grid-cols-2 gap-4 text-[12.5px] text-subtext">
                  <div>
                    <div className="mb-1 font-semibold text-body">Field constraints</div>
                    <ul className="leading-relaxed">
                      <li>Headline ≤{constraints.headline_max_words}</li>
                      <li>Subheadline ≤{constraints.subheadline_max_words}</li>
                      <li>
                        Body {constraints.body_section_count}×≤
                        {constraints.body_section_max_words}
                      </li>
                      <li>CTA ≤{constraints.cta_max_words}</li>
                    </ul>
                  </div>
                  <div>
                    <div className="mb-1 font-semibold text-body">Image slots</div>
                    <ul className="leading-relaxed">
                      {slots.length === 0 && <li>None</li>}
                      {slots.map((s) => (
                        <li key={s.slot_id}>
                          {s.label} {s.spec && `(${s.spec})`}
                        </li>
                      ))}
                    </ul>
                    <div className="mb-1 mt-3 font-semibold text-body">Theme</div>
                    <div className="flex items-center gap-2">
                      {[theme.primary_color, theme.accent_color].map((hex, i) => (
                        <span key={i} className="flex items-center gap-1">
                          <span
                            className="size-[16px] rounded border border-hairline"
                            style={{ background: hex }}
                          />
                          <span className="font-mono text-[11px]">{hex}</span>
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        <div className="flex flex-col gap-4">
          {["Brochure (Tri-fold)", "Email Campaign"].map((name) => (
            <div
              key={name}
              className="rounded-2xl border border-dashed border-hairline bg-surface p-5 opacity-70"
            >
              <div className="text-[13.5px] font-semibold text-ink">{name}</div>
              <p className="mt-1 text-[12px] text-mute">
                Coming soon — same JSON contract.
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Implement the builder**

`frontend/src/routes/template-new.tsx`:

```tsx
import { useState } from "react";
import { Link, useNavigate } from "@tanstack/react-router";
import { CaretRight, Check, Image, Lock, Minus, Plus, TextT, Trash } from "@phosphor-icons/react";

import {
  createMaterialErrorText as errorText,
} from "@/lib/api/materials";
import { useCreateTemplate, type TemplateImageSlot } from "@/lib/api/templates";

// Bounds mirror the backend serializer (spec §5.1).
const BOUNDS = {
  headline: { min: 1, max: 60 },
  subheadline: { min: 1, max: 60 },
  cta: { min: 1, max: 60 },
  bodyWords: { min: 1, max: 300 },
  bodyRows: { min: 1, max: 10 },
  slots: { max: 8 },
};

export function slugifyId(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

/** slot_id per row: slugified label, uniquified with _2, _3… (spec §7.3). */
export function toImageSlots(
  rows: { label: string; spec: string; source: TemplateImageSlot["source"] }[],
): TemplateImageSlot[] {
  const seen = new Map<string, number>();
  return rows.map((row) => {
    const base = slugifyId(row.label) || "slot";
    const n = (seen.get(base) ?? 0) + 1;
    seen.set(base, n);
    return { slot_id: n === 1 ? base : `${base}_${n}`, ...row };
  });
}

function Stepper({
  value,
  min,
  max,
  onChange,
}: {
  value: number;
  min: number;
  max: number;
  onChange: (v: number) => void;
}) {
  return (
    <span className="flex items-center gap-1 rounded-lg border border-field px-1 py-[2px]">
      <button
        type="button"
        onClick={() => onChange(Math.max(min, value - 1))}
        className="p-1 text-mute hover:text-body"
        aria-label="decrease"
      >
        <Minus size={11} />
      </button>
      <span className="min-w-[60px] text-center text-[12px] text-body">≤ {value} words</span>
      <button
        type="button"
        onClick={() => onChange(Math.min(max, value + 1))}
        className="p-1 text-mute hover:text-body"
        aria-label="increase"
      >
        <Plus size={11} />
      </button>
    </span>
  );
}

function BuilderCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-hairline bg-surface p-5">
      <h3 className="mb-4 text-[13px] font-semibold text-ink">{title}</h3>
      {children}
    </div>
  );
}

type SlotRow = { label: string; spec: string; source: TemplateImageSlot["source"] };

export function TemplateNewPage() {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [headlineMax, setHeadlineMax] = useState(10);
  const [subheadlineMax, setSubheadlineMax] = useState(22);
  const [ctaMax, setCtaMax] = useState(15);
  const [bodyRows, setBodyRows] = useState(2);
  const [bodyMax, setBodyMax] = useState(80);
  const [slots, setSlots] = useState<SlotRow[]>([
    { label: "Hero image", spec: "1200×630", source: "generated_placeholder" },
    { label: "Sender logo", spec: "SVG/PNG", source: "sender" },
  ]);
  const [primary, setPrimary] = useState("#5b5bd6");
  const [accent, setAccent] = useState("#0f172a");
  const [error, setError] = useState<string | null>(null);

  const create = useCreateTemplate();
  const navigate = useNavigate();
  const slug = slugifyId(name);

  const save = () => {
    setError(null);
    create.mutate(
      {
        name: name.trim(),
        description: description.trim() || undefined,
        constraints: {
          headline_max_words: headlineMax,
          subheadline_max_words: subheadlineMax,
          body_section_count: bodyRows,
          body_section_max_words: bodyMax,
          cta_max_words: ctaMax,
        },
        image_slots: toImageSlots(slots.filter((s) => s.label.trim())),
        theme: { primary_color: primary, accent_color: accent },
      },
      {
        onSuccess: () => navigate({ to: "/templates" }),
        onError: (err) => setError(errorText(err)),
      },
    );
  };

  const setSlot = (i: number, patch: Partial<SlotRow>) =>
    setSlots(slots.map((s, j) => (j === i ? { ...s, ...patch } : s)));

  const textRow = (
    icon: React.ReactNode,
    label: string,
    stepper: React.ReactNode,
    onRemove?: () => void,
  ) => (
    <div className="flex items-center gap-3 border-b border-hairline py-2 last:border-0">
      <span className="flex size-[26px] items-center justify-center rounded-lg bg-brand-soft text-brand">
        {icon}
      </span>
      <span className="flex-1 text-[13px] font-semibold text-body">{label}</span>
      {stepper}
      {onRemove && (
        <button
          type="button"
          onClick={onRemove}
          className="text-mute hover:text-destructive"
          aria-label={`remove ${label}`}
        >
          <Trash size={14} />
        </button>
      )}
    </div>
  );

  return (
    <div className="mx-auto max-w-[1080px] px-10 pb-[60px] pt-8">
      <div className="mb-[18px] flex items-center gap-[7px] text-[12.5px] text-mute">
        <Link to="/templates" className="hover:text-brand">
          Templates
        </Link>
        <CaretRight size={11} />
        <span className="font-medium text-body">New template</span>
      </div>
      <h1 className="text-[24px] font-bold tracking-[-0.02em] text-ink">Create Template</h1>
      <p className="mb-6 mt-1 text-[13px] text-subtext">
        Define the fields, limits and image slots. Generated content is validated against
        these constraints.
      </p>

      <div className="grid grid-cols-[1.5fr_1fr] items-start gap-5">
        <div className="flex flex-col gap-4">
          <BuilderCard title="Basics">
            <div className="flex flex-col gap-3">
              <div>
                <label className="mb-1 block text-[12px] font-semibold text-body">
                  Template name
                </label>
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Product Spotlight"
                  className="w-full rounded-[10px] border border-field bg-subtle px-3 py-[8px] text-[13px] text-body outline-none focus:border-brand"
                />
              </div>
              <div>
                <label className="mb-1 flex items-center gap-1 text-[12px] font-semibold text-body">
                  Template ID <Lock size={11} className="text-mute" />
                </label>
                <div className="rounded-[10px] bg-[#f4f4f6] px-3 py-[8px] font-mono text-[12px] text-subtext">
                  {slug || "—"}
                </div>
              </div>
              <div>
                <label className="mb-1 block text-[12px] font-semibold text-body">
                  Description
                </label>
                <input
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  className="w-full rounded-[10px] border border-field bg-subtle px-3 py-[8px] text-[13px] text-body outline-none focus:border-brand"
                />
              </div>
            </div>
          </BuilderCard>

          <BuilderCard title="Text fields">
            {textRow(
              <TextT size={13} />,
              "Headline",
              <Stepper
                value={headlineMax}
                min={BOUNDS.headline.min}
                max={BOUNDS.headline.max}
                onChange={setHeadlineMax}
              />,
            )}
            {textRow(
              <TextT size={13} />,
              "Subheadline",
              <Stepper
                value={subheadlineMax}
                min={BOUNDS.subheadline.min}
                max={BOUNDS.subheadline.max}
                onChange={setSubheadlineMax}
              />,
            )}
            {Array.from({ length: bodyRows }, (_, i) =>
              textRow(
                <TextT size={13} />,
                `Body section ${i + 1}`,
                // All body rows share ONE limit (fixed contract, spec §7.3).
                <Stepper
                  value={bodyMax}
                  min={BOUNDS.bodyWords.min}
                  max={BOUNDS.bodyWords.max}
                  onChange={setBodyMax}
                />,
                bodyRows > BOUNDS.bodyRows.min
                  ? () => setBodyRows(bodyRows - 1)
                  : undefined,
              ),
            )}
            {textRow(
              <TextT size={13} />,
              "CTA",
              <Stepper
                value={ctaMax}
                min={BOUNDS.cta.min}
                max={BOUNDS.cta.max}
                onChange={setCtaMax}
              />,
            )}
            <button
              type="button"
              disabled={bodyRows >= BOUNDS.bodyRows.max}
              onClick={() => setBodyRows(bodyRows + 1)}
              className="mt-3 w-full rounded-[10px] border border-dashed border-field py-[8px] text-[12.5px] font-semibold text-brand hover:bg-subtle disabled:opacity-40"
            >
              + Add text field (body section)
            </button>
          </BuilderCard>

          <BuilderCard title="Image slots">
            {slots.map((slot, i) => (
              <div
                key={i}
                className="flex items-center gap-3 border-b border-hairline py-2 last:border-0"
              >
                <span className="flex size-[26px] items-center justify-center rounded-lg bg-review-soft text-review">
                  <Image size={13} />
                </span>
                <input
                  value={slot.label}
                  onChange={(e) => setSlot(i, { label: e.target.value })}
                  placeholder="Slot name"
                  className="flex-1 rounded-lg border border-field bg-subtle px-2 py-[5px] text-[12.5px] font-semibold text-body outline-none focus:border-brand"
                />
                <input
                  value={slot.spec}
                  onChange={(e) => setSlot(i, { spec: e.target.value })}
                  placeholder="Spec (e.g. 1200×630)"
                  className="w-[120px] rounded-lg border border-field bg-subtle px-2 py-[5px] text-[12px] text-body outline-none focus:border-brand"
                />
                <select
                  value={slot.source}
                  onChange={(e) =>
                    setSlot(i, { source: e.target.value as SlotRow["source"] })
                  }
                  className="rounded-lg border border-field bg-subtle px-2 py-[5px] text-[12px] text-body outline-none"
                >
                  <option value="generated_placeholder">Placeholder</option>
                  <option value="sender">Sender</option>
                  <option value="receiver">Receiver</option>
                </select>
                <button
                  type="button"
                  onClick={() => setSlots(slots.filter((_, j) => j !== i))}
                  className="text-mute hover:text-destructive"
                  aria-label={`remove slot ${slot.label}`}
                >
                  <Trash size={14} />
                </button>
              </div>
            ))}
            <button
              type="button"
              disabled={slots.length >= BOUNDS.slots.max}
              onClick={() =>
                setSlots([...slots, { label: "", spec: "", source: "generated_placeholder" }])
              }
              className="mt-3 w-full rounded-[10px] border border-dashed border-field py-[8px] text-[12.5px] font-semibold text-brand hover:bg-subtle disabled:opacity-40"
            >
              + Add image slot
            </button>
          </BuilderCard>

          <BuilderCard title="Theme colors">
            <div className="flex gap-6">
              {(
                [
                  ["Primary", primary, setPrimary],
                  ["Accent", accent, setAccent],
                ] as const
              ).map(([label, value, set]) => (
                <div key={label} className="flex items-center gap-2">
                  <span
                    className="size-[28px] rounded-lg border border-hairline"
                    style={{ background: value }}
                  />
                  <div>
                    <div className="text-[11px] font-semibold text-body">{label}</div>
                    <input
                      value={value}
                      onChange={(e) => set(e.target.value)}
                      className="w-[90px] rounded border border-field bg-subtle px-1 py-[2px] font-mono text-[11.5px] text-body outline-none"
                    />
                  </div>
                </div>
              ))}
            </div>
          </BuilderCard>
        </div>

        <div className="sticky top-[26px] flex flex-col gap-4">
          <div className="rounded-2xl border border-hairline bg-surface p-5">
            <h3 className="mb-3 text-[13px] font-semibold text-ink">Live layout preview</h3>
            {slots.some((s) => s.source === "generated_placeholder") && (
              <div
                className="mb-3 flex h-[90px] items-center justify-center rounded-lg text-[11px] text-mute"
                style={{
                  backgroundImage:
                    "repeating-linear-gradient(45deg, #ececf0 0 10px, #f6f6f8 10px 20px)",
                }}
              >
                Hero image
              </div>
            )}
            <div className="mb-2 h-[14px] w-3/4 rounded bg-[#e7e7ec]" />
            <div className="mb-3 h-[9px] w-full rounded bg-[#f0f0f2]" />
            {Array.from({ length: bodyRows }, (_, i) => (
              <div key={i} className="mb-2 h-[9px] w-full rounded bg-[#f0f0f2]" />
            ))}
            <div
              className="mt-3 h-[30px] rounded-lg"
              style={{ background: `${primary}22` }}
            />
            <div className="mt-4 flex gap-2 text-[11px] text-subtext">
              <span className="rounded-full border border-hairline px-2 py-[2px]">
                {3 + bodyRows} text fields
              </span>
              <span className="rounded-full border border-hairline px-2 py-[2px]">
                {slots.length} image slots
              </span>
            </div>
          </div>
          <p className="rounded-xl bg-brand-soft px-4 py-3 text-[12px] text-body">
            This template compiles to the same layout-JSON schema every generation is
            validated against.
          </p>
        </div>
      </div>

      {error && (
        <p className="mt-4 rounded-lg bg-danger-soft px-3 py-2 text-[12.5px] text-destructive">
          {error}
        </p>
      )}
      <div className="mt-5 flex justify-end gap-3">
        <Link
          to="/templates"
          className="rounded-[10px] px-[14px] py-[9px] text-[13px] font-semibold text-subtext hover:text-body"
        >
          Cancel
        </Link>
        <button
          type="button"
          disabled={!name.trim() || create.isPending}
          onClick={save}
          className="flex items-center gap-2 rounded-[10px] bg-brand px-[18px] py-[9px] text-[13px] font-semibold text-white hover:bg-brand-hover disabled:opacity-50"
        >
          <Check size={15} weight="bold" />
          Save template
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Register the route**

In `frontend/src/router.tsx`: add `import { TemplateNewPage } from "@/routes/template-new";`, then after `templatesRoute`:

```tsx
const templateNewRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/templates/new",
  component: TemplateNewPage,
});
```

and add `templateNewRoute` to `appRoute.addChildren([...])`.

- [ ] **Step 4: Typecheck + lint + tests, commit**

```bash
cd frontend && pnpm typecheck && pnpm lint && pnpm test
git add frontend/src/routes/templates.tsx frontend/src/routes/template-new.tsx frontend/src/router.tsx
git commit -m "feat(frontend): templates list + fixed-contract template builder"
```

---

### Task 20: End-to-end verification

**Files:** none (verification only; fix anything found and commit).

- [ ] **Step 1: Full backend + frontend gates**

```bash
docker compose -f docker-compose.local.yml run --rm django pytest -q
cd frontend && pnpm test && pnpm typecheck && pnpm lint && pnpm build
```

Expected: everything green.

- [ ] **Step 2: Regenerate + diff the OpenAPI types**

```bash
docker compose -f docker-compose.local.yml up -d django postgres
cd frontend && pnpm gen:api && git diff --stat src/lib/api/schema.d.ts
```

Expected: no diff (schema.d.ts already committed in Task 12; a diff means a later backend task changed the API — commit the regenerated file).

- [ ] **Step 3: Manual E2E in the running stack**

```bash
docker compose -f docker-compose.local.yml up -d
```

Then in the browser (http://localhost:3000, logged in):

1. Company detail → Generated Materials tab renders two columns (empty states first).
2. `/templates` shows the seeded Newsletter Article card; `/templates/new` creates a custom template that then appears in the wizard's Step 2.
3. `/create`: search-select sender + receiver (both need processed documents — upload via the Documents tab first), template pre-selected, fill title + prompt, Generate → lands on the detail page showing the Processing panel with polling.
4. Worker outcome depends on Vertex access: **with** `GOOGLE_CLOUD_PROJECT` + ADC configured in the django container, the material completes — verify Preview renders the article with template theme, Layout JSON is syntax-colored with working Copy, Sources shows sender/receiver cards and open-at-page works, constraint meters + quality checks populate, Approve/Reject toggle the pill, Regenerate re-runs. **Without** Vertex access, the material lands on `failed` with a clear `error_message` — verify the error banner + Regenerate render (this is the expected local-degraded path, same as worker 1).
5. `/materials` lists everything with working chips + search; row click opens detail; delete from detail returns to `/materials`.

- [ ] **Step 4: Commit any fixes and finish**

```bash
git status
git add -A && git commit -m "fix: address end-to-end verification findings"  # only if needed
```

Then use the superpowers:finishing-a-development-branch skill to decide merge/PR.

---

## Execution notes

- Tasks 1–11 are backend and strictly ordered (each consumes the previous task's interfaces). Tasks 12–19 are frontend and strictly ordered after 11 (Task 12's `gen:api` needs the final API surface; page tasks need the routes registered in order 15 → 16). Task 11 (CI) can run any time after Task 10.
- The frontend dev loop assumes the compose stack backend at `http://localhost:8000` (VITE_API_URL default).
- If `pnpm gen:api` produces schema names that differ from the plan's assumptions (`MaterialList`, `MaterialDetail`, `MaterialCreate`, `PatchedMaterialUpdate`, `Template`), trust the generated file — drf-spectacular names come from serializer class names minus the `Serializer` suffix; adjust the type aliases in one place (`materials.ts`/`templates.ts`).




