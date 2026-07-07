# Design Spec: Document Ingestion (Company Knowledge Base)

**Date:** 2026-07-07
**Branch:** `worktree-documents-ingestion` (isolated worktree, based on `origin/main`)
**Status:** Approved design — ready for implementation planning

## Overview

Add a per-company document knowledge base to Collateral AI. A user uploads PDFs on a
company's **Documents tab**; each PDF is stored in GCS, then processed by a worker that
extracts text/tables/images, chunks the content, embeds it with Gemini (via Vertex AI),
and stores the chunks in Postgres + pgvector. The stored chunks become the grounding
source for the later marketing-material generation feature (out of scope here).

This is delivered in two phases — an upload surface (no AI) then the processing worker — so
the branch stays mergeable and Phase 1 ships on its own.

### Goals
- Company-scoped document upload with a real progress bar (bytes go straight to GCS).
- Visible processing lifecycle (`pending → processing → processed | failed`) with retry.
- A worker that turns a PDF into embedded, retrievable `DocumentChunk`s.
- Keeps the existing companies/logo patterns and the Pulumi-owned infra model.

### In scope (added)
- **Document delete** — API + UI. Removes the `Document` row (chunks/vectors cascade),
  the stored PDF, and (Phase 2) any extracted images from GCS. See "Document deletion" below.

### Non-goals (deferred — YAGNI)
- Document rename.
- AI company summary / profile auto-fill (Overview tab content).
- The retrieval endpoint and generation pipeline (chunks are stored *ready* for it).
- Non-PDF file types.

## Context / Existing Patterns to Mirror

- **Backend:** Django + DRF (cookiecutter-django). The `collateral_ai.companies` app is the
  template: `models.py`, `api/views.py` (`GenericViewSet` + mixins + `@action`), `api/serializers.py`,
  `gcs.py` (dual prod/emulator V4 signed URLs), registered in `config/api_router.py`.
- **Storage:** GCS bucket (`GS_BUCKET_NAME`). Signed **PUT** upload + signed **GET** display already
  solved keylessly (IAM SignBlob in prod, throwaway key against the emulator locally).
- **DB:** Cloud SQL **Postgres** (private IP); local Postgres via docker-compose.
- **Infra:** Pulumi owns all GCP infra (`deploy/__main__.py`); GitHub Actions owns deploys.
  Runtime service account `cloud-run-sa` has `cloudsql.client`, `secretmanager.secretAccessor`,
  `storage.objectAdmin`, and `iam.serviceAccountTokenCreator` (self).
- **Frontend:** React + Vite, TanStack Router/Query, openapi-typescript `schema.d.ts`,
  `lib/api/companies.ts` hooks + `requestUploadAndPut` (POST signed URL → PUT to GCS).
- **Design source of truth:** `mvp-frontend-architecture/` handoff. Documents live in
  **Company Detail → Documents tab**: a dashed PDF dropzone + a table
  (`File name · Type · Pages · Chunks · Tables · Images · Status`) with `Processed / Processing / Failed`
  status pills. Design tokens (colors/typography/spacing) are defined in that handoff.

## Architecture Decisions (locked)

| Decision | Choice | Rationale |
|---|---|---|
| Document scoping | **Company-scoped** (FK to Company) | Matches design + per-company retrieval model. |
| Worker execution (prod) | **Cloud Run Job** triggered via Cloud Run Admin API | Clean fit for a batch management command; no long work in a web request. |
| Worker execution (local/CI) | **Inline** `call_command` | Devs/tests see real processing with no extra infra. |
| Gemini auth | **Vertex AI** (`google-genai` Vertex mode, ADC, keyless) | No API key to manage; matches the project's keyless GCP posture. |
| Extraction scope | **Text + tables + images** | Full pipeline per product owner; populates every design column. |
| Embeddings | `gemini-embedding-001`, **768-dim**, normalized, `RETRIEVAL_DOCUMENT` | MVP cost/perf; task type per Google docs. |

## Data Model — `collateral_ai.documents` app

### `Document`
| field | type | notes |
|---|---|---|
| id | BigAuto | |
| company | FK → `companies.Company`, `on_delete=CASCADE`, `related_name="documents"` | |
| file_name | CharField(255) | original filename |
| storage_path | CharField(512) | GCS object path |
| content_type | CharField(100) | `application/pdf` only for MVP |
| status | CharField(32) | see `DocumentStatus` |
| page_count | PositiveIntegerField(null=True) | |
| chunks_count | PositiveIntegerField(default=0) | |
| tables_count | PositiveIntegerField(default=0) | design "Tables" column |
| images_count | PositiveIntegerField(default=0) | design "Images" column |
| error_message | TextField(blank=True) | set on `failed` |
| created_at | DateTimeField(auto_now_add=True) | |
| updated_at | DateTimeField(auto_now=True) | |

`class Meta: ordering = ["-created_at"]`.

**`DocumentStatus`** (constants class in `documents/statuses.py`):
`PENDING = "pending"`, `PROCESSING = "processing"`, `PROCESSED = "processed"`, `FAILED = "failed"`.
Lifecycle: `pending` (row created, awaiting upload+complete) → `processing` (complete called) →
`processed` | `failed`. Re-calling `complete` on a `failed` doc restarts it (retry).

> Status→pill mapping for the UI: `processing → Processing`, `processed → Processed`,
> `failed → Failed`. `pending` is transient (between create and complete) and surfaces as
> "Processing" if ever shown.

### `DocumentChunk`
| field | type | notes |
|---|---|---|
| id | BigAuto | |
| document | FK → `Document`, `on_delete=CASCADE`, `related_name="chunks"` | |
| company | FK → `companies.Company` | denormalized for company-scoped retrieval |
| chunk_type | CharField(32) | `text` \| `table` \| `image_caption` |
| page_number | PositiveIntegerField | |
| content | TextField | |
| embedding | `pgvector.django.VectorField(dimensions=768)` | |
| metadata | JSONField(default=dict) | provenance: source, chunk_index, word range, embedding model/dims/version, image storage path |
| created_at | DateTimeField(auto_now_add=True) | |

> **Additions beyond the original field list (approved):** `tables_count`/`images_count` on
> `Document` (full pipeline + design columns) and `metadata` on `DocumentChunk` (retrieval
> provenance; the future `generation_sources` records lean on chunk/page provenance).
> `updated_at` added to `Document` for lifecycle tracking.

**pgvector enablement:** a Django migration runs `CREATE EXTENSION IF NOT EXISTS vector`
(supported on Cloud SQL PG15/16 and standard Postgres). The `DocumentChunk` migration depends
on it.

## API — DRF (`documents/api/`)

`DocumentViewSet` registered on the router as `documents` (basename `document`), mirroring
`CompanyViewSet`. Mixins: `List`, `Retrieve`, `Create`. `IsAuthenticated` (project default).

| Method / path | Purpose |
|---|---|
| `GET /api/documents/?company={id}` | List a company's documents, newest first. `company` filter required in practice (list is company-scoped in the UI). |
| `POST /api/documents/` | Body `{company, file_name, content_type}`. Validates `content_type == application/pdf`. Creates `Document(status="pending")`, builds a GCS object path, returns the serialized document **plus `upload_url`** (signed PUT, 15-min expiry). Returns **503** if GCS is not configured (mirrors logo upload). |
| `GET /api/documents/{id}/` | Retrieve one document (used by polling if needed). |
| `POST /api/documents/{id}/complete/` | Marks `processing`, triggers the worker, returns **202** + document. Idempotent-ish: re-callable on `failed` (retry) and no-op-safe on already-terminal states. |
| `DELETE /api/documents/{id}/` | Deletes the document. `perform_destroy` removes the stored PDF (and, Phase 2, extracted images) from GCS via best-effort `gcs.delete_object`, then deletes the row — `DocumentChunk` rows (and their embeddings/vectors) go with it via `on_delete=CASCADE`. Returns **204**. |

**Upload flow (two calls, mirrors logo pattern):**
1. `POST /api/documents/` → `{ ...document, upload_url }` (row reserved as `pending`).
2. Client `PUT`s bytes to `upload_url` (GCS) with an XHR progress bar.
3. `POST /api/documents/{id}/complete/` → `202`, worker triggered.

Orphans (created but never completed, e.g. PUT failed) simply remain `pending`; cleanup is a
future concern, not MVP.

**Object path:** `media/companies/{company_id}/documents/{document_id}/{sanitized_name}.pdf`
(reuses the sanitize/prefix approach from `companies/gcs.py`).

**GCS helpers:** a `documents/gcs.py` (or shared extension of the existing module) provides:
- `build_document_object_path(company_id, document_id, filename)`
- `signed_upload_url(object_path, content_type)` — reuse existing signer
- `download_bytes(object_path)` / `upload_bytes(object_path, content, content_type)` — direct
  GCS access via ADC for the worker (runtime SA already has `storage.objectAdmin`).
- `delete_object(object_path)` — best-effort delete, never raises (mirrors the companies pattern).

### Document deletion

`DocumentViewSet` includes `DestroyModelMixin`. `perform_destroy(instance)`:
1. If GCS is configured, `gcs.delete_object(instance.storage_path)` (the PDF). In Phase 2, also
   delete any extracted-image objects recorded on the chunks' metadata (or under the document's
   `.../images/` prefix).
2. `instance.delete()` — `DocumentChunk` rows and their pgvector embeddings cascade away.

GCS cleanup is best-effort (never blocks the delete); an orphaned object is harmless and cheap.
Frontend: a per-row **delete** action with a confirm step; on success invalidate the documents
query so the row disappears.

## Worker — `process_document` management command

`python manage.py process_document --document-id <id> [--force]`

Refactored from the reference into focused, independently-testable services under
`documents/processing/`:

- **`storage.py`** — download the PDF, upload extracted images.
- **`extraction.py`** — PyMuPDF: page count, per-page text blocks, images (uploaded to GCS with
  captions). pdfplumber: tables → markdown. Returns an `ExtractionResult` DTO.
- **`chunking.py`** — deterministic word-overlap chunking (`max_words=300`, `overlap=50`),
  version-tagged (`v1`). No LLM.
- **`embeddings.py`** — `EmbeddingService` using `google-genai` in **Vertex AI mode** (ADC):
  `gemini-embedding-001`, 768-dim, `RETRIEVAL_DOCUMENT`, L2-normalized, batched
  (`EMBEDDING_BATCH_SIZE`). Exposes `embed_documents()` now and `embed_query()` (`RETRIEVAL_QUERY`)
  for the future retrieval feature.
- **`pipeline.py`** — `DocumentProcessingService.process(document_id, force)`:
  1. `select_for_update` the row; guard status; set `processing` (clear `error_message`).
  2. Download → extract → build chunk payloads (text + table + image_caption).
  3. Embed all chunk contents; assert count parity.
  4. In a transaction: delete existing chunks for the doc, `bulk_create` new ones.
  5. Update `page_count`/`chunks_count`/`tables_count`/`images_count`, set `processed`.
  6. On any exception: set `failed` + `error_message`, re-raise.

Settings (in `config/settings/base.py`, env-overridable):
`EMBEDDING_MODEL`, `EMBEDDING_DIMENSIONS=768`, `EMBEDDING_BATCH_SIZE=64`,
`DOCUMENT_CHUNK_MAX_WORDS=300`, `DOCUMENT_CHUNK_OVERLAP_WORDS=50`,
`DOCUMENT_CHUNKING_VERSION="v1"`, plus Vertex config (`GOOGLE_CLOUD_PROJECT`, `VERTEX_LOCATION`).

> **Do not** mix embedding models/dimensions in the same vector column — changing the model
> later requires re-embedding all chunks. The chunk `metadata` records model+dims+version so a
> future migration is safe.

## Worker Execution Wiring

`complete` decides how to run based on a `DOCUMENT_PROCESSOR_JOB` setting:

- **Set (prod):** call the **Cloud Run Admin API** (`google-cloud-run`) to execute the named Job
  with a container arg **override** `--document-id <id>`. Return `202` immediately.
- **Unset (local/CI):** run `call_command("process_document", document_id=id)` **inline**
  (synchronous). Dev/test see the full pipeline (embeddings can be stubbed/mocked in unit tests).

A thin `documents/worker_trigger.py` encapsulates this branch so the view stays clean and the
selection is unit-testable.

## Infrastructure (Pulumi — `deploy/__main__.py`)

Per the project's **infra-via-Pulumi** rule (no direct gcloud/console):

- Enable the **`aiplatform`** API.
- Grant runtime SA **`roles/aiplatform.user`** (Vertex embeddings).
- Grant runtime SA **`roles/run.developer`** and allow it to `actAs` itself, so the web service
  can execute the Job.
- Add a **`gcp.cloudrunv2.Job`** running the backend image with command
  `python manage.py process_document`, wired with the same secrets/env (DATABASE_URL,
  GS_BUCKET_NAME, Vertex config), VPC connector, and Cloud SQL access as the web service.
- Export the Job name for the backend's `DOCUMENT_PROCESSOR_JOB` setting.

**pgvector local:** switch the local Postgres image (`compose/production/postgres/Dockerfile`,
currently `postgres:16`) to a pgvector-enabled base (e.g. `pgvector/pgvector:pg16`) so
`CREATE EXTENSION vector` and migrations run locally.

**CI (`cd.yml`):** in addition to updating the web service image on deploy, update the Cloud Run
**Job** image to the same tag so the worker code ships with each deploy.

**Backend deps (`pyproject.toml`):** `pymupdf`, `pdfplumber`, `google-genai`, `pgvector`,
`google-cloud-storage` (if not already transitively present), `google-cloud-run`.

## Frontend — Company Detail → Documents tab

- Add the underline **tab bar** (Overview / Documents / Generated Materials) to
  `routes/company-detail.tsx`. The **Documents** tab is the deliverable; Overview keeps the
  current profile view, Generated Materials is a light placeholder.
  **Coordination:** the CRUD session may also edit this file — keep changes additive
  (introduce the tab shell, move existing content into the Overview tab).
- **Dropzone** (dashed, "Drop PDFs here or **browse** · PDF only · max 50 MB"). For each accepted
  file: `POST /documents/` → `PUT` to GCS via **XHR with progress events** → `POST /complete/`.
  Per-file progress + status shown inline while uploading.
- **Documents table** matching the design columns: File name (+ "Uploaded … · relative time")
  · Type · Pages · Chunks · Tables · Images · **StatusPill**. `—` (muted) for null numeric cells.
  **Failed** rows expose a **Retry** action (re-calls `complete`) and can surface `error_message`.
  Every row exposes a **Delete** action (confirm → `DELETE /api/documents/{id}/` → invalidate list).
- **Polling:** while any listed doc is `processing`, TanStack Query `refetchInterval` (~3 s)
  refreshes the list until all settle, then stops.
- **API layer:** new `lib/api/documents.ts` hooks (`useDocuments(companyId)`, `useCreateDocument`
  + `requestDocumentUploadAndPut`, `useCompleteDocument`) mirroring `companies.ts`. Regenerate
  `schema.d.ts` from the updated OpenAPI schema.
- Reusable `StatusPill` component per the design token spec (icon + `text-*`/`bg-*-soft` pair).

## Phasing (implementation sequence)

Two phases, matching the product framing ("complete returns okay for now" → then wire the worker).

1. **Phase 1 — Upload surface (no AI). Shippable on its own.**
   `documents` app + `Document` model/migration + `DocumentViewSet`
   (list, create+upload-url, `complete` **stub** returns `202`, **delete** with GCS PDF cleanup).
   Frontend: Documents tab, dropzone, table, XHR progress bar, polling, `StatusPill`, row
   **delete** (confirm), `documents.ts` hooks, schema regen.
   End state: a user can upload PDFs to a company, see them listed, and delete them; nothing is
   processed yet.
2. **Phase 2 — Processing (worker + AI + infra).**
   `process_document` command + `DocumentStatus` transitions; `DocumentChunk` model +
   **pgvector extension migration** + **local pgvector image swap**
   (`postgres:16` → `pgvector/pgvector:pg16` in `compose/production/postgres/Dockerfile`);
   extraction (text+tables+images) → chunking → Vertex embeddings → chunk persistence + count/status
   updates; `complete` wired to Cloud Run Job (prod) / inline (local); Pulumi Job + IAM +
   `aiplatform` API.

## Testing Strategy

- **Models/API:** factory-based tests (mirror `companies/tests/`): create+upload-url returns a
  signed URL and a `pending` doc; `complete` transitions status and triggers the (mocked) worker;
  list is company-scoped; PDF-only validation; 503 when GCS unconfigured;
  **delete** returns 204, removes the row, and calls `gcs.delete_object` (mocked) with the PDF path.
- **Worker services:** unit-test chunking (deterministic), extraction (small fixture PDF),
  embedding service with a **mocked** Vertex client (assert model/dims/task_type/normalization),
  and `pipeline` end-to-end with mocked storage+embeddings against a fixture PDF (asserts chunk
  rows, counts, and `processed` status; failure path sets `failed` + `error_message`).
- **Worker trigger:** unit-test the prod-vs-local branch selection via the
  `DOCUMENT_PROCESSOR_JOB` setting.
- **Frontend:** hook tests mirroring `companies.test.ts` (create→PUT→complete happy path,
  progress callback, retry on failed), with the network layer mocked.

## Open Coordination Notes
- `routes/company-detail.tsx` is shared with the company-CRUD session — additive tab-shell change only.
- `config/api_router.py`, `config/settings/base.py`, and `schema.d.ts` will also be touched by
  both sessions; expect a small merge at integration time.
