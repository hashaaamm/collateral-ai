# Company "Last updated" Field Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Last updated" column to the companies list page, reflecting the most recent of a company record change or a document being added to it.

**Architecture:** Denormalized `last_activity_at` column on `Company` (`auto_now=True` covers company edits; a `Document` `post_save` signal covers document adds). Exposed through the API as read-only `last_updated`, regenerated into the frontend's typed OpenAPI schema, and rendered as relative time by a new `formatRelativeDay` helper.

**Tech Stack:** Django + DRF (drf-spectacular), pytest + pytest-django + factory_boy, React + TanStack Router/Query, Vitest, Tailwind v4, `openapi-typescript`. All commands run through Docker via `just`.

**Spec:** `docs/superpowers/specs/2026-07-08-company-last-updated-design.md`

## Global Constraints

- **Backend import style:** one symbol per line (`from x import a` / `from x import b`), matching existing files.
- **Backend tests:** pytest + pytest-django + factory_boy (`CompanyFactory`, `DocumentFactory`). DB access via `pytestmark = pytest.mark.django_db`. Run with `just test <path>` (→ `docker compose run --rm django pytest <path>`), paths relative to `backend/`.
- **Frontend helpers:** named `export function` with a single-line `/** ... */` JSDoc. No default exports. Files live flat in `frontend/src/lib/`.
- **Frontend tests:** Vitest. Import `{ describe, expect, it }` explicitly from `"vitest"` (no globals). Run with `docker compose run --rm frontend pnpm test <path>` from repo root.
- **Muted cell text token:** `text-subtext` (#77777f) — matches both the existing Website cell and the design's Last-updated color.
- **Stack must be up** (`just up`) for the OpenAPI regen task; it hits the live `/api/schema/` endpoint.

---

### Task 1: `Company.last_activity_at` column + migration

**Files:**
- Modify: `backend/collateral_ai/companies/models.py`
- Create: `backend/collateral_ai/companies/migrations/0002_company_last_activity_at.py`
- Test: `backend/collateral_ai/companies/tests/test_models.py`

**Interfaces:**
- Produces: `Company.last_activity_at` (`DateTimeField`, `auto_now=True`) — set on every `company.save()`; written directly by later tasks via `.update()`.

- [ ] **Step 1: Write the failing test**

Add to `backend/collateral_ai/companies/tests/test_models.py`:

```python
def test_company_has_last_activity_after_create():
    company = CompanyFactory()
    assert company.last_activity_at is not None


def test_saving_company_bumps_last_activity():
    company = CompanyFactory()
    before = company.last_activity_at
    company.name = "Renamed"
    company.save()
    company.refresh_from_db()
    assert company.last_activity_at >= before
```

(The file already imports `CompanyFactory` and sets `pytestmark = pytest.mark.django_db`; reuse the existing imports. If `CompanyFactory` is not yet imported here, add `from collateral_ai.companies.tests.factories import CompanyFactory`.)

- [ ] **Step 2: Run test to verify it fails**

Run: `just test collateral_ai/companies/tests/test_models.py -v`
Expected: FAIL — `AttributeError: 'Company' object has no attribute 'last_activity_at'`.

- [ ] **Step 3: Add the model field**

In `backend/collateral_ai/companies/models.py`, add the field immediately after `created_at`:

```python
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity_at = models.DateTimeField(auto_now=True)
```

- [ ] **Step 4: Create the migration by hand**

Create `backend/collateral_ai/companies/migrations/0002_company_last_activity_at.py` with exactly this content (companies is currently at `0001_initial`; documents at `0001_initial`):

```python
import django.utils.timezone
from django.db import migrations
from django.db import models
from django.db.models import Max


def backfill_last_activity(apps, schema_editor):
    Company = apps.get_model("companies", "Company")
    companies = Company.objects.annotate(_latest_doc=Max("documents__created_at"))
    for company in companies.iterator():
        latest_doc = company._latest_doc
        if latest_doc is None:
            value = company.created_at
        else:
            value = max(company.created_at, latest_doc)
        Company.objects.filter(pk=company.pk).update(last_activity_at=value)


class Migration(migrations.Migration):

    dependencies = [
        ("companies", "0001_initial"),
        ("documents", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="company",
            name="last_activity_at",
            field=models.DateTimeField(
                auto_now=True,
                default=django.utils.timezone.now,
            ),
            preserve_default=False,
        ),
        migrations.RunPython(
            backfill_last_activity,
            migrations.RunPython.noop,
        ),
    ]
```

- [ ] **Step 5: Verify migration state is consistent**

Run: `just manage makemigrations --check --dry-run`
Expected: exits 0 with "No changes detected" (the hand-written migration already matches the model; no additional migration is needed).

- [ ] **Step 6: Run tests to verify they pass**

Run: `just test collateral_ai/companies/tests/test_models.py -v`
Expected: PASS (pytest-django applies the new migration to the test DB).

- [ ] **Step 7: Manually verify the backfill on a seeded row**

The backfill has no automated migration test (the project has no migration-testing tooling). Verify it directly:

Run:
```bash
just up
just migrate
just manage shell -c "from collateral_ai.companies.models import Company; from django.utils import timezone; import datetime; c = Company.objects.create(name='Backfill Probe'); Company.objects.filter(pk=c.pk).update(last_activity_at=timezone.now() - datetime.timedelta(days=30)); c.refresh_from_db(); print('OK' if c.last_activity_at is not None else 'MISSING')"
```
Expected: prints `OK` (column exists and is populated; existing rows were backfilled by the RunPython step when `just migrate` applied `0002`).

- [ ] **Step 8: Commit**

```bash
git add backend/collateral_ai/companies/models.py backend/collateral_ai/companies/migrations/0002_company_last_activity_at.py backend/collateral_ai/companies/tests/test_models.py
git commit -m "feat(companies): add last_activity_at column with backfill"
```

---

### Task 2: Bump `last_activity_at` when a document is added

**Files:**
- Create: `backend/collateral_ai/documents/signals.py`
- Modify: `backend/collateral_ai/documents/apps.py`
- Test: `backend/collateral_ai/documents/tests/test_signals.py`

**Interfaces:**
- Consumes: `Company.last_activity_at` (Task 1).
- Produces: `bump_company_last_activity(sender, instance, created, **kwargs)` receiver — on `Document` create, sets `company.last_activity_at = instance.created_at` via `.update()`.

- [ ] **Step 1: Write the failing test**

Create `backend/collateral_ai/documents/tests/test_signals.py`:

```python
import pytest

from collateral_ai.companies.tests.factories import CompanyFactory
from collateral_ai.documents.tests.factories import DocumentFactory

pytestmark = pytest.mark.django_db


def test_adding_document_bumps_company_last_activity():
    company = CompanyFactory()
    doc = DocumentFactory(company=company)
    company.refresh_from_db()
    assert company.last_activity_at == doc.created_at


def test_bump_uses_latest_document():
    company = CompanyFactory()
    DocumentFactory(company=company)
    latest = DocumentFactory(company=company)
    company.refresh_from_db()
    assert company.last_activity_at == latest.created_at
```

- [ ] **Step 2: Run test to verify it fails**

Run: `just test collateral_ai/documents/tests/test_signals.py -v`
Expected: FAIL — `company.last_activity_at` reflects the company's own creation time (auto_now), not the document's `created_at`, so the `==` assertion fails.

- [ ] **Step 3: Create the signal receiver**

Create `backend/collateral_ai/documents/signals.py`:

```python
from django.db.models.signals import post_save
from django.dispatch import receiver

from collateral_ai.companies.models import Company
from collateral_ai.documents.models import Document


@receiver(post_save, sender=Document)
def bump_company_last_activity(sender, instance, created, **kwargs):
    """Mark a document's company as recently active when the document is added."""
    if not created:
        return
    Company.objects.filter(pk=instance.company_id).update(
        last_activity_at=instance.created_at,
    )
```

- [ ] **Step 4: Register the signal in the app config**

In `backend/collateral_ai/documents/apps.py`, add a `ready()` method that imports the signals module:

```python
from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class DocumentsConfig(AppConfig):
    name = "collateral_ai.documents"
    verbose_name = _("Documents")

    def ready(self):
        from collateral_ai.documents import signals  # noqa: F401
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `just test collateral_ai/documents/tests/test_signals.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/collateral_ai/documents/signals.py backend/collateral_ai/documents/apps.py backend/collateral_ai/documents/tests/test_signals.py
git commit -m "feat(documents): bump company last_activity_at on document add"
```

---

### Task 3: Expose `last_updated` in the company API

**Files:**
- Modify: `backend/collateral_ai/companies/api/serializers.py`
- Test: `backend/collateral_ai/companies/tests/api/test_views.py`

**Interfaces:**
- Consumes: `Company.last_activity_at` (Task 1).
- Produces: API field `last_updated` (read-only ISO datetime) on the `Company` schema — the frontend depends on this exact key.

- [ ] **Step 1: Write the failing test**

Add to `backend/collateral_ai/companies/tests/api/test_views.py` (reuse the file's existing `auth_client` fixture, `CompanyFactory` import, and `HTTPStatus` import — add any that are missing):

```python
def test_company_list_includes_last_updated(auth_client):
    CompanyFactory()
    response = auth_client.get("/api/companies/")
    assert response.status_code == HTTPStatus.OK
    row = response.json()[0]
    assert "last_updated" in row
    assert row["last_updated"] is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `just test collateral_ai/companies/tests/api/test_views.py::test_company_list_includes_last_updated -v`
Expected: FAIL — `KeyError`/assertion: `"last_updated"` is not in the serialized row.

- [ ] **Step 3: Add the serializer field**

In `backend/collateral_ai/companies/api/serializers.py`, declare the field on `CompanySerializer` (next to `logo_url`) and add it to `Meta.fields` and `Meta.read_only_fields`:

```python
class CompanySerializer(serializers.ModelSerializer[Company]):
    logo_url = serializers.SerializerMethodField()
    last_updated = serializers.DateTimeField(
        source="last_activity_at",
        read_only=True,
    )
    # Declared explicitly so the OpenAPI schema types brand_colors as string[]
    # (a bare JSONField would emit a loose type that breaks the typed frontend).
    brand_colors = serializers.ListField(
        child=serializers.CharField(),
        required=False,
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
            "last_updated",
        ]
        read_only_fields = ["id", "created_at", "last_updated"]
        extra_kwargs = {"logo": {"write_only": True, "required": False}}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `just test collateral_ai/companies/tests/api/test_views.py::test_company_list_includes_last_updated -v`
Expected: PASS.

- [ ] **Step 5: Run the full companies test suite (guard against regressions)**

Run: `just test collateral_ai/companies -v`
Expected: PASS (existing CRUD/list tests still green with the added field).

- [ ] **Step 6: Commit**

```bash
git add backend/collateral_ai/companies/api/serializers.py backend/collateral_ai/companies/tests/api/test_views.py
git commit -m "feat(companies): expose last_updated in the API"
```

---

### Task 4: Regenerate the typed OpenAPI schema

**Files:**
- Modify (generated): `frontend/src/lib/api/schema.d.ts`

**Interfaces:**
- Consumes: the `last_updated` API field (Task 3).
- Produces: `readonly last_updated: string` on `components["schemas"]["Company"]` in `schema.d.ts` — makes `c.last_updated` typecheck in the frontend.

- [ ] **Step 1: Ensure the stack is running**

Run: `just up`
Expected: `django` and `frontend` containers are up (the schema is fetched from the live backend `/api/schema/`).

- [ ] **Step 2: Regenerate the frontend API types**

Run: `just gen-api`
Expected: completes without error; `frontend/src/lib/api/schema.d.ts` is rewritten.

- [ ] **Step 3: Verify the new field landed**

Run: `grep -n "last_updated" frontend/src/lib/api/schema.d.ts`
Expected: at least one match inside the `Company:` schema block, e.g. `readonly last_updated: string;`.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/api/schema.d.ts
git commit -m "chore(api): regenerate schema with last_updated"
```

---

### Task 5: `formatRelativeDay` frontend helper

**Files:**
- Create: `frontend/src/lib/format.ts`
- Test: `frontend/src/lib/format.test.ts`

**Interfaces:**
- Produces: `formatRelativeDay(iso: string, now?: Date): string` — returns `Today` / `Yesterday` / `N days ago` / `Last week` / a short date like `24 Jun`. The optional `now` (defaults to `new Date()`) exists so tests are deterministic.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/lib/format.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { formatRelativeDay } from "./format";

const now = new Date("2026-07-08T12:00:00");

describe("formatRelativeDay", () => {
  it("returns Today for the same calendar day", () => {
    expect(formatRelativeDay("2026-07-08T09:00:00", now)).toBe("Today");
  });

  it("returns Yesterday for the previous calendar day", () => {
    expect(formatRelativeDay("2026-07-07T23:00:00", now)).toBe("Yesterday");
  });

  it("counts yesterday across a late-night boundary", () => {
    const lateNow = new Date("2026-07-08T01:00:00");
    expect(formatRelativeDay("2026-07-07T23:00:00", lateNow)).toBe("Yesterday");
  });

  it("returns N days ago for 2-6 days", () => {
    expect(formatRelativeDay("2026-07-06T10:00:00", now)).toBe("2 days ago");
    expect(formatRelativeDay("2026-07-02T10:00:00", now)).toBe("6 days ago");
  });

  it("returns Last week for 7-13 days", () => {
    expect(formatRelativeDay("2026-07-01T10:00:00", now)).toBe("Last week");
    expect(formatRelativeDay("2026-06-25T10:00:00", now)).toBe("Last week");
  });

  it("returns a short date for 14+ days", () => {
    expect(formatRelativeDay("2026-06-24T10:00:00", now)).toBe("24 Jun");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose run --rm frontend pnpm test src/lib/format.test.ts`
Expected: FAIL — cannot resolve `./format` (module does not exist yet).

- [ ] **Step 3: Write the helper**

Create `frontend/src/lib/format.ts`:

```ts
/** Format an ISO timestamp as a short relative-day label: "Today",
 *  "Yesterday", "N days ago", "Last week", or a short date like "24 Jun". */
export function formatRelativeDay(iso: string, now: Date = new Date()): string {
  const then = new Date(iso);
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const startOfThen = new Date(
    then.getFullYear(),
    then.getMonth(),
    then.getDate(),
  );
  const dayMs = 24 * 60 * 60 * 1000;
  const days = Math.round(
    (startOfToday.getTime() - startOfThen.getTime()) / dayMs,
  );

  if (days <= 0) return "Today";
  if (days === 1) return "Yesterday";
  if (days < 7) return `${days} days ago`;
  if (days < 14) return "Last week";
  return then.toLocaleDateString("en-GB", { day: "numeric", month: "short" });
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose run --rm frontend pnpm test src/lib/format.test.ts`
Expected: PASS (all cases green).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/format.ts frontend/src/lib/format.test.ts
git commit -m "feat(frontend): add formatRelativeDay helper"
```

---

### Task 6: Add the "Last updated" column to the list page

**Files:**
- Modify: `frontend/src/routes/companies-list.tsx`

**Interfaces:**
- Consumes: `formatRelativeDay` (Task 5), `c.last_updated` from the `Company` type (Task 4).

- [ ] **Step 1: Import the helper**

At the top of `frontend/src/routes/companies-list.tsx`, add below the existing `useDebouncedValue` import:

```tsx
import { formatRelativeDay } from "@/lib/format";
```

- [ ] **Step 2: Widen the header grid and add the header cell**

Replace the header row block:

```tsx
        <div className="grid grid-cols-[2fr_1fr_1fr_auto] gap-4 border-b border-hairline bg-subtle px-5 py-3 text-[11px] font-semibold uppercase tracking-wide text-faint">
          <span>Company</span>
          <span>Industry</span>
          <span>Website</span>
          <span className="w-4" />
        </div>
```

with:

```tsx
        <div className="grid grid-cols-[2fr_1fr_1fr_1fr_auto] gap-4 border-b border-hairline bg-subtle px-5 py-3 text-[11px] font-semibold uppercase tracking-wide text-faint">
          <span>Company</span>
          <span>Industry</span>
          <span>Website</span>
          <span>Last updated</span>
          <span className="w-4" />
        </div>
```

- [ ] **Step 3: Widen the row grid and add the data cell**

Replace the row `<Link>` block:

```tsx
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
```

with:

```tsx
          <Link
            key={c.id}
            to="/companies/$companyId"
            params={{ companyId: String(c.id) }}
            className="grid grid-cols-[2fr_1fr_1fr_1fr_auto] items-center gap-4 border-b border-hairline px-5 py-[14px] last:border-b-0 hover:bg-subtle"
          >
            <span className="flex items-center gap-3">
              <CompanyLogo name={c.name} logoUrl={c.logo_url} />
              <span className="text-[13.5px] font-semibold text-ink">{c.name}</span>
            </span>
            <span className="text-[13px] text-body">{c.industry || "—"}</span>
            <span className="truncate text-[13px] text-subtext">{c.website || "—"}</span>
            <span className="text-[13px] text-subtext">{formatRelativeDay(c.last_updated)}</span>
            <CaretRight size={14} className="text-faint" />
          </Link>
```

- [ ] **Step 4: Typecheck**

Run: `docker compose run --rm frontend pnpm typecheck`
Expected: PASS — `c.last_updated` is typed as `string` (from Task 4); no TS errors.

- [ ] **Step 5: Visually verify in the running app**

With the stack up (`just up`), open the app, log in, and go to the Companies page. Confirm a "Last updated" column appears between "Website" and the caret, showing values like `Today` / `Yesterday` / `N days ago`. Uploading a document to a company and returning to the list should show that company as `Today`.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/routes/companies-list.tsx
git commit -m "feat(companies): show Last updated column in the list"
```

---

## Self-Review Notes

- **Spec coverage:** model field + auto_now (Task 1), document-add bump (Task 2), backfill migration (Task 1 step 4/7), serializer `last_updated` (Task 3), OpenAPI regen (Task 4), `formatRelativeDay` with the exact design vocabulary (Task 5), the new column keeping Website and current columns (Task 6). Out-of-scope items (Documents count column, dropping Website, ordering change) are intentionally excluded.
- **`bulk_create` caveat (from spec):** confirmed the ingestion upload path uses `Document.objects.create(...)` (fires `post_save`, `created=True`), and the worker only mutates status via queryset `.update()` (no signal) — matching the intended "document added" semantic. `DocumentChunk` bulk_create is irrelevant (not a `Document`). No extra bump call site needed.
- **Backfill testing:** no automated migration test exists in the project; Task 1 Step 7 is an explicit manual verification rather than a claimed unit test.
