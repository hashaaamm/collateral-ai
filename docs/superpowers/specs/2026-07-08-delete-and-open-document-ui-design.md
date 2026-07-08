# Delete pop screen, open document, and company delete restyle

**Date:** 2026-07-08
**Branch/worktree:** `claude/delete-ui-documents-company-7ba153` (isolated worktree)

## Goal

Three related UI changes on the company-detail surface:

1. Replace the document-delete `window.confirm()` with the new "pop screen"
   confirmation dialog from the design.
2. Reuse that same dialog for company delete (restyle the current plain
   `AlertDialog`).
3. Add an "Open in new tab" action per document row: fetch a signed GCS GET URL
   and open the PDF in a new browser tab.

## Context / current state

- Document delete: `frontend/src/components/documents-tab.tsx` uses
  `window.confirm(...)` then `useDeleteDocument()`.
- Company delete: `frontend/src/routes/company-detail.tsx` already uses a Radix
  `AlertDialog` — but plain text, not the design's pop screen.
- Design source: `mvp-frontend-architecture/project/Collate.dc.html:673` — the
  delete modal (soft-red trash icon tile, title "Delete document?", bold
  filename in body, Cancel + red Delete buttons). Line 282 shows the per-row
  "Open in new tab" button (`ph-arrow-square-out`).
- Backend: `collateral_ai/companies/gcs.py` already has
  `signed_get_url(object_path)` (V4 GET, 15-min `GET_EXPIRY`).
  `collateral_ai/documents/gcs.py` re-exports upload/delete/is_configured but
  **not** `signed_get_url`. No download endpoint exists yet.
- `DocumentViewSet` (`collateral_ai/documents/api/views.py`) is a
  List/Retrieve/Create/Destroy viewset nested under companies.

## Decisions

- Company delete **is** restyled to the shared pop-screen dialog (user: "use the
  same for both").
- The Open button shows on **any uploaded document** (has `storage_path`),
  regardless of processing status — the PDF is uploaded to GCS before processing.
- Download endpoint returns JSON `{ "url": ... }` (mirrors the existing
  upload-url pattern); the frontend controls the new-tab open. No server-side
  redirect.

## Section 1 — Backend: signed download URL

**File:** `backend/collateral_ai/documents/gcs.py`
- Add `signed_get_url` to the re-export list from `companies.gcs`.

**File:** `backend/collateral_ai/documents/api/views.py`
- New action on `DocumentViewSet`:

```python
@extend_schema(
    responses=inline_serializer(
        name="DocumentDownloadResponse",
        fields={"url": serializers.URLField()},
    ),
)
@action(detail=True, methods=["get"], url_path="download-url")
def download_url(self, request, pk=None, company_pk=None):
    doc = self.get_object()
    if not doc.storage_path or not gcs.is_configured():
        return Response(
            {"detail": "Document download is not available in this environment."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    return Response({"url": gcs.signed_get_url(doc.storage_path)})
```

- Route (auto from router): `GET /api/companies/{company_pk}/documents/{id}/download-url/`.

**Tests** (`backend/collateral_ai/documents/tests/api/`):
- 200 + `url` present when gcs configured and doc has `storage_path`.
- 503 when gcs not configured (or no storage_path).
- Scoped to company (a doc from another company is 404 via the existing
  `get_queryset` filter).

## Section 2 — Frontend: shared `ConfirmDeleteDialog`

**New file:** `frontend/src/components/confirm-delete-dialog.tsx`

Wraps the existing Radix `AlertDialog` primitives
(`frontend/src/components/ui/alert-dialog.tsx`, which already provides
`AlertDialogMedia`) into the design's pop screen. Controlled component.

Props:
```ts
{
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: React.ReactNode;   // may contain a bold entity name
  confirmLabel?: string;          // default "Delete"
  loading?: boolean;
  onConfirm: () => void;
}
```

Layout: `AlertDialogContent` (size `sm`/centered) → `AlertDialogMedia` with a
soft-red rounded tile + destructive trash icon → `AlertDialogTitle` →
`AlertDialogDescription` → footer with `AlertDialogCancel` ("Cancel") and a
destructive `AlertDialogAction` (`confirmLabel`, trash icon, disabled while
`loading`). Uses existing Phosphor icons and theme tokens (`text-destructive`,
etc.) consistent with the rest of the app.

## Section 3 — Frontend: documents-tab wiring

**File:** `frontend/src/lib/api/documents.ts`
- Add `getDocumentDownloadUrl(companyId: number, id: number): Promise<string>` —
  `GET /api/companies/{company_pk}/documents/{id}/download-url/`, returns
  `data.url`; throws on error (e.g. `download_unavailable`).

**File:** `frontend/src/components/documents-tab.tsx`
- **Open button:** new icon button (`ArrowSquareOut`) per row, shown for any doc.
  Click handler opens the tab synchronously to dodge popup blockers, then sets
  its location once the signed URL resolves:
  ```ts
  const w = window.open("", "_blank", "noopener,noreferrer");
  try {
    const url = await getDocumentDownloadUrl(companyId, d.id);
    if (w) w.location.href = url;
  } catch {
    w?.close();
    setError("Couldn't open the document. Try again.");
  }
  ```
  Per-row loading state (disable the button for the in-flight doc id).
- **Delete:** replace the `window.confirm` trash button with an icon trash
  button that sets `deleteTarget` (the doc) and opens `ConfirmDeleteDialog`.
  Description: `<><b>{name}</b> and all its extracted chunks, tables and images
  will be permanently removed. This can't be undone.</>`. On confirm →
  `del.mutate({ id, companyId })`, close on success.
- Retry-on-failed button stays unchanged.

## Section 4 — Frontend: company-detail wiring

**File:** `frontend/src/routes/company-detail.tsx`
- Replace the inline `AlertDialog` block with local `open` state + the shared
  `ConfirmDeleteDialog`. The existing "Delete" button becomes the trigger
  (`onClick={() => setDeleteOpen(true)}`). Description: "This permanently removes
  the company and its logo. This can't be undone." On confirm →
  `del.mutate(company.id, { onSuccess: () => navigate({ to: "/companies" }) })`.
- Drop the now-unused `AlertDialog*` imports from this file.

## Testing summary

- Backend: new `download_url` action tests (configured / unconfigured).
- Frontend: extend `frontend/src/lib/api/documents.test.ts` with a
  `getDocumentDownloadUrl` case (mock the endpoint). Shared dialog is covered
  through the components that use it.
- Run existing frontend + backend suites to confirm no regressions.

## Implementation parallelism & branch safety

All work stays on the current branch in **this** worktree. Sub-agents operate on
disjoint file sets and must NOT create/switch branches, touch `main`, or run
destructive git commands (other sessions share the repo).

- **Track A (backend):** `documents/gcs.py` re-export + `download_url` action +
  backend tests. Independent.
- **Track B (component):** `confirm-delete-dialog.tsx`. Independent.
- **Track C (frontend wiring):** documents API fn, documents-tab, company-detail,
  frontend test. Depends on Track B (imports the component) and Track A's route
  shape (already fixed in this spec).

A and B run concurrently; C follows once B lands.
