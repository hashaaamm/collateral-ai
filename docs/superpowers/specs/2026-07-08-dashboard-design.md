# Dashboard — Design

**Date:** 2026-07-08
**Screen:** #2 in the design handoff (`/dashboard`)
**Status:** Approved

## Purpose

Landing overview for the app. Greets the user, surfaces four workspace stats, shows
recent generated materials, and offers a quick-start card. Replaces the current
placeholder at `frontend/src/routes/dashboard.tsx`.

Materials and review features are not built yet, so the material-related stats and the
recent-materials table are **dummy** placeholders. Everything else is wired to real data.

## Data sources

| Piece | Source | Real / Dummy |
|---|---|---|
| Greeting name | `useCurrentUser()` (already used by the sidebar); fallback "there" | Real |
| Date eyebrow | client-side `Intl.DateTimeFormat` (e.g. "Wednesday, July 8") | Real |
| **Companies** stat | new `GET /api/dashboard/stats/` → `companies_count` | Real |
| **Documents processed** stat | same endpoint → `documents_processed`; sub-line uses `documents_processing` | Real |
| **Materials generated** stat | hardcoded `11`, "+4 this week" (green) | Dummy |
| **Needs review** stat | hardcoded `2`, "Awaiting approval" (amber) | Dummy |
| Recent materials table | 4 hardcoded rows | Dummy |
| Quick start buttons | navigation → `/create` (wizard) and `/companies` | Real |

## Backend

New `dashboard` concern exposing a single read endpoint:

- `GET /api/dashboard/stats/` — an `APIView` (not a model viewset), auth-guarded like the
  rest of the API, returning:
  ```json
  { "companies_count": 6, "documents_processed": 18, "documents_processing": 2 }
  ```
- Computed with aggregate `.count()` queries (companies total; documents filtered by
  `status`). No N+1 — a couple of counts.
- A DRF serializer defines the response shape so it lands in the generated OpenAPI
  schema. Regenerate `frontend/src/lib/api/schema.d.ts` afterward (`pnpm gen:api`).

## Frontend

Layout mirrors `companies-list.tsx`: `mx-auto max-w-[1080px] px-10 pb-[60px] pt-8`.
Structure: greeting block → 4-col stat grid (`gap-4`) → 2-col row (`1.6fr / 1fr`, `gap-5`).

### Components

- **`routes/dashboard.tsx`** — replaces the placeholder; composes the sections and fetches
  stats via a new `useDashboardStats()` query hook (in `lib/api/`).
- **`components/stat-card.tsx`** (new) — label + top-right Phosphor icon (`#b7b7c0`),
  big number (`27px/700`), delta line with tone (`green | muted | amber`). Reused 4×.
  Accepts a `loading` flag → skeleton for the two real stats while the query resolves.
- **Recent materials card** (left, inline in dashboard) — borderless table, 4 dummy rows:
  title (`13px/600`) + "Sender → Receiver" subline (`11.5px`, muted) + right-aligned
  status pill. Header has a "View all" link → `/materials`. Rows are **non-clickable**
  (Result Detail route does not exist yet) — no dead links.
- **Quick start card** (right, inline in dashboard) — heading + one line of copy +
  "Create Material" primary button (→ `/create`) + "Manage Companies" ghost button
  (→ `/companies`).

### Material status pills

The existing `StatusPill` only covers document statuses (processed/processing/failed).
Material statuses (completed / processing / needs_review) differ. To avoid prematurely
committing to a shared material-status component before that feature exists, the dashboard
renders its dummy pills with a small **local** status map. When materials are built, a
proper `MaterialStatusPill` can be extracted then.

Add the two missing status tokens to `frontend/src/index.css` (the design defines them):
- `--color-review: #7c3aed` / `--color-review-soft: #f1eafe`
- `--color-draft: #52525b` / `--color-draft-soft: #f0f0f2`

## Design tokens used

Existing tokens: `ink`, `subtext`, `faint`, `mute`, `body`, `hairline`, `surface`,
`subtle`, `brand`, `brand-hover`, `brand-soft`, `success`, `warning`. New: `review`,
`draft` (above). Fonts, radii, and spacing per the handoff (`docs`: stat card
`bg-surface border border-hairline rounded-2xl p-[18px]`).

## Testing

- **Backend:** test `/api/dashboard/stats/` — asserts counts reflect created
  companies/documents (processed vs processing) and that the endpoint requires auth.
- **Frontend:** render test for the dashboard with a mocked stats response — asserts the
  real numbers render and the quick-start links resolve to `/create` and `/companies`.

## Out of scope (dummy until the feature lands)

Materials-generated & needs-review counts, the recent-materials rows, and any click-through
to Result Detail.
