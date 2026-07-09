# Standardize delete/remove popups

**Date:** 2026-07-09
**Goal:** Every delete/remove confirmation in the frontend uses one consistent popup — the plain "Delete material" look the user liked — sourced from a single shared component. No bespoke delete dialogs remain, and the two (three) remove actions that previously had no confirmation gain one.

## Background

The frontend (React + TanStack Router, `frontend/src`) had three different delete/remove treatments:

1. **Bespoke inline `AlertDialog`** — the "Delete material" popup on `material-detail.tsx`. Plain: no icon, neutral Delete button, no loading state. **This is the reference look.**
2. **Shared `ConfirmDeleteDialog`** — used by Delete document and Delete company. Richer: red trash-icon badge, red destructive button, loading state, `size="sm"`.
3. **No confirmation at all** — removing a template body-section, removing a template image-slot, and removing a brand color all mutate local state directly.

## Decisions

- **Standard look = the plain material popup** (user choice): no `AlertDialogMedia` badge, default content size, neutral action button, no trash icon inside the button.
- **Keep the `loading` prop/behavior** in the shared component. It is behavior, not look; dropping it would regress the document/company network deletes (buttons must disable + the dialog must stay mounted during the mutation). The material dialog never needed it because it navigates away on success — harmless to retain.
- **Add confirmation to all inline remove actions** (user choice), applied consistently to all three: brand color, template body-section, template image-slot.

## Design

### 1. Restyle `frontend/src/components/confirm-delete-dialog.tsx`

Reshape to the plain look while keeping the same props (`open`, `onOpenChange`, `title`, `description`, `confirmLabel?`, `loading?`, `onConfirm`):

- Remove `AlertDialogMedia` + the `Trash` badge import.
- `AlertDialogContent` → default size (drop `size="sm"`).
- Action button → default variant (drop `variant="destructive"`), no `Trash` icon inside; render just `{confirmLabel}`.
- Keep `loading` disabling both buttons and the `e.preventDefault()` that keeps the dialog mounted during the mutation.

Document & company deletes automatically inherit the new look — no changes needed there.

### 2. Migrate "Delete material" (`frontend/src/routes/material-detail.tsx`)

Replace the bespoke `AlertDialog` (lines ~366–392) with:
- A local `const [confirmOpen, setConfirmOpen] = useState(false)`.
- The existing rail button becomes a plain `<button onClick={() => setConfirmOpen(true)}>` (same styling/label/icon).
- A `<ConfirmDeleteDialog>` with `title="Delete material?"`, the existing description, `loading={del.isPending}`, and `onConfirm` running the delete mutation → navigate to `/materials` on success.
- Drop the now-unused `AlertDialog*` imports that were only used by the delete dialog (keep the ones still used by `EditPromptDialog`).

### 3. Add confirmation — `frontend/src/routes/template-new.tsx`

Introduce one page-level pending-action state:
```ts
const [pending, setPending] = useState<{ title: string; description: ReactNode; onConfirm: () => void } | null>(null);
```
- Body-section remove (`textRow` `onRemove`) and image-slot remove (`onClick` at the slot row) set `pending` instead of mutating directly.
- Render a single `<ConfirmDeleteDialog open={pending !== null} onOpenChange={(o) => !o && setPending(null)} title=... description=... onConfirm={() => { pending?.onConfirm(); setPending(null); }} />`.
- Titles: `"Remove field?"` / `"Remove image slot?"`, `confirmLabel="Remove"`.

### 4. Add confirmation — `frontend/src/components/company-form.tsx`

Same single-pending-action pattern for the brand-color remove button (the `X` at line ~163): set `pending` → confirm removes the color. `title="Remove color?"`, `confirmLabel="Remove"`.

## Out of scope

- The `EditPromptDialog` (edit, not delete) stays a bespoke `AlertDialog`.
- No backend changes.

## Verification

- `npm run build` (or the frontend's typecheck/lint) passes with no unused-import errors.
- Manual/preview smoke: each of the five flows opens the identical plain popup; Cancel dismisses; confirm performs the action; network deletes disable buttons while pending.

## After implementation

Commit, merge the branch to `main`, and deploy (per user instruction "after that merge and deploy").
