# Documents table: split Status and Actions into two columns

**Date:** 2026-07-08
**Scope:** Layout fix only (frontend) — `frontend/src/components/documents-tab.tsx`

## Problem

In the documents table, the `StatusPill` and the two action buttons (Open in new tab,
Delete) are all crammed into a single right-aligned `Status` cell. The icons are bare
(no button chrome, mismatched sizes `15px`/`14px`), so the pill and icons fight for space
under a right-aligned `STATUS` header. This does not match the design bundle.

Reference:
- Current code: `frontend/src/components/documents-tab.tsx:114-176`
- Design: `mvp-frontend-architecture/project/Collate.dc.html:280-284`

In the design, Status and the actions are **two separate columns**: a left-aligned `Status`
column holding only the pill, and a trailing unlabeled `width:76px` column holding the two
actions as `30×30` rounded icon-button chips with a hover background.

## Design

### Table header (`<thead>`)
- Change the `Status` `<th>` from `text-right` to `text-left`.
- Add a trailing empty header cell for actions: `<th className="w-[76px]"></th>`.

### Status cell (`<td>`)
- Left-aligned. Contains only `<StatusPill status={d.status} />`.
- The inline **Retry** button (rendered only when `d.status === "failed"`) stays in this
  cell next to the pill — it is status-related and is kept per scope. Wrap pill + optional
  Retry in a `flex items-center gap-2` container.

### Actions cell (new `<td>`)
- Right-aligned: `flex items-center justify-end gap-1`.
- Two icon-button chips replacing the current bare icons:
  - **Open in new tab** — `ArrowSquareOut` at `size={16}`.
  - **Delete** — `Trash` at `size={16}`.
- Each button: `flex h-[30px] w-[30px] items-center justify-center rounded-lg text-faint`
  (matching the design's `30×30`, `border-radius:8px`, muted default color).
- Hover states map the design's `iconBtnHover` / `iconBtnDangerHover` to existing app
  tokens rather than hardcoded hex:
  - Open: `hover:bg-subtle hover:text-brand`
  - Delete: `hover:bg-danger-soft hover:text-destructive`
- Preserve existing behavior/attributes: Open keeps `disabled={openingId === d.id}`,
  `disabled:opacity-50`, `onClick={() => onOpen(d)}`, `aria-label`, `title`. Delete keeps
  `onClick={() => setDeleteTarget(d)}`, `aria-label`, `title`.

### Out of scope (design differs but intentionally not changed)
- The design's `Type` column.
- The `Uploaded today · time` subtitle under each filename.
- Dropping the inline Retry button (design omits it; we keep it).

### Unchanged
- `StatusPill` component already matches the design — no change.
- Data flow, handlers (`onOpen`, `retry`, `del`, `setDeleteTarget`), and the
  `ConfirmDeleteDialog` are untouched.

## Testing
- Visual check: pill sits under a left-aligned `Status` header; the two actions occupy a
  separate right-aligned column with hover chips.
- Verify a `failed` row still shows the Retry button next to the Failed pill and that Retry
  fires `retry.mutate`.
- Verify Open is disabled while `openingId === d.id` and Delete still opens the confirm dialog.
