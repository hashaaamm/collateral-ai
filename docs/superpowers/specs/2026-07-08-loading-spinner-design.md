# Loading Spinner UI — Design

**Date:** 2026-07-08
**Status:** Approved

## Goal

Replace the plain "Loading…" text shown while API responses are fetched with a
spinner-based UI, using a small reusable component.

## Context

- Frontend: React + Vite + Tailwind v4, components under `frontend/src`.
- Icon library already in use: `@phosphor-icons/react`.
- `src/components/status-pill.tsx` already spins `CircleNotch` with `animate-spin`
  — the established spinner pattern. Build on it; no new dependency.
- `cn()` helper lives in `src/lib/utils.ts`.

## Component

New file: `src/components/ui/spinner.tsx`, two exports.

### `<Spinner size? className? />`
- Spinning icon primitive: `CircleNotch` + `animate-spin`.
- `size` defaults to ~16px. Color inherits `currentColor` so Tailwind text color
  classes (`text-mute`, `text-brand`, …) drive it.
- Used for inline cases.

### `<LoadingState label? className? />`
- Centered flex row: `<Spinner>` + label text (`text-[13px] text-mute`).
- `label` defaults to "Loading…".
- Used for block / full-page loading states.

## Swaps

| Location | Change |
|---|---|
| `components/documents-tab.tsx:109` | `<p>Loading…</p>` → `<LoadingState />` |
| `routes/company-detail.tsx:33` | Keep `max-w-[1080px] px-10 pt-8` wrapper, `<LoadingState>` inside |
| `routes/edit-company.tsx:14` | Keep `max-w-[760px] px-10 pt-8` wrapper, `<LoadingState>` inside |
| `routes/home.tsx:35` | Replace the mid-sentence `isLoading` text branch with inline `<Spinner>` + "Loading current user…" |

## Rationale

One primitive (`Spinner`) plus one convenience wrapper (`LoadingState`) covers both
inline and block cases without duplicated markup. Consistent with existing
`animate-spin` usage; size/color driven by Tailwind classes to fit each context.

## Testing

Small presentational change. Verify by running the frontend and confirming each
loading state renders the spinner. No unit tests exist for these presentational
components.
