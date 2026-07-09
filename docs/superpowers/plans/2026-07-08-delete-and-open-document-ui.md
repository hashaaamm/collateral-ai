# Delete pop screen, open document, and company delete restyle — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a signed-GCS "open document in new tab" action, replace the document-delete `window.confirm` with the design's pop-screen dialog, and reuse that same dialog for company delete.

**Architecture:** Backend gains a `download-url` GET action on `DocumentViewSet` returning a signed GCS GET URL as JSON. Frontend gets one shared, controlled `ConfirmDeleteDialog` component (Radix `AlertDialog` + design pop-screen layout) used by both `documents-tab` and `company-detail`, plus an "Open in new tab" per-row action that fetches the signed URL and opens it.

**Tech Stack:** Django REST Framework + drf-spectacular (backend), React + TanStack Query + Radix UI + Tailwind + Phosphor icons + openapi-fetch/openapi-typescript (frontend), pytest (backend tests), vitest/jsdom (frontend tests).

## Global Constraints

- All work stays on the current branch `claude/delete-ui-documents-company-7ba153` in **this** worktree. Sub-agents must NOT create/switch branches, checkout, touch `main`, or run destructive git commands — other sessions share the repo.
- Backend tests run via: `cd backend && just pytest <path>` (wraps `docker compose run --rm django pytest`).
- Frontend commands run from `frontend/`: `pnpm test`, `pnpm typecheck`, `pnpm build`.
- Download endpoint returns JSON `{ "url": "<signed GET url>" }` (mirror the upload-url pattern) — no server-side redirect.
- The Open button is shown for **any uploaded document** (has `storage_path`), regardless of processing status.
- Phosphor icons are imported from `@phosphor-icons/react` (not `/ssr`).
- No new dependencies. There is no React component-test infra (no `@testing-library/react`); presentational components are verified via `pnpm typecheck` + `pnpm build`, matching the existing codebase (only `lib/**` has unit tests).

## Track / dependency map

- **Track A (Task 1)** — backend endpoint. Independent.
- **Track B (Task 2)** — `ConfirmDeleteDialog` component. Independent.
- **Track C (Tasks 3–5)** — frontend wiring. Task 3 (schema + api fn) depends on Track A's route. Tasks 4–5 depend on Track B (component) and Task 3 (api fn).

A and B run concurrently. C follows once A and B land.

---

## Task 1: Backend — signed download URL endpoint

**Files:**
- Modify: `backend/collateral_ai/documents/gcs.py`
- Modify: `backend/collateral_ai/documents/api/views.py`
- Test: `backend/collateral_ai/documents/tests/api/test_views.py`

**Interfaces:**
- Consumes: `collateral_ai.companies.gcs.signed_get_url(object_path) -> str` (exists, V4 GET, 1-hour expiry); `gcs.is_configured() -> bool`.
- Produces: route `GET /api/companies/{company_pk}/documents/{id}/download-url/` → `200 {"url": str}` when configured & doc has `storage_path`, else `503 {"detail": str}`. Scoped to company (404 for another company's doc via existing `get_queryset`).

- [ ] **Step 1: Write the failing tests**

Append to `backend/collateral_ai/documents/tests/api/test_views.py`:

```python
def test_download_url_returns_signed_url_when_configured(auth_client):
    company = CompanyFactory()
    doc = DocumentFactory(company=company, file_name="report.pdf")
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
        resp = auth_client.get(
            f"/api/companies/{company.pk}/documents/{doc.pk}/download-url/",
        )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == {"url": "https://signed-get"}


def test_download_url_503_when_not_configured(auth_client):
    company = CompanyFactory()
    doc = DocumentFactory(company=company, file_name="report.pdf")
    with mock.patch(
        "collateral_ai.documents.api.views.gcs.is_configured",
        return_value=False,
    ):
        resp = auth_client.get(
            f"/api/companies/{company.pk}/documents/{doc.pk}/download-url/",
        )
    assert resp.status_code == HTTPStatus.SERVICE_UNAVAILABLE


def test_download_url_scoped_to_company(auth_client):
    a, b = CompanyFactory(), CompanyFactory()
    doc = DocumentFactory(company=b, file_name="b.pdf")
    resp = auth_client.get(
        f"/api/companies/{a.pk}/documents/{doc.pk}/download-url/",
    )
    assert resp.status_code == HTTPStatus.NOT_FOUND
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && just pytest collateral_ai/documents/tests/api/test_views.py -k download_url`
Expected: FAIL — 404 for all (action/route does not exist yet).

- [ ] **Step 3: Re-export `signed_get_url` in documents gcs**

In `backend/collateral_ai/documents/gcs.py`, add the import alongside the existing re-exports:

```python
from collateral_ai.companies.gcs import delete_object  # noqa: F401  (re-exported)
from collateral_ai.companies.gcs import is_configured  # noqa: F401  (re-exported)
from collateral_ai.companies.gcs import signed_get_url  # noqa: F401  (re-exported)
from collateral_ai.companies.gcs import signed_upload_url  # noqa: F401  (re-exported)
```

- [ ] **Step 4: Add the `download_url` action**

In `backend/collateral_ai/documents/api/views.py`, add this method to `DocumentViewSet` (after `complete`, before `perform_destroy`):

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

(`action`, `extend_schema`, `inline_serializer`, `serializers`, `status`, `Response`, `gcs` are all already imported in this file.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && just pytest collateral_ai/documents/tests/api/test_views.py -k download_url`
Expected: PASS (3 passed).

- [ ] **Step 6: Run the full documents suite for regressions**

Run: `cd backend && just pytest collateral_ai/documents`
Expected: PASS (no regressions).

- [ ] **Step 7: Commit**

```bash
git add backend/collateral_ai/documents/gcs.py backend/collateral_ai/documents/api/views.py backend/collateral_ai/documents/tests/api/test_views.py
git commit -m "feat(documents): signed GCS download-url endpoint

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Frontend — shared `ConfirmDeleteDialog` component

**Files:**
- Create: `frontend/src/components/confirm-delete-dialog.tsx`

**Interfaces:**
- Consumes: `@/components/ui/alert-dialog` primitives (`AlertDialog`, `AlertDialogContent`, `AlertDialogHeader`, `AlertDialogMedia`, `AlertDialogTitle`, `AlertDialogDescription`, `AlertDialogFooter`, `AlertDialogCancel`, `AlertDialogAction`); `Trash` from `@phosphor-icons/react`.
- Produces: default export? No — **named export** `ConfirmDeleteDialog` with props:
  ```ts
  {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    title: string;
    description: React.ReactNode;
    confirmLabel?: string;      // default "Delete"
    loading?: boolean;
    onConfirm: () => void;
  }
  ```

- [ ] **Step 1: Create the component**

Create `frontend/src/components/confirm-delete-dialog.tsx`:

```tsx
import type { ReactNode } from "react";
import { Trash } from "@phosphor-icons/react";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogMedia,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";

export function ConfirmDeleteDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel = "Delete",
  loading = false,
  onConfirm,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: ReactNode;
  confirmLabel?: string;
  loading?: boolean;
  onConfirm: () => void;
}) {
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent size="sm">
        <AlertDialogHeader>
          <AlertDialogMedia className="bg-destructive/10 text-destructive">
            <Trash weight="bold" />
          </AlertDialogMedia>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          <AlertDialogDescription>{description}</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={loading}>Cancel</AlertDialogCancel>
          <AlertDialogAction
            variant="destructive"
            disabled={loading}
            onClick={(e) => {
              // Keep the dialog mounted while the mutation runs; the caller
              // closes it via onOpenChange on success.
              e.preventDefault();
              onConfirm();
            }}
          >
            <Trash weight="bold" />
            {confirmLabel}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
```

- [ ] **Step 2: Verify `destructive` button variant exists**

Run: `grep -n "destructive" frontend/src/components/ui/button.tsx`
Expected: a `destructive` variant is listed. If it is NOT present, use `className="bg-destructive text-white hover:bg-destructive/90"` on `AlertDialogAction` instead of `variant="destructive"` and drop the `variant` prop.

- [ ] **Step 3: Typecheck**

Run: `cd frontend && pnpm typecheck`
Expected: PASS (no type errors).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/confirm-delete-dialog.tsx
git commit -m "feat(ui): shared ConfirmDeleteDialog pop-screen component

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: Frontend — schema + `getDocumentDownloadUrl` api fn

**Depends on:** Task 1 (endpoint must exist).

**Files:**
- Modify: `frontend/src/lib/api/schema.d.ts`
- Modify: `frontend/src/lib/api/documents.ts`
- Test: `frontend/src/lib/api/documents.test.ts`

**Interfaces:**
- Produces: `getDocumentDownloadUrl(companyId: number, id: number): Promise<string>` — GETs the download-url endpoint, returns `data.url`; throws `Error("download_unavailable")` on error/missing data.

- [ ] **Step 1: Add the path to the generated schema**

> Canonical method: with the backend running, `cd frontend && pnpm gen:api` regenerates `schema.d.ts`. If a running backend isn't available in this environment, apply the deterministic manual edit below (self-consistent operation name).

In `frontend/src/lib/api/schema.d.ts`, immediately after the `"/api/companies/{company_pk}/documents/{id}/complete/"` path block (ends at the `};` on the line before `"/api/companies/{id}/":`), insert:

```ts
    "/api/companies/{company_pk}/documents/{id}/download-url/": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get: operations["companies_documents_download_url_retrieve"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
```

Then, in the `operations` interface (after `companies_documents_complete_create: { ... }`), insert:

```ts
    companies_documents_download_url_retrieve: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                company_pk: number;
                id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        url: string;
                    };
                };
            };
        };
    };
```

- [ ] **Step 2: Write the failing test**

Add to `frontend/src/lib/api/documents.test.ts` (and add `getDocumentDownloadUrl` to the import from `./documents`):

```ts
describe("getDocumentDownloadUrl", () => {
  it("GETs the download-url endpoint and returns the url", async () => {
    const get = vi.spyOn(api, "GET").mockResolvedValue({
      data: { url: "https://signed-get" },
      error: undefined,
    } as never);
    const url = await getDocumentDownloadUrl(3, 7);
    expect(get).toHaveBeenCalledWith(
      "/api/companies/{company_pk}/documents/{id}/download-url/",
      { params: { path: { company_pk: 3, id: 7 } } },
    );
    expect(url).toBe("https://signed-get");
  });

  it("throws download_unavailable on error", async () => {
    vi.spyOn(api, "GET").mockResolvedValue({
      data: undefined,
      error: { detail: "no" },
    } as never);
    await expect(getDocumentDownloadUrl(3, 7)).rejects.toThrow("download_unavailable");
  });
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd frontend && pnpm test documents`
Expected: FAIL — `getDocumentDownloadUrl is not a function` / import error.

- [ ] **Step 4: Implement the api fn**

Add to `frontend/src/lib/api/documents.ts` (after `deleteDocument`):

```ts
export async function getDocumentDownloadUrl(companyId: number, id: number): Promise<string> {
  const { data, error } = await api.GET(
    "/api/companies/{company_pk}/documents/{id}/download-url/",
    { params: { path: { company_pk: companyId, id } } },
  );
  if (error || !data) throw new Error("download_unavailable");
  return data.url;
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd frontend && pnpm test documents`
Expected: PASS.

- [ ] **Step 6: Typecheck**

Run: `cd frontend && pnpm typecheck`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/lib/api/schema.d.ts frontend/src/lib/api/documents.ts frontend/src/lib/api/documents.test.ts
git commit -m "feat(documents): getDocumentDownloadUrl api client fn + schema

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Frontend — documents-tab open + delete wiring

**Depends on:** Task 2 (`ConfirmDeleteDialog`), Task 3 (`getDocumentDownloadUrl`).

**Files:**
- Modify: `frontend/src/components/documents-tab.tsx`

**Interfaces:**
- Consumes: `ConfirmDeleteDialog` from `@/components/confirm-delete-dialog`; `getDocumentDownloadUrl` from `@/lib/api/documents`; `ArrowSquareOut`, `Trash` from `@phosphor-icons/react`.

- [ ] **Step 1: Add imports and state**

In `frontend/src/components/documents-tab.tsx`:

Update the Phosphor import to add `ArrowSquareOut`:
```tsx
import { ArrowClockwise, ArrowSquareOut, FilePdf, Trash, UploadSimple } from "@phosphor-icons/react";
```

Add imports:
```tsx
import { ConfirmDeleteDialog } from "@/components/confirm-delete-dialog";
import {
  getDocumentDownloadUrl,
  useCompleteDocument,
  useDeleteDocument,
  useDocuments,
  uploadDocument,
  type Document,
} from "@/lib/api/documents";
```
(add `getDocumentDownloadUrl` to the existing `@/lib/api/documents` import; do not duplicate the import statement.)

Inside `DocumentsTab`, after the existing `useState` hooks, add:
```tsx
  const [deleteTarget, setDeleteTarget] = useState<Document | null>(null);
  const [openingId, setOpeningId] = useState<number | null>(null);

  async function onOpen(d: Document) {
    setError("");
    setOpeningId(d.id);
    // Open the tab synchronously so the browser doesn't block it, then point
    // it at the signed URL once it resolves.
    const w = window.open("", "_blank", "noopener,noreferrer");
    try {
      const url = await getDocumentDownloadUrl(companyId, d.id);
      if (w) w.location.href = url;
    } catch {
      w?.close();
      setError("Couldn't open the document. Try again.");
    } finally {
      setOpeningId(null);
    }
  }
```

- [ ] **Step 2: Add the Open button and replace the delete button**

In the row actions `<div className="flex items-center justify-end gap-2">`, replace the existing delete `<button>` (the one calling `window.confirm`) and add the Open button before it, so the block reads:

```tsx
                    <div className="flex items-center justify-end gap-2">
                      <StatusPill status={d.status} />
                      {d.status === "failed" && (
                        <button
                          type="button"
                          onClick={() => retry.mutate({ id: d.id, companyId })}
                          className="flex items-center gap-1 text-[12px] text-brand hover:underline"
                        >
                          <ArrowClockwise size={13} /> Retry
                        </button>
                      )}
                      <button
                        type="button"
                        disabled={openingId === d.id}
                        onClick={() => onOpen(d)}
                        className="flex items-center gap-1 text-[12px] text-mute hover:text-brand disabled:opacity-50"
                        aria-label={`Open ${d.file_name} in a new tab`}
                        title="Open in new tab"
                      >
                        <ArrowSquareOut size={15} />
                      </button>
                      <button
                        type="button"
                        onClick={() => setDeleteTarget(d)}
                        className="flex items-center gap-1 text-[12px] text-mute hover:text-destructive"
                        aria-label={`Delete ${d.file_name}`}
                        title="Delete"
                      >
                        <Trash size={14} />
                      </button>
                    </div>
```

- [ ] **Step 3: Render the dialog**

Immediately before the final closing `</div>` of the component's returned tree, add:

```tsx
      <ConfirmDeleteDialog
        open={deleteTarget !== null}
        onOpenChange={(o) => {
          if (!o) setDeleteTarget(null);
        }}
        title="Delete document?"
        description={
          deleteTarget ? (
            <>
              <b className="font-semibold text-body">{deleteTarget.file_name}</b> and all its
              extracted chunks, tables and images will be permanently removed. This can&apos;t be
              undone.
            </>
          ) : null
        }
        loading={del.isPending}
        onConfirm={() => {
          if (deleteTarget) {
            del.mutate(
              { id: deleteTarget.id, companyId },
              { onSuccess: () => setDeleteTarget(null) },
            );
          }
        }}
      />
```

- [ ] **Step 4: Typecheck, lint, build**

Run: `cd frontend && pnpm typecheck && pnpm lint && pnpm build`
Expected: PASS (no type/lint/build errors). Confirm no unused-import warning for the removed `window.confirm` path.

- [ ] **Step 5: Run frontend tests for regressions**

Run: `cd frontend && pnpm test`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/documents-tab.tsx
git commit -m "feat(documents): open-in-new-tab action + pop-screen delete dialog

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: Frontend — company-detail delete uses shared dialog

**Depends on:** Task 2 (`ConfirmDeleteDialog`).

**Files:**
- Modify: `frontend/src/routes/company-detail.tsx`

- [ ] **Step 1: Swap imports**

In `frontend/src/routes/company-detail.tsx`, remove the whole `AlertDialog*` import block (the `import { AlertDialog, AlertDialogAction, ... AlertDialogTrigger } from "@/components/ui/alert-dialog";`) and add:

```tsx
import { ConfirmDeleteDialog } from "@/components/confirm-delete-dialog";
```

Keep `Trash` in the existing `@phosphor-icons/react` import (still used by the trigger button).

- [ ] **Step 2: Add local open state**

In `CompanyDetailPage`, alongside the existing `const [tab, setTab] = useState<Tab>("Overview");`, add:

```tsx
  const [deleteOpen, setDeleteOpen] = useState(false);
```

- [ ] **Step 3: Replace the AlertDialog block**

Replace the entire `<AlertDialog> ... </AlertDialog>` element (the delete control in the header actions) with a plain trigger button plus the shared dialog:

```tsx
          <button
            type="button"
            onClick={() => setDeleteOpen(true)}
            className="flex items-center gap-[7px] rounded-[10px] border border-field bg-surface px-[14px] py-[9px] text-[13px] font-semibold text-destructive hover:bg-subtle"
          >
            <Trash size={15} />
            Delete
          </button>
```

Then, immediately before the outermost closing `</div>` of the returned tree, add:

```tsx
      <ConfirmDeleteDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        title={`Delete ${company.name}?`}
        description={
          <>
            This permanently removes the company and its logo. This can&apos;t be undone.
          </>
        }
        loading={del.isPending}
        onConfirm={() =>
          del.mutate(company.id, {
            onSuccess: () => {
              setDeleteOpen(false);
              navigate({ to: "/companies" });
            },
          })
        }
      />
```

- [ ] **Step 4: Typecheck, lint, build**

Run: `cd frontend && pnpm typecheck && pnpm lint && pnpm build`
Expected: PASS, with no unused-import errors (all `AlertDialog*` references removed).

- [ ] **Step 5: Run frontend tests**

Run: `cd frontend && pnpm test`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/routes/company-detail.tsx
git commit -m "feat(companies): reuse shared ConfirmDeleteDialog for delete

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Final verification (after all tasks)

- [ ] `cd backend && just pytest collateral_ai/documents` → PASS
- [ ] `cd frontend && pnpm typecheck && pnpm lint && pnpm test && pnpm build` → all PASS
- [ ] Manual smoke (optional, needs stack up via `just` / docker): open a company → Documents tab → Open button opens the PDF in a new tab; Delete shows the pop screen and removes the row; company Delete shows the same pop screen and navigates back to the list.
