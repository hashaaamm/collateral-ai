# Global Upload Notification Tray (bottom-right)

**Date:** 2026-07-13
**Status:** Approved — ready for implementation plan
**Builds on:** `2026-07-13-parallel-pdf-upload-design.md` (concurrent uploads already shipped)

## Problem

Concurrent PDF upload progress currently renders **inline inside `DocumentsTab`**
(`frontend/src/components/documents-tab.tsx`), which the user disliked: it clutters the
tab's own screen, disappears if you navigate away, and completed documents don't appear in
the list promptly. Two concrete issues:

1. **Placement:** progress should live in a floating **bottom-right notification tray**
   (like the GCP Cloud Console activity tray) — a small, scrollable, collapsible panel that
   persists across navigation — not inline in the documents table.
2. **"Doesn't appear instantly":** the documents list is refetched only **once, after the
   whole batch settles** (`invalidateQueries` runs after `Promise.allSettled`). Dropping N
   files where one is slow delays all the others' rows from appearing.

## Goal

Move upload progress into a **global, persistent, bottom-right tray**, and refetch the
documents list **per file as each completes** so rows appear promptly.

## Non-Goals

- Not a general activity/notification tray — **uploads only**. Can be generalized later.
- No upload retry (out of scope, as before).
- No backend changes. `uploadDocument` (`src/lib/api/documents.ts`) and `putWithProgress`
  (`src/lib/api/upload.ts`) are unchanged; uploads still go direct-to-GCS via signed URLs,
  and progress still comes from `xhr.upload.onprogress` (bytes sent to GCS ÷ total).
- No per-file company label in the tray — filename + progress only.

## Design

### 1. Global uploads store — `UploadsProvider` + `useUploads()`

New file `frontend/src/components/uploads/uploads-context.tsx`. Mounted **inside**
`QueryClientProvider` in `frontend/src/components/providers.tsx` (it needs the query client),
wrapping `children`. Owns all upload orchestration that previously lived in `DocumentsTab`.

State:

```ts
type UploadStatus = "uploading" | "processing" | "done" | "error";

type UploadItem = {
  id: string;        // crypto.randomUUID()
  name: string;      // file.name
  companyId: number; // for per-file query invalidation
  status: UploadStatus;
  progress: number;  // 0–100
  error?: string;
};
```

Held as `useState<UploadItem[]>([])`, plus a `useRef` for the auto-dismiss timer.

Context value:

- `items: UploadItem[]`
- `enqueue(files: FileList | File[], companyId: number): void`
- `dismiss(): void`

Behavior:

- **`enqueue`**: cancel any pending auto-dismiss timer. Build one `UploadItem` per selected
  file — valid PDFs (`file.type === "application/pdf"`) start `status: "uploading",
  progress: 0`; non-PDFs are added as `status: "error", error: "Only PDF files are
  supported."` and never uploaded. **Append** these to `items` (GCP-style; a new selection
  while the tray is up adds to it, does not replace). Then fire the runnable ones via
  `Promise.allSettled(runnable.map(runOne))`.
- **`runOne(item, file)`**: call `uploadDocument({ companyId: item.companyId, file,
  onProgress })`; `onProgress` patches that item's `progress` by `id` (and flips to
  `"processing"` at 100%). On success: patch `status: "done", progress: 100` **and
  immediately `qc.invalidateQueries({ queryKey: ["documents", item.companyId] })`** — this is
  the per-file refetch that fixes "doesn't appear instantly." On throw: patch
  `status: "error"` with the mapped message (`upload_not_configured` → "Document upload isn't
  configured in this environment.", else "Upload failed. Try again.").
- **Auto-dismiss**: after a batch settles, if **every** item is settled
  (`status ∈ {done, error}`) **and none** is `error`, start a ~5s timer that calls
  `dismiss()`. If **any** item is `error`, do **not** auto-dismiss — the tray stays until the
  user closes it. A new `enqueue` cancels a pending timer.
- **`dismiss`**: clear the timer and set `items` to `[]` (tray unmounts its content).

Patch helper: `setItems(prev => prev.map(u => u.id === id ? { ...u, ...patch } : u))`.

### 2. Tray UI — `<UploadTray />`

New file `frontend/src/components/uploads/upload-tray.tsx`. Rendered once, next to
`<Toaster>` inside `UploadsProvider`. Reads `useUploads()`. Renders **nothing when
`items.length === 0`**.

- **Container:** `fixed bottom-4 right-4 z-[60] w-[360px] max-w-[calc(100vw-2rem)]`
  rounded card with border + shadow, matching existing surface/hairline tokens. A defined
  `z-index` keeps ordering stable relative to Sonner toasts (which are transient and stack
  above).
- **Header (always visible):** a summary label derived from `items` —
  `Uploading N of M` while any are in-flight, else `Uploads complete`, else
  `N failed` when there are failures. A **chevron** toggles collapse (local `useState` in the
  tray). A **close (×)** button calls `dismiss()`.
- **Body (when expanded):** scrollable list `max-h-[280px] overflow-y-auto`. One row per
  item: `FilePdf` icon + **truncated** filename (`truncate`) + a progress bar
  (`bg-brand` on `bg-hairline-soft`, as today) while uploading/processing, or a status label
  (`done` / `failed — <error>`). During upload the row shows filename + bar only (no extra
  metadata), per the requirement.

### 3. `DocumentsTab` slims down

`frontend/src/components/documents-tab.tsx`:

- Remove the local upload state (`uploads`/`UploadItem`/`runOne`/`patchUpload`) and the
  inline `<ul>` of upload rows added in the previous change.
- Keep the dashed dropzone button + hidden `<input type="file" accept="application/pdf"
  multiple>`. Its `onChange` now calls `useUploads().enqueue(e.target.files, companyId)`.
- Keep everything else unchanged: `openError` state and the Open-in-new-tab flow, the
  documents table, retry-processing button, and delete dialog.

## Testing

- **`uploads-context.test.tsx`** (new): with a mocked `uploadDocument`, `enqueue` of 3 PDFs
  fires all three before any resolve (concurrency); `onProgress` updates only the matching
  item; each file's success triggers `invalidateQueries(["documents", companyId])`
  individually (assert called per file, not once at the end); using fake timers, a
  fully-successful batch clears `items` after the delay, while a batch containing an error
  does **not** auto-dismiss; a non-PDF becomes an error item and never calls `uploadDocument`.
- **`upload-tray.test.tsx`** (new): renders one row per context item; header summary text
  reflects in-flight / complete / failed; chevron toggles the list; close button calls
  `dismiss`; renders nothing when `items` is empty.
- **`documents-tab.test.tsx`** (rewrite): selecting files calls `enqueue(files, companyId)`;
  the inline upload rows are gone. Orchestration assertions move to the context test. Wrap
  the component in both `QueryClientProvider` and a (real or mocked) `UploadsProvider`.

## Files Touched

- `frontend/src/components/uploads/uploads-context.tsx` — new (store + hook).
- `frontend/src/components/uploads/upload-tray.tsx` — new (tray UI).
- `frontend/src/components/providers.tsx` — mount `UploadsProvider` + render `<UploadTray/>`.
- `frontend/src/components/documents-tab.tsx` — remove inline upload UI, call `enqueue`.
- `frontend/src/components/uploads/uploads-context.test.tsx` — new.
- `frontend/src/components/uploads/upload-tray.test.tsx` — new.
- `frontend/src/components/documents-tab.test.tsx` — rewrite.
