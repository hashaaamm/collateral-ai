# Parallel PDF Uploads with Per-File Progress

**Date:** 2026-07-13
**Status:** Approved — ready for implementation plan

## Problem

Document (PDF) upload in `frontend/src/components/documents-tab.tsx` uploads files
**sequentially**: `onFiles` loops over the selected `FileList` with `await` inside a
`for...of`, so file N+1 does not start until file N finishes all three of its steps.
Progress is a single shared `progress: number | null` value reset to 0 before each file,
so a multi-file selection only ever shows the currently-uploading file's bar.

Users uploading several PDFs wait far longer than necessary and get no per-file feedback.

## Goal

Upload all selected PDFs **concurrently** and show an **independent progress row per file**.

## Non-Goals

- No backend changes. The backend already issues single-file signed URLs and a per-file
  `/complete` endpoint — exactly what concurrent uploads need.
- No changes to the logo upload flow (`company-form.tsx`) — it is single-file.
- No retry-on-failure UI. Failed files display a failed status and stop there.
- No artificial concurrency limit / upload pool (see Concurrency below).

## Current Architecture (unchanged pieces)

Each file is a 3-step, direct-to-GCS flow; the file never passes through the backend:

1. `POST /api/companies/{company_pk}/documents/` with `{file_name, content_type}`
   → `{ id, upload_url }` (503 → `upload_not_configured`).
2. `putWithProgress(upload_url, file, onProgress)` — `XMLHttpRequest` PUT directly to GCS,
   reporting 0–100 via `xhr.upload.onprogress` (`frontend/src/lib/api/upload.ts`).
3. `POST /api/companies/{company_pk}/documents/{id}/complete/` — kicks off backend
   processing, returns 202.

All three are wrapped by `uploadDocument({ companyId, file, onProgress })` in
`frontend/src/lib/api/documents.ts`. **`uploadDocument`, `putWithProgress`, and all backend
endpoints stay exactly as they are.** The change is confined to how `documents-tab.tsx`
orchestrates and renders multiple `uploadDocument` calls.

## Design

### Concurrency

All valid PDFs start at once via `Promise.allSettled(items.map(runOne))`. No explicit pool
or limit: every signed-URL request targets the same backend host and every PUT targets the
same GCS host, so the browser's per-host connection cap (~6) naturally throttles the batch.
This gives maximum speed with no risk of an unbounded connection storm.

### State model

Replace the current single `progress` / `error` `useState` in `documents-tab.tsx` with a
list of upload items:

```ts
type UploadStatus = "uploading" | "processing" | "done" | "error";

type UploadItem = {
  id: string;        // crypto.randomUUID() — stable React key + update key
  name: string;      // file.name
  status: UploadStatus;
  progress: number;  // 0–100, drives the bar (meaningful while status === "uploading")
  error?: string;    // message shown when status === "error"
};
```

Held as `useState<UploadItem[]>([])`. Updates are **keyed by `id`** so each row updates
independently without disturbing the others.

### Orchestration (`onFiles`)

1. On new selection, validate each file (`file.type === "application/pdf"`, as today).
   Non-PDF files are reported as an error row (or a single top-level error message) and not
   uploaded.
2. Build one `UploadItem` per valid file with `status: "uploading"`, `progress: 0`, and set
   this as the new items list (replacing any prior batch — rows persist only until the next
   selection).
3. `Promise.allSettled(items.map(runOne))` where `runOne(item)`:
   - calls `uploadDocument({ companyId, file, onProgress })`, and `onProgress` patches that
     item's `progress` by `id`.
   - when the PUT completes and the `/complete` call begins, patch `status: "processing"`;
     on overall success patch `status: "done"`.
   - on throw, patch `status: "error"` with the extracted message (reuse existing error
     mapping, e.g. `upload_not_configured`).
4. After all settle: `qc.invalidateQueries({ queryKey: ["documents", companyId] })`.

Note: step 3's `processing`→`done` transition is a UI signal for "bytes uploaded, backend
notified." The existing `useDocuments` 3s polling for server-side `processing` docs is
untouched and continues to reflect true backend processing state in the documents list.

### UI

The single progress bar (`documents-tab.tsx:102-106`) becomes a list rendered from
`UploadItem[]`. Each row shows:

- filename (`name`)
- a progress bar bound to `progress`
- a status label: `uploading NN%` / `processing` / `done` / `failed — <error>`

The dashed "Drop PDFs here or browse" trigger and hidden `<input multiple>` are unchanged.
Rows remain visible until the user selects a new batch (which replaces the list).

## Testing

- **Unit / component:** with a mocked `uploadDocument`, selecting 3 files creates 3 rows all
  in `uploading`; resolving them in a non-sequential order updates the correct rows by `id`;
  a rejecting file lands in `error` while the others reach `done`; `invalidateQueries` fires
  once after all settle.
- **Progress:** a mocked `onProgress` sequence updates only the targeted row's `progress`.
- **Manual:** select multiple PDFs against the real dev backend and confirm bars advance
  concurrently rather than one-at-a-time, and the documents list refreshes when done.

## Files Touched

- `frontend/src/components/documents-tab.tsx` — state model, `onFiles` orchestration, row UI.
- (No other files expected to change.)
