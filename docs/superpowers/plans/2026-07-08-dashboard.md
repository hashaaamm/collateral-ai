# Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `/dashboard` landing screen — greeting, a 4-stat grid (2 real, 2 dummy), a dummy "Recent materials" table, and a "Quick start" card — backed by a new `GET /api/dashboard/stats/` endpoint.

**Architecture:** A new lightweight `dashboard` backend module exposes a single read-only `APIView` returning aggregate counts (no model, no migration). The frontend adds a typed `fetchDashboardStats()` + `useDashboardStats()` hook against the regenerated OpenAPI schema, a reusable `StatCard`, and rebuilds `routes/dashboard.tsx` per the design handoff. Materials/review features aren't built, so those stats and the recent-materials rows are hardcoded dummy data.

**Tech Stack:** Django REST Framework + drf-spectacular (backend); React + TanStack Router/Query + openapi-fetch + Phosphor icons + Tailwind v4 tokens (frontend). pytest (backend tests), vitest (frontend tests).

## Global Constraints

- Spec: [docs/superpowers/specs/2026-07-08-dashboard-design.md](../specs/2026-07-08-dashboard-design.md).
- Frontend uses the project's named Tailwind tokens (`ink`, `subtext`, `faint`, `mute`, `body`, `hairline`, `surface`, `subtle`, `brand`, `brand-hover`, `brand-soft`, `success`, `warning`) — never raw `[#hex]` where a token exists.
- Icons: `@phosphor-icons/react`, imported per-icon.
- All API hooks go through the typed `api` client (`frontend/src/lib/api/client.ts`); plain async fetch functions are exported and unit-tested by spying on `api.GET` (see `frontend/src/lib/api/documents.test.ts`).
- Backend endpoints require auth by default (DRF default permission → anon gets `403 FORBIDDEN`).
- Backend tests run via `just test <path>`; the frontend via `docker compose run --rm frontend pnpm test` (or `cd frontend && pnpm test` if node is local).
- Page layout matches `frontend/src/routes/companies-list.tsx`: `mx-auto max-w-[1080px] px-10 pb-[60px] pt-8`.

---

### Task 1: Backend `GET /api/dashboard/stats/` endpoint

**Files:**
- Create: `backend/collateral_ai/dashboard/__init__.py` (empty)
- Create: `backend/collateral_ai/dashboard/api/__init__.py` (empty)
- Create: `backend/collateral_ai/dashboard/api/serializers.py`
- Create: `backend/collateral_ai/dashboard/api/views.py`
- Create: `backend/collateral_ai/dashboard/tests/__init__.py` (empty)
- Create: `backend/collateral_ai/dashboard/tests/api/__init__.py` (empty)
- Create: `backend/collateral_ai/dashboard/tests/api/test_views.py`
- Modify: `backend/config/api_router.py`

**Interfaces:**
- Produces: `GET /api/dashboard/stats/` → JSON `{ "companies_count": int, "documents_processed": int, "documents_processing": int }`, auth-required.
- Consumes: `collateral_ai.companies.models.Company`, `collateral_ai.documents.models.Document`, `collateral_ai.documents.statuses.DocumentStatus`.

- [ ] **Step 1: Write the failing tests**

Create `backend/collateral_ai/dashboard/__init__.py`, `backend/collateral_ai/dashboard/api/__init__.py`, `backend/collateral_ai/dashboard/tests/__init__.py`, and `backend/collateral_ai/dashboard/tests/api/__init__.py` as empty files.

Create `backend/collateral_ai/dashboard/tests/api/test_views.py`:

```python
from __future__ import annotations

from http import HTTPStatus

import pytest
from rest_framework.test import APIClient

from collateral_ai.companies.tests.factories import CompanyFactory
from collateral_ai.documents.statuses import DocumentStatus
from collateral_ai.documents.tests.factories import DocumentFactory
from collateral_ai.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def auth_client() -> APIClient:
    client = APIClient()
    client.force_authenticate(user=UserFactory())
    return client


def test_stats_requires_auth():
    resp = APIClient().get("/api/dashboard/stats/")
    assert resp.status_code == HTTPStatus.FORBIDDEN


def test_stats_counts_companies_and_documents_by_status(auth_client):
    CompanyFactory()
    CompanyFactory()
    DocumentFactory(status=DocumentStatus.PROCESSED)
    DocumentFactory(status=DocumentStatus.PROCESSED)
    DocumentFactory(status=DocumentStatus.PROCESSING)
    DocumentFactory(status=DocumentStatus.PENDING)
    DocumentFactory(status=DocumentStatus.FAILED)

    resp = auth_client.get("/api/dashboard/stats/")

    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == {
        "companies_count": 2,
        "documents_processed": 2,
        "documents_processing": 1,
    }


def test_stats_zero_state(auth_client):
    resp = auth_client.get("/api/dashboard/stats/")
    assert resp.json() == {
        "companies_count": 0,
        "documents_processed": 0,
        "documents_processing": 0,
    }
```

> Note: confirm `DocumentFactory` accepts a `status=` kwarg. Inspect `backend/collateral_ai/documents/tests/factories.py` — `DjangoModelFactory` passes through model-field kwargs, so `status=` works.

- [ ] **Step 2: Run tests to verify they fail**

Run: `just test collateral_ai/dashboard/tests/api/test_views.py -v`
Expected: FAIL — `404 NOT FOUND` (URL not wired) / import errors for the not-yet-created module.

- [ ] **Step 3: Write the serializer**

Create `backend/collateral_ai/dashboard/api/serializers.py`:

```python
from rest_framework import serializers


class DashboardStatsSerializer(serializers.Serializer):
    """Read-only aggregate counts for the dashboard stat cards."""

    companies_count = serializers.IntegerField()
    documents_processed = serializers.IntegerField()
    documents_processing = serializers.IntegerField()
```

- [ ] **Step 4: Write the view**

Create `backend/collateral_ai/dashboard/api/views.py`:

```python
from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from collateral_ai.companies.models import Company
from collateral_ai.documents.models import Document
from collateral_ai.documents.statuses import DocumentStatus

from .serializers import DashboardStatsSerializer


class DashboardStatsView(APIView):
    """Aggregate counts powering the dashboard's stat cards."""

    @extend_schema(responses=DashboardStatsSerializer)
    def get(self, request: Request) -> Response:
        data = {
            "companies_count": Company.objects.count(),
            "documents_processed": Document.objects.filter(
                status=DocumentStatus.PROCESSED,
            ).count(),
            "documents_processing": Document.objects.filter(
                status=DocumentStatus.PROCESSING,
            ).count(),
        }
        return Response(DashboardStatsSerializer(data).data)
```

- [ ] **Step 5: Wire the URL**

Modify `backend/config/api_router.py`. Add the import near the other view imports:

```python
from collateral_ai.dashboard.api.views import DashboardStatsView
```

Add `path` to the imports from django at the top of the file:

```python
from django.urls import path
```

Change the final `urlpatterns` line from:

```python
urlpatterns = router.urls + companies_router.urls
```

to:

```python
urlpatterns = [
    *router.urls,
    *companies_router.urls,
    path("dashboard/stats/", DashboardStatsView.as_view(), name="dashboard-stats"),
]
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `just test collateral_ai/dashboard/tests/api/test_views.py -v`
Expected: PASS (3 passed).

- [ ] **Step 7: Commit**

```bash
git add backend/collateral_ai/dashboard backend/config/api_router.py
git commit -m "feat(dashboard): add GET /api/dashboard/stats/ aggregate endpoint"
```

---

### Task 2: Frontend stats data layer (regen schema + hook)

**Files:**
- Modify: `frontend/src/lib/api/schema.d.ts` (regenerated — do not hand-edit)
- Create: `frontend/src/lib/api/dashboard.ts`
- Create: `frontend/src/lib/api/dashboard.test.ts`

**Interfaces:**
- Consumes: `GET /api/dashboard/stats/` from Task 1 (must be present in the regenerated schema).
- Produces:
  - `type DashboardStats = components["schemas"]["DashboardStats"]` — `{ companies_count: number; documents_processed: number; documents_processing: number }`.
  - `fetchDashboardStats(): Promise<DashboardStats>` — plain async fn used by the hook and unit-tested.
  - `useDashboardStats()` — `useQuery` wrapper, `queryKey: ["dashboard-stats"]`.

- [ ] **Step 1: Regenerate the OpenAPI schema**

The endpoint must exist in `schema.d.ts` before the typed client will accept the path. With the backend serving `/api/schema/`:

Run:
```bash
just up            # starts django + postgres + frontend
just gen-api       # docker compose run --rm frontend pnpm gen:api
```
Expected: `frontend/src/lib/api/schema.d.ts` now contains a `"/api/dashboard/stats/"` path and a `DashboardStats` schema with the three integer fields. Verify:
```bash
grep -n "dashboard/stats" frontend/src/lib/api/schema.d.ts
grep -n "DashboardStats" frontend/src/lib/api/schema.d.ts
```
Expected: both grep hits are non-empty.

- [ ] **Step 2: Write the failing test**

Create `frontend/src/lib/api/dashboard.test.ts`:

```ts
import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchDashboardStats } from "./dashboard";
import { api } from "./client";

afterEach(() => vi.restoreAllMocks());

describe("fetchDashboardStats", () => {
  it("GETs /api/dashboard/stats/ and returns the counts", async () => {
    const get = vi.spyOn(api, "GET").mockResolvedValue({
      data: {
        companies_count: 6,
        documents_processed: 18,
        documents_processing: 2,
      },
      error: undefined,
    } as never);

    const stats = await fetchDashboardStats();

    expect(get).toHaveBeenCalledWith("/api/dashboard/stats/", {});
    expect(stats).toEqual({
      companies_count: 6,
      documents_processed: 18,
      documents_processing: 2,
    });
  });

  it("throws when the request errors", async () => {
    vi.spyOn(api, "GET").mockResolvedValue({
      data: undefined,
      error: { detail: "boom" },
    } as never);

    await expect(fetchDashboardStats()).rejects.toBeDefined();
  });
});
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `docker compose run --rm frontend pnpm test src/lib/api/dashboard.test.ts`
Expected: FAIL — cannot resolve `./dashboard` (module not created yet).

- [ ] **Step 4: Write the hook module**

Create `frontend/src/lib/api/dashboard.ts`:

```ts
import { useQuery } from "@tanstack/react-query";
import type { components } from "./schema";
import { api } from "./client";

export type DashboardStats = components["schemas"]["DashboardStats"];

export async function fetchDashboardStats(): Promise<DashboardStats> {
  const { data, error } = await api.GET("/api/dashboard/stats/", {});
  if (error || !data) throw error ?? new Error("dashboard_stats_failed");
  return data;
}

export function useDashboardStats() {
  return useQuery({
    queryKey: ["dashboard-stats"],
    queryFn: fetchDashboardStats,
  });
}
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `docker compose run --rm frontend pnpm test src/lib/api/dashboard.test.ts`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/api/schema.d.ts frontend/src/lib/api/dashboard.ts frontend/src/lib/api/dashboard.test.ts
git commit -m "feat(dashboard): typed useDashboardStats hook + regenerated schema"
```

---

### Task 3: StatCard component + status tokens

**Files:**
- Modify: `frontend/src/index.css`
- Create: `frontend/src/components/stat-card.tsx`

**Interfaces:**
- Produces: `StatCard` component:
  ```ts
  function StatCard(props: {
    label: string;
    value: number | string;
    Icon: Icon;              // phosphor icon component type
    delta: string;
    tone?: "success" | "warning" | "muted";  // delta color; default "muted"
    loading?: boolean;       // renders a skeleton value + delta
  }): JSX.Element
  ```
- Consumes: `@phosphor-icons/react` `Icon` type.

- [ ] **Step 1: Add the missing status tokens**

Modify `frontend/src/index.css`. In the `@theme { … }` block, directly after the `--color-danger-soft: #fbe9e9;` line, add:

```css
  --color-review: #7c3aed;
  --color-review-soft: #f1eafe;
  --color-draft: #52525b;
  --color-draft-soft: #f0f0f2;
```

- [ ] **Step 2: Write the StatCard component**

Create `frontend/src/components/stat-card.tsx`:

```tsx
import type { Icon } from "@phosphor-icons/react";

const TONE: Record<string, string> = {
  success: "text-success",
  warning: "text-warning",
  muted: "text-mute",
};

export function StatCard({
  label,
  value,
  Icon,
  delta,
  tone = "muted",
  loading = false,
}: {
  label: string;
  value: number | string;
  Icon: Icon;
  delta: string;
  tone?: "success" | "warning" | "muted";
  loading?: boolean;
}) {
  return (
    <div className="rounded-2xl border border-hairline bg-surface p-[18px]">
      <div className="flex items-start justify-between">
        <span className="text-[12.5px] text-subtext">{label}</span>
        <Icon size={18} weight="regular" className="text-faint" />
      </div>
      {loading ? (
        <div className="mt-2 h-[27px] w-12 animate-pulse rounded bg-subtle" />
      ) : (
        <div className="mt-2 text-[27px] font-bold leading-none text-ink">{value}</div>
      )}
      <div className={`mt-[7px] text-[12px] ${loading ? "text-faint" : TONE[tone]}`}>
        {loading ? "—" : delta}
      </div>
    </div>
  );
}
```

> `Icon` is the phosphor icon component *type* (each icon like `Buildings` is assignable to it). If `Icon` is not exported by the installed `@phosphor-icons/react` version, replace the import with `import type { ComponentType } from "react";` and type the prop as `ComponentType<{ size?: number; weight?: string; className?: string }>`. Verify the export first: `grep -n "export.*Icon" frontend/node_modules/@phosphor-icons/react/dist/index.d.ts`.

- [ ] **Step 3: Verify it typechecks**

Run: `docker compose run --rm frontend pnpm exec tsc -p tsconfig.json --noEmit`
Expected: no errors referencing `stat-card.tsx`.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/index.css frontend/src/components/stat-card.tsx
git commit -m "feat(dashboard): StatCard component + review/draft status tokens"
```

---

### Task 4: Dashboard page assembly

**Files:**
- Modify: `frontend/src/routes/dashboard.tsx` (replace the placeholder)

**Interfaces:**
- Consumes: `useDashboardStats()` (Task 2), `StatCard` (Task 3), `useCurrentUser` (`@/lib/api/queries`), TanStack Router `Link`, Phosphor icons.

- [ ] **Step 1: Replace the dashboard route**

Replace the entire contents of `frontend/src/routes/dashboard.tsx` with:

```tsx
import { Link } from "@tanstack/react-router";
import {
  Buildings,
  FileText,
  MagicWand,
  Flag,
  CheckCircle,
  CircleNotch,
  ArrowRight,
} from "@phosphor-icons/react";

import { StatCard } from "@/components/stat-card";
import { useDashboardStats } from "@/lib/api/dashboard";
import { useCurrentUser } from "@/lib/api/queries";

/** Dummy recent materials — the materials feature isn't built yet. */
type MaterialStatus = "completed" | "processing" | "needs_review";

const RECENT: Array<{
  title: string;
  sender: string;
  receiver: string;
  status: MaterialStatus;
}> = [
  { title: "AI for Smarter Logistics", sender: "Acme AI", receiver: "DHL Logistics", status: "completed" },
  { title: "Predictive Demand Planning", sender: "Acme AI", receiver: "RetailCo", status: "processing" },
  { title: "Secure AI Infrastructure", sender: "CloudSec", receiver: "Acme AI", status: "needs_review" },
  { title: "Financial Forecasting, Automated", sender: "NordFinance", receiver: "DHL Logistics", status: "completed" },
];

const MATERIAL_PILL: Record<
  MaterialStatus,
  { label: string; cls: string; Icon: typeof CheckCircle; spin?: boolean }
> = {
  completed: { label: "Completed", cls: "text-success bg-success-soft", Icon: CheckCircle },
  processing: { label: "Processing", cls: "text-warning bg-warning-soft", Icon: CircleNotch, spin: true },
  needs_review: { label: "Needs Review", cls: "text-review bg-review-soft", Icon: Flag },
};

function MaterialPill({ status }: { status: MaterialStatus }) {
  const s = MATERIAL_PILL[status];
  return (
    <span
      className={`inline-flex items-center gap-[5px] rounded-full px-[10px] py-[3px] text-[11.5px] font-semibold ${s.cls}`}
    >
      <s.Icon size={13} weight="fill" className={s.spin ? "animate-spin" : ""} />
      {s.label}
    </span>
  );
}

function greeting(hour: number): string {
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

export function DashboardPage() {
  const { data: user } = useCurrentUser();
  const { data: stats, isLoading } = useDashboardStats();

  const now = new Date();
  const dateLabel = new Intl.DateTimeFormat("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
  }).format(now);
  const firstName = user?.name?.trim().split(/\s+/)[0] || "there";

  return (
    <div className="mx-auto max-w-[1080px] px-10 pb-[60px] pt-8">
      {/* Greeting */}
      <div className="mb-6">
        <div className="text-[13px] text-mute">{dateLabel}</div>
        <h1 className="mt-1 text-[26px] font-bold tracking-[-0.03em] text-ink">
          {greeting(now.getHours())}, {firstName}
        </h1>
      </div>

      {/* Stat grid */}
      <div className="mb-5 grid grid-cols-4 gap-4">
        <StatCard
          label="Companies"
          value={stats?.companies_count ?? 0}
          Icon={Buildings}
          delta="Reusable context"
          tone="muted"
          loading={isLoading}
        />
        <StatCard
          label="Documents processed"
          value={stats?.documents_processed ?? 0}
          Icon={FileText}
          delta={
            stats?.documents_processing
              ? `${stats.documents_processing} processing`
              : "All processed"
          }
          tone="muted"
          loading={isLoading}
        />
        <StatCard
          label="Materials generated"
          value={11}
          Icon={MagicWand}
          delta="+4 this week"
          tone="success"
        />
        <StatCard
          label="Needs review"
          value={2}
          Icon={Flag}
          delta="Awaiting approval"
          tone="warning"
        />
      </div>

      {/* Recent materials + Quick start */}
      <div className="grid grid-cols-[1.6fr_1fr] gap-5">
        {/* Recent materials (dummy) */}
        <div className="rounded-2xl border border-hairline bg-surface p-5">
          <div className="mb-1 flex items-center justify-between">
            <h2 className="text-[15px] font-semibold text-ink">Recent materials</h2>
            <Link to="/materials" className="text-[12.5px] text-brand hover:underline">
              View all
            </Link>
          </div>
          <div>
            {RECENT.map((m) => (
              <div
                key={m.title}
                className="flex items-center justify-between rounded-lg px-2 py-[11px] hover:bg-subtle"
              >
                <div>
                  <div className="text-[13px] font-semibold text-ink">{m.title}</div>
                  <div className="text-[11.5px] text-mute">
                    {m.sender} → {m.receiver}
                  </div>
                </div>
                <MaterialPill status={m.status} />
              </div>
            ))}
          </div>
        </div>

        {/* Quick start */}
        <div className="rounded-2xl border border-hairline bg-surface p-5">
          <h2 className="text-[15px] font-semibold text-ink">Quick start</h2>
          <p className="mt-1 text-[13px] text-subtext">
            Generate a tailored marketing article, or manage the company context it draws from.
          </p>
          <div className="mt-4 flex flex-col gap-2">
            <Link
              to="/create"
              className="flex items-center justify-center gap-[7px] rounded-[10px] bg-brand px-[15px] py-[10px] text-[13.5px] font-semibold text-white hover:bg-brand-hover"
            >
              <MagicWand weight="fill" size={15} />
              Create Material
            </Link>
            <Link
              to="/companies"
              className="flex items-center justify-center gap-[7px] rounded-[10px] border border-field px-[15px] py-[10px] text-[13.5px] font-semibold text-body hover:bg-nav-hover"
            >
              Manage Companies
              <ArrowRight weight="bold" size={14} />
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
```

> Confirm the Phosphor icon names resolve in the installed version (`Buildings`, `FileText`, `MagicWand`, `Flag`, `CheckCircle`, `CircleNotch`, `ArrowRight`). `Buildings`, `CheckCircle`, `CircleNotch`, `MagicWand`, `ArrowRight`, `Plus` are already used elsewhere in the codebase. If `FileText` or `Flag` are missing, substitute `FilePdf` / `FlagBanner` respectively.

- [ ] **Step 2: Typecheck**

Run: `docker compose run --rm frontend pnpm exec tsc -p tsconfig.json --noEmit`
Expected: no errors. (`to="/create"` and `to="/materials"` must be valid registered routes — both exist in `frontend/src/router.tsx`.)

- [ ] **Step 3: Lint**

Run: `docker compose run --rm frontend pnpm exec eslint src/routes/dashboard.tsx src/components/stat-card.tsx`
Expected: no errors.

- [ ] **Step 4: Verify in the running app**

With `just up` running and the local stack seeded/logged in, open `http://localhost:<frontend-port>/dashboard`. Confirm:
- Greeting shows today's date + the logged-in user's first name.
- Companies + Documents stats show live counts (create a company/document to see them move); Materials(11)/Needs review(2) show the dummy values.
- Recent-materials rows render with correct status pills; "View all" links to `/materials`.
- "Create Material" → `/create`, "Manage Companies" → `/companies`.

> Per the deploy-smoke memory: hard-refresh to avoid a stale bundle before concluding anything is wrong.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/routes/dashboard.tsx
git commit -m "feat(dashboard): build /dashboard screen (real stats + dummy materials)"
```

---

## Self-Review

- **Spec coverage:** greeting (Task 4) ✓; real Companies + Documents stats via new endpoint (Tasks 1–2, wired in Task 4) ✓; dummy Materials/Needs-review stats (Task 4) ✓; dummy non-clickable recent-materials table with local status pills + "View all" → `/materials` (Task 4) ✓; Quick start → `/create` + `/companies` (Task 4) ✓; `StatCard` reusable + loading skeleton (Task 3) ✓; `review`/`draft` tokens (Task 3) ✓; backend endpoint + tests (Task 1) ✓; frontend hook + test (Task 2) ✓.
- **Placeholder scan:** none — all code blocks are complete; dummy data is explicit and intentional per spec.
- **Type consistency:** `DashboardStats` fields (`companies_count`, `documents_processed`, `documents_processing`) are identical across the serializer (Task 1), the generated type + hook (Task 2), and consumption (Task 4). `StatCard` prop names/`tone` union match between Task 3 definition and Task 4 usage. `MaterialStatus` union matches its pill map.
