# Diagram Context — CollateralAI

Reference material for six diagrams, compiled from the codebase at commit `f33bc97` (2026-07-14).
Each section lists the boxes (components), the arrows (interactions), and the labels (technology names)
you need to draw it.

---

## 1. High-Level System Architecture

### Architecture style

- **Monorepo** with three deployable units: `frontend/` (React SPA), `backend/` (Django + DRF), `deploy/` (Pulumi Python IaC).
- **Synchronous REST API + asynchronous batch workers.** The Django service handles all interactive HTTP traffic; two long-running jobs (document ingestion, material generation) run out-of-band as **one-off Kubernetes Jobs on GKE Autopilot**, created on demand by the backend. No Celery/Redis queue — Redis is only a Django cache.
- **RAG pipeline** at the core: upload → embed → store vectors → retrieve → LLM-generate → validate/repair, orchestrated with **LangGraph**, traced in **LangSmith**.
- **Split control planes**: Pulumi owns infrastructure; GitHub Actions owns deploys.

### Runtime components

| Component | Technology | Hosted on |
|---|---|---|
| Frontend | React 19 SPA, Vite 6, TanStack Router + Query, Tailwind CSS 4, typed `openapi-fetch` client, pnpm 10 / Node 24 | GCS website bucket + Cloud CDN + global HTTPS LB |
| Backend API | Django 6.0 + DRF 3.17, drf-spectacular (OpenAPI), django-allauth (+MFA), Python 3.13, gunicorn :8080 | Cloud Run service `collateral-ai-backend` (1 CPU / 512Mi / max 4 instances / min 0) |
| DB + vector store | Cloud SQL PostgreSQL 15, **pgvector** (`vector(768)` on `DocumentChunk.embedding`), private IP only | Cloud SQL instance `collateral-ai-sql` |
| Object storage | GCS: static/media bucket (PDFs, logos, extracted images) + separate frontend site bucket | Cloud Storage |
| Async workers | Kubernetes Jobs created by the backend via the `kubernetes` Python client; same Docker image as the backend | GKE Autopilot cluster `collateral-ai-autopilot`, namespace `workers` |
| Embeddings | Vertex AI `gemini-embedding-001`, 768-dim, via `google-genai` SDK (keyless ADC) | Vertex AI |
| LLM generation | Vertex AI `gemini-2.5-flash` via raw `google-genai` (deliberately NOT ChatVertexAI), orchestrated by LangGraph 0.2.61 | Vertex AI |
| Tracing | LangSmith 0.1.147, project `collateral-material-gen` | LangSmith SaaS (external) |
| Cache | Redis via django-redis (cache only, not a queue) | — |
| Secrets | Secret Manager: `database-url`, `database-url-private`, `django-secret-key`, `langsmith-api-key`, … | Secret Manager |
| Images | Artifact Registry repo `collateral-ai-repo` (`backend:<sha>`) | Artifact Registry |

### Interactions (arrows)

- **Browser → Frontend**: HTTPS `https://collateralai.tinyfleet.dev` → global external HTTPS LB → Cloud CDN → GCS site bucket (SPA `index.html` fallback).
- **SPA → Backend**: REST `/api/v1/…` over HTTPS to the Cloud Run URL; typed client generated from the backend OpenAPI schema; CORS-restricted; TokenAuth + SessionAuth.
- **Backend → Cloud SQL**: Postgres over the Cloud SQL unix socket (`--add-cloudsql-instances`), via the serverless VPC connector (`private-ranges-only` egress).
- **Backend → GCS**: blob upload/download + keyless V4 signed URLs (runtime SA self-impersonation `SignBlob`).
- **Backend → GKE control plane**: HTTPS to the public, IAM-gated Kubernetes API endpoint (ADC bearer token + injected CA cert, no kubeconfig); creates BatchV1 Jobs `collateral-ai-backend-docproc-*` and `collateral-ai-backend-matgen-*`.
- **Worker pod → Cloud SQL**: Postgres over the DB **private IP** (`WORKER_DATABASE_URL` — different URL form than the Cloud Run socket).
- **Worker pod → Vertex AI**: embeddings + Gemini generation via Workload Identity (KSA `workers/worker` → GSA `gke-worker-sa`).
- **Worker pod → GCS**: download source PDFs, upload extracted images.
- **Worker pod → LangSmith**: outbound HTTPS traces (matgen worker only).

### Networking (from `deploy/`)

- Custom VPC `collateral-ai-network`, subnet `collateral-ai-subnet` `10.10.0.0/24` (us-central1) with GKE secondary ranges `gke-pods` `10.20.0.0/16` and `gke-services` `10.30.0.0/20`.
- Serverless VPC Access connector `collateral-ai-connector` (`10.8.0.0/28`) — Cloud Run attaches with `private-ranges-only` egress.
- Private Services Access peering for Cloud SQL (private IP only, `ipv4_enabled=False`).
- GKE Autopilot: private nodes, **public IAM-gated control-plane endpoint** (master authorized networks `0.0.0.0/0`, gated by IAM+RBAC not IP allowlists).
- Service accounts (least privilege):
  - `cloud-run-sa` (runtime): cloudsql.client, secretmanager.secretAccessor, storage.objectAdmin, aiplatform.user, run.developer, container.developer, self `serviceAccountTokenCreator`.
  - `gke-worker-sa` (workers): aiplatform.user + storage.objectAdmin only.
  - `github-cicd-sa` (CI/CD): artifactregistry.writer, run.admin, iam.serviceAccountUser, storage.admin, compute.loadBalancerAdmin; keyless via Workload Identity Federation.
- GCP project `collateralai-501708`; DNS zone for `tinyfleet.dev` lives in separate project `shared-infra-project-501613`.

### Suggested diagram grouping

Three planes: **(a) Edge/CDN** (browser → LB → CDN → SPA bucket), **(b) Sync API plane** (Cloud Run Django ↔ Cloud SQL / GCS / Secret Manager), **(c) Async/AI plane** (Cloud Run → GKE Jobs → Vertex AI + Cloud SQL private IP + GCS + LangSmith). Cross-cutting: VPC, IAM/Workload Identity, Artifact Registry + GitHub Actions feeding images.

---

## 2. Document Ingestion Pipeline

**Pattern: direct-to-GCS upload via signed URL → `/complete` flips DB status and dispatches a K8s Job → worker extracts, chunks, embeds, and bulk-inserts pgvector rows → frontend polls.**

### Sequence

```
Browser (DocumentsTab / UploadsProvider)
  │ 1. POST /api/companies/{cid}/documents/   {file_name, content_type}
  ▼
Django DocumentViewSet.create ──► INSERT Document(status=pending)
  │    computes storage_path, signs V4 PUT URL (15-min expiry)
  ◄── 201 {document, upload_url}
  │ 2. PUT upload_url  (raw PDF bytes, XHR with progress)
  ▼
GCS  media/companies/{cid}/documents/{doc_id}/{name}.pdf
  │ 3. POST …/documents/{id}/complete/
  ▼
DocumentViewSet.complete ──► status=processing ──► trigger_processing()
  ├─ local dev: inline `manage.py process_document`
  └─ prod: K8s Job on GKE Autopilot (ns `workers`, KSA `worker`,
     image = backend:<sha>, cmd `manage.py process_document --document-id N`,
     backoff_limit=1, deadline 900s, 2 CPU / 2Gi)
  ◄── 202 Accepted
        ▼ (worker pod)
DocumentProcessingService.process()
  ├─ StorageService.download(GCS)
  ├─ PdfExtractionService: PyMuPDF (text + images), pdfplumber (tables→Markdown);
  │  images re-uploaded to GCS as caption chunks (no OCR/vision)
  ├─ ChunkingService: word windows, 300 words / 50 overlap, version "v1"
  ├─ EmbeddingService: Vertex AI gemini-embedding-001, 768-dim,
  │  batch 64, task_type=RETRIEVAL_DOCUMENT, L2-normalized
  ├─ _save_chunks: atomic DELETE old chunks → bulk_create DocumentChunk (vector(768))
  └─ status=processed (+ page/chunks/tables/images counts)  |  on error → failed + error_message
        ▼
Browser polls GET …/documents/ every 3s while status==processing
```

### Details worth labeling

- **Upload validation**: `content_type` must be `application/pdf`; file name ≤255 chars; 503 if GCS unconfigured. The "max 50 MB" is UI copy only — not enforced server-side.
- **Models**: `Document` (status machine `pending → processing → processed|failed`, counts, `error_message`) and `DocumentChunk` (FK document + denormalized FK company, `chunk_type` text|table|image_caption, `page_number`, `content`, `embedding vector(768)`, `metadata` JSON).
- **No ANN index** — no HNSW/IVFFlat; retrieval is an exact cosine scan over company-filtered rows (fine at current scale, a known future optimization).
- **No dedup/checksum** — re-processing deletes and recreates all chunks for the document (idempotent replace).
- **Retry** is user-driven: the Retry button re-POSTs `/complete/`.
- **Completion signaling is polling** (TanStack Query `refetchInterval` 3000ms), not websockets/SSE.

Key files: `documents/api/views.py`, `documents/gcs.py`, `documents/worker_trigger.py`, `worker_jobs.py`, `documents/processing/{pipeline,extraction,chunking,embeddings}.py`, `documents/models.py`, `frontend/src/lib/api/documents.ts`.

---

## 3. Retrieval + Material Generation (Worker 2, LangGraph)

### Entry point

- `POST /api/materials/` (create) and `POST /api/materials/{id}/regenerate/` — `MaterialViewSet` in `materials/api/views.py`.
- Frontend: 4-step wizard (`frontend/src/routes/create.tsx`): Companies → Template → Prompt → Generate.
- User inputs: `sender_company`, `receiver_company` (must differ, each needs ≥1 PROCESSED document), `template` (carries constraints: word limits, `body_section_count`, image slots, theme — default `newsletter_article_v1`), `prompt` (campaign goal), `tone`, `cta_style`, `cta_link`, `language`.

### Dispatch

- Row saved with `generation_status=queued` → `trigger_generation()`:
  - local: inline `manage.py generate_material`.
  - prod: K8s Job `collateral-ai-backend-matgen-*` (backoff_limit=0 — deliberate, validation failures are deterministic; deadline 600s; 1 CPU / 1Gi). LangSmith env vars are forwarded into the pod.
- Worker runs `MaterialGenerationService.generate()`: claims the row with `select_for_update` (QUEUED/FAILED → PROCESSING), then invokes the graph.

### The LangGraph graph (`materials/generation/graph.py`)

```
START → retrieve → generate → validate ──(is_valid)──► END
                                  │  ▲
                        (invalid, attempts < 2)
                                  ▼  │
                                repair ┘        (attempts ≥ max 2 → END as failed)
```

State (`GenerationState` TypedDict): `material_id`, `material`, `template`, `top_k`, `query_embedding`, `sender_chunks`, `receiver_chunks`, `source_map`, `allowed_ids`, `response_schema`, `output`, `validation_errors`, `is_valid`, `attempts`, `context_snapshot`.

- **retrieve**: builds a retrieval query from prompt + company names + tone; embeds via Vertex `gemini-embedding-001` (768-d, `task_type=RETRIEVAL_QUERY`, L2-normalized); runs **two** pgvector searches (sender + receiver): `DocumentChunk.objects.filter(company_id=…).annotate(distance=CosineDistance("embedding", q)).order_by("distance")[:top_k]` (top_k default 8). Chunks get synthetic ids `SENDER_SOURCE_1`, `RECEIVER_SOURCE_2`, …; builds `source_map` + `allowed_ids`; raises if either company has zero chunks.
- **generate**: calls `GenerationModel.generate_structured` with `SYSTEM_INSTRUCTION` ("senior B2B marketing strategist… use ONLY provided context, cite every claim, banned buzzword list, respect template word limits") + a JSON payload (material prompt, tone, cta, language, company profiles, template constraints, retrieved sender/receiver context) + a response schema.
- **validate**: deterministic `OutputValidator` — four error categories: `structure`, `word_limit`, `image_slot`, `source` (citations must be within `allowed_ids`).
- **repair**: re-calls the model with `REPAIR_SYSTEM_INSTRUCTION` ("fix ONLY the listed errors, no new claims") + the invalid output + errors; loops back to validate. Max 2 repair attempts.

### Generation call (`materials/generation/model.py`)

- **Raw `google-genai` SDK direct**: `genai.Client(vertexai=True).models.generate_content(...)` — deliberately NOT `ChatVertexAI` (a controlled A/B showed langchain-google-vertexai catastrophically degraded grounding; raw client grounds reliably).
- Model `gemini-2.5-flash`, temperature 0.2, max_output_tokens 8192, `response_mime_type=application/json` + **response schema** where `source_id` is an **enum of the allowed retrieved ids** — structurally preventing hallucinated citations. Thinking disabled (`thinking_budget=0`).
- "Grounding" = grounded in retrieved pgvector context injected into the prompt (no Google Search grounding tool).
- Server-side stamping: `template_id`, `theme`, `image_slots`, `cta_url` are stamped by code, never model-generated.

### Persistence + display

- Valid → `generation_status=COMPLETED`, saves `output_json`, `validation_result`, `retrieved_context` (context snapshot), `completed_at`, and bulk-creates **`GenerationSource`** rows (one per citation: company, document, chunk, role, page, snippet, used_fact, relevance_score) — powers the Sources tab.
- Invalid after repair budget / any error → `FAILED` + `error_message`.
- Frontend polls `GET /api/materials/{id}/` every 3s while queued/processing; renders via `newsletter-preview.tsx` + `material-sources.tsx`.

Key files: `materials/generation/{graph,service,retrieval,prompts,model,schema,validation}.py`, `materials/worker_trigger.py`, `materials/models.py`, settings `config/settings/base.py:333-370`.

---

## 4. Monitoring / Observability (LangSmith)

### LangSmith tracing

- **Entirely env-var driven, zero code in the hot path**: `LANGSMITH_TRACING=true`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT=collateral-material-gen`. When unset (local/CI), tracing is a no-op.
- **What's traced**: every `graph.invoke()` of the LangGraph generation pipeline auto-emits a trace — node path (`retrieve → generate → validate ⇄ repair`), repair cycles, node-level state I/O (retrieved chunks, prompts, JSON output).
- **What's NOT traced**: the raw `google-genai` Gemini calls are not individually wrapped (no `@traceable`, no dedicated child LLM span with token counts) — they appear only implicitly inside the `generate`/`repair` node spans. Live traces carry **no custom tags/metadata** (no job/user/version tags; `graph.invoke` passes no `config=`); `material_id` appears only inside the state payload. Two honest gaps to show on the diagram.

### Secret / env flow (draw this chain)

```
Pulumi (deploy/__main__.py, ENABLE_TRACING=true)
  └─► Secret Manager secret `langsmith-api-key`
        └─► cd.yml: gcloud run deploy --set-secrets LANGSMITH_API_KEY=langsmith-api-key:latest
                                       --set-env-vars LANGSMITH_TRACING=true;LANGSMITH_PROJECT=…
              └─► Backend Cloud Run env
                    └─► worker_jobs.py _FORWARDED_ENV: copied verbatim into the GKE matgen pod
                          └─► LangGraph auto-traces → HTTPS → LangSmith (project collateral-material-gen)
```

### Non-LangSmith observability

- **Structured logging → stdout → GCP Cloud Logging** (Cloud Run + GKE capture automatically). Timing logs per pipeline stage (`logger.info("timing: …")`), `logger.exception` on failure.
- **Django prod logging**: HTTP 500s email admins via `AdminEmailHandler` (the only alerting in the repo).
- **Health endpoint**: `GET /health/` → `200 {"status":"ok"}` (dependency-free; Cloud Run probes).
- **K8s job lifecycle**: `backoff_limit`, `active_deadline_seconds`, `ttl_seconds_after_finished=3600`; observed via the GKE control plane.
- **Not present**: no Sentry, no OpenTelemetry, no Prometheus/Datadog.

---

## 5. Evaluation Flow (offline eval harness)

**Offline, dev-time, LangSmith-experiment-based. Gates nothing (explicit non-goal) — a manual "did my change improve the average?" tool.**

### Flow

```
1. `manage.py seed_eval_dataset`
   ├─ seed.py builds 7 golden MarketingMaterials in the DB:
   │    3 substantive B2B company pairs × 2 templates (2-section+slots, 3-section no-slots)
   │    + 1 adversarial sparse-context case
   │    company facts seeded as DocumentChunks with REAL Vertex embeddings
   └─ datasets.py pushes examples to LangSmith dataset `material-gen-golden`
        (each example input is just {"material_id": <pk>} — content lives in the DB)

2. `manage.py run_eval [--label X]`   (locally via `just manage run_eval`, or Cloud Run Job via jobs.yml)
   ├─ target: full production pipeline — MaterialGenerationService.generate(force=True)
   │  (retrieve → generate → validate ⇄ repair; whole graph, not per-node)
   ├─ 5 evaluators score the final output:
   │    Deterministic:
   │      • schema_valid     — re-runs the production OutputValidator
   │      • sources_grounded — every cited source_id ∈ retrieved allowed set
   │      • counts_match     — body sections + image slots match template constraints
   │    LLM-as-judge (gemini-2.5-flash, temp 0.0, raw google-genai; retries on 429; never raises):
   │      • groundedness_judge — 0..1: every used_fact supported by cited context
   │      • specificity_judge — 0..1: concrete facts vs generic buzzwords
   └─ langsmith.evaluation.evaluate(..., experiment_prefix = git short-SHA or --label,
        max_concurrency=1) → uploads a scored experiment

3. Results: LangSmith Experiments UI (side-by-side comparison across commits/labels) + console line.
```

- Code: `materials/generation/eval/{seed,datasets,evaluators}.py`, commands `seed_eval_dataset.py`, `run_eval.py`.
- CI runs only pytest smoke tests of the harness (LangSmith client + judge mocked); real evals never run in CI.
- Ad-hoc single-material scoring exists: `run_eval.evaluate_one(material_id)` (no LangSmith).

---

## 6. CI/CD

Three GitHub Actions workflows. Auth everywhere is **keyless Workload Identity Federation** (GitHub OIDC → pool `collateral-ai-gh-pool` / provider `collateral-ai-gh-provider`, attribute-conditioned to this repo → SA `github-cicd-sa`). Pulumi provisions infra; Actions only deploys.

### CI — `ci.yml` (merge gates)

- Triggers: PRs to main + pushes to main. Concurrency: cancel-in-progress **true**.
- `changes` job (dorny/paths-filter) gates everything by path: `backend/**` vs `frontend/**`.
- **backend-lint**: pre-commit — ruff check + ruff format (v0.15.20), django-upgrade, djLint, standard hooks.
- **backend-test**: builds the docker-compose stack → `makemigrations --check` (migration drift gate) → `migrate` → `pytest`.
- **frontend-test**: `pnpm install --frozen-lockfile` (**this is the lockfile gate**) → `pnpm lint` (eslint) → `pnpm typecheck` (tsc) → `pnpm test` (**vitest merge gate**) → `pnpm build` (vite).
- All three run in parallel after `changes`.

### CD — `cd.yml` (deploy on push to main, path-filtered; or manual dispatch)

- Concurrency: cancel-in-progress **false** (deploys queue, never cancel).
- **deploy-backend**: WIF auth → docker build `backend/Dockerfile.cloudrun` → push `backend:<sha>` + `:latest` to Artifact Registry → `gcloud run deploy collateral-ai-backend` with VPC connector, Cloud SQL instance, secrets (`DATABASE_URL`, `DJANGO_SECRET_KEY`, `WORKER_DATABASE_URL`, `LANGSMITH_API_KEY`), and env vars wiring the K8s workers (`WORKER_IMAGE=backend:<sha>` — same image, `DOCUMENT_PROCESSOR_JOB`, `MATERIAL_GENERATOR_JOB`, `GKE_ENDPOINT`, `GKE_CA_CERT`, `WORKER_GCP_SERVICE_ACCOUNT`, LangSmith vars). Sizing: 1 CPU / 512Mi / concurrency 80 / min 0 / max 4.
- **deploy-frontend-gcs**: WIF auth → `pnpm install --frozen-lockfile` → Vite build (`VITE_API_URL`, `VITE_SITE_URL`) → `gcloud storage rsync ./dist gs://<frontend-bucket> --delete-unmatched-destination-objects` → `gcloud compute url-maps invalidate-cdn-cache collateral-ai-frontend-urlmap` (async, non-fatal).
- Backend and frontend deploy **in parallel**, no ordering guarantee. **No migrations run on deploy** (deliberate).

### Jobs — `jobs.yml` (manual, workflow_dispatch only)

- Runs a one-off **Cloud Run Job** `collateral-ai-backend-manage` for `manage.py <command>` (default `migrate`; also `createsuperuser`, `collectstatic`, `run_eval`…). Build (buildx + registry cache, from `backend/compose/production/django/Dockerfile` — a *different* Dockerfile than cd.yml) → `gcloud run jobs deploy` → `execute --wait`. Concurrency group `production-jobs` serializes runs.
- Migrations are gated only by manual dispatch — no GitHub environments/approval gates anywhere.

### Async worker deploy path (clarification for the diagram)

The K8s docproc/matgen workers have **no deploy pipeline of their own**: the worker image *is* the backend image at the same SHA. GKE Autopilot nodes pull it from Artifact Registry (node SA has `artifactregistry.reader`), and the backend creates the Jobs at request time. The historical WIF/GKE flakiness was fixed architecturally — public IAM-gated control-plane endpoint (no IP allowlist to flap) — not with retries.

### Pipeline sketch

```
PR ──► CI: changes ─┬─► backend-lint (ruff/pre-commit)
                    ├─► backend-test (compose, migrations --check, pytest)
                    └─► frontend-test (frozen lockfile, eslint, tsc, vitest, vite build)
merge to main ──► CD: changes ─┬─► deploy-backend: build Dockerfile.cloudrun → AR push → gcloud run deploy
                               └─► deploy-frontend-gcs: vite build → gcs rsync → CDN invalidate
manual dispatch ──► jobs.yml: build (prod Dockerfile) → Cloud Run Job `-manage` → execute --wait (migrate, …)
                     [all three auth via WIF: GitHub OIDC → collateral-ai-gh-provider → github-cicd-sa]
```
