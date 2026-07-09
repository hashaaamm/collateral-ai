# Dashboard real-data wiring

**Date:** 2026-07-09
**Status:** Approved

## Goal

Remove all dummy data from the dashboard so every stat card and the recent-materials
feed is backed by real APIs. Today the dashboard's first two stat cards are already
real, but "Materials generated" and "Needs review" are hardcoded, and the entire
"Recent materials" list is a fake in-file array.

## Current state

`frontend/src/routes/dashboard.tsx`:

- **Companies** stat — real (`stats.companies_count`).
- **Documents processed** stat — real (`stats.documents_processed` / `documents_processing`).
- **Materials generated** stat — hardcoded `11`, fake delta `"+4 this week"`.
- **Needs review** stat — hardcoded `2`, fake delta `"Awaiting approval"`.
- **Recent materials** — the entire `RECENT` array is fabricated.

Available real APIs:

- `GET /api/dashboard/stats/` → `companies_count`, `documents_processed`, `documents_processing`.
- `GET /api/materials/` → all materials, ordered `-created_at` (newest first), each with
  `title`, `sender_company` / `receiver_company` (`CompanySummary` with `name`),
  `generation_status`, `review_status`, `created_at`.

## Design

### 1. Backend — extend the stats endpoint

Add two integer fields to the dashboard stats contract.

`backend/collateral_ai/dashboard/api/serializers.py` — add to `DashboardStatsSerializer`:

- `materials_generated = serializers.IntegerField()`
- `materials_needs_review = serializers.IntegerField()`

`backend/collateral_ai/dashboard/api/views.py` — `DashboardStatsView.get` adds:

- `"materials_generated"`: `MarketingMaterial.objects.filter(generation_status=GenerationStatus.COMPLETED).count()`
- `"materials_needs_review"`: `MarketingMaterial.objects.filter(review_status=ReviewStatus.PENDING).count()`

Import `MarketingMaterial` from `collateral_ai.materials.models` and the status
constants from `collateral_ai.materials.statuses` (`GenerationStatus.COMPLETED = "completed"`,
`ReviewStatus.PENDING = "pending"`).

`backend/collateral_ai/dashboard/tests/api/test_views.py` — extend the fixtures to
create materials in known states and assert the two new counts (both the populated
case and the zero case).

Regenerate the frontend typed client: `just gen-api`. This updates
`frontend/src/lib/api/schema.d.ts` so `DashboardStats` gains the two fields
automatically; `frontend/src/lib/api/dashboard.ts` needs no change (it re-exports the
schema type).

### 2. Frontend — stat cards

`frontend/src/routes/dashboard.tsx`:

- **Materials generated** card → `value={stats?.materials_generated ?? 0}`, `loading={isLoading}`,
  no caption.
- **Needs review** card → `value={stats?.materials_needs_review ?? 0}`, `loading={isLoading}`,
  `tone="warning"`, no caption.
- The **Companies** and **Documents processed** cards keep their existing captions unchanged.

`frontend/src/components/stat-card.tsx`:

- Make `delta` optional (`delta?: string`).
- When `delta` is absent (and not loading), render an empty spacer occupying the same
  vertical space as the caption line so all four cards in the grid stay the same height.
  When loading, keep the existing `"—"` placeholder behavior.

### 3. Frontend — Recent materials

`frontend/src/routes/dashboard.tsx`:

- Delete the `RECENT` dummy array and the `MaterialStatus` literal union tied to it.
- Fetch via the existing `useMaterials()` hook (`frontend/src/lib/api/materials.ts`).
  Take the newest 4 items (`data?.slice(0, 4)`); the list is already ordered newest-first.
- Each row: `title` as the label; subtitle `sender_company.name → receiver_company.name`.
- **Status pill** derived per row (generation first, then review):
  1. still generating (`generation_status` is `queued` or `processing`, via the existing
     `isGenerating` helper) → **Processing**
  2. `generation_status === "failed"` → **Failed**
  3. `review_status === "pending"` → **Needs Review**
  4. otherwise → **Completed**
- Add a **Failed** pill variant to `MATERIAL_PILL` (existing variants: completed,
  processing, needs_review). Use the existing danger/review design tokens for styling
  and a suitable Phosphor icon (e.g. `WarningCircle`).
- **Loading state**: while `useMaterials()` is loading, render 4 skeleton rows.
- **Empty state**: when there are no materials, render a short "No materials yet" message
  in the card body.
- The "View all" link to `/materials` is unchanged.

### Status pill mapping table

| Condition (checked in order) | Pill |
| --- | --- |
| `generation_status` ∈ {queued, processing} | Processing |
| `generation_status` == failed | Failed |
| `review_status` == pending | Needs Review |
| else | Completed |

## Out of scope

- Weekly-delta aggregates (no `"+N this week"` numbers).
- Any new endpoints — recent materials reuses `GET /api/materials/`.
- Changes to the Quick start card or the greeting header.

## Testing

- Backend: `test_views.py` covers the two new counts (populated + zero cases) via
  `just test`.
- Frontend: `dashboard.test.ts` (and/or a component test) verifies stat cards read the
  new fields and that the recent-materials pill derivation picks the correct pill for
  each of the four conditions, plus loading and empty states.

## Verification

Run the stack locally and confirm the dashboard renders real counts and real recent
materials (no hardcoded `11` / `2`, no fabricated company names), including the empty
state when no materials exist.
