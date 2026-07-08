# Material Management & Generation Worker — Design

**Date:** 2026-07-08
**Status:** Approved (brainstorming complete)
**Scope:** Materials backend app + generation worker (worker 2) + material/template frontend pages

## 1. Context

Collateral AI ingests company documents (worker 1: extract → chunk → embed into pgvector, 768-d Vertex `gemini-embedding-001` vectors). This feature adds the second half of the product: generating tailored B2B marketing materials from those documents, and the pages to create, list, review, approve and inspect them.

Everything below is greenfield: there is no `materials` app, no material API, and the frontend routes `/create`, `/materials`, `/templates` are placeholder stubs. The authoritative UI design is `mvp-frontend-architecture/README.md` (Claude Design handoff); referenced sections below (§4–§8b) point there.

## 2. Decisions (agreed during brainstorming)

| Decision | Choice |
|---|---|
| Status model | **Two fields**: `generation_status` (worker lifecycle) + `review_status` (human review) |
| Preview | **Client-side render** from `output_json` (worker produces JSON only, no HTML) |
| GenAI auth | **Vertex-only** via ADC (`genai.Client(vertexai=True, …)`), same as worker 1 |
| Scope | Company-tab list, global `/materials` list, material detail, create wizard, **plus** `/templates` list and `/templates/new` builder |
| Template flexibility | **Fixed contract + custom limits**: every template uses the newsletter JSON contract; templates customize word limits, body-section count, image slots, theme |
| Worker pipeline | **A: single-pass** structured-output generation + deterministic validation + repair loop (layered code so it can split into multi-stage later) |
| Template storage | DB `Template` model, seeded default `newsletter_article_v1` via data migration; no template edit/delete UI in MVP |

## 3. Data model (new app `collateral_ai.materials`)

Register in `LOCAL_APPS` (`backend/config/settings/base.py`). Status constants live in `materials/statuses.py` (mirroring `documents/statuses.py`).

### 3.1 `Template`

| Field | Type | Notes |
|---|---|---|
| `name` | Char 255 | e.g. "Newsletter Article" |
| `slug` | Slug, unique | auto-slugified from name, uniquified with numeric suffix (`newsletter_article_v1` style IDs); read-only after create |
| `description` | Text, blank | |
| `constraints` | JSON | `{headline_max_words, subheadline_max_words, body_section_count, body_section_max_words, cta_max_words}` — all positive ints |
| `image_slots` | JSON list | `[{slot_id, label, spec, source}]`; `source ∈ sender \| receiver \| generated_placeholder`; `slot_id` slug-like, unique within the template |
| `theme` | JSON | `{primary_color, accent_color}` hex strings |
| `is_active` | Bool, default true | design's "Active" pill |
| `created_at`, `updated_at` | | |

No `schema_json` field: with the fixed contract, the structured-output schema is built in code and parameterized by `constraints`/`image_slots`.

**Seed data migration:** `newsletter_article_v1` — headline ≤10, subheadline ≤22, 2 body sections ≤80 each, CTA ≤15; slots `hero_image` (spec `1200×630`, source `generated_placeholder`) and `sender_logo` (spec `SVG/PNG`, source `sender`); theme `#5b5bd6` / `#0f172a` (design §8).

### 3.2 `MarketingMaterial`

| Field | Type | Notes |
|---|---|---|
| `title` | Char 255 | |
| `description` | Text, blank | |
| `sender_company` | FK Company, CASCADE | `related_name="materials_as_sender"` |
| `receiver_company` | FK Company, CASCADE | `related_name="materials_as_receiver"` |
| `template` | FK Template, PROTECT | deleting a template must not destroy materials |
| `prompt` | Text | campaign goal |
| `tone` | Char 32, default `professional` | wizard chips: Professional / Friendly / Executive / Technical |
| `cta_style` | Char 32, default `soft` | chips: Soft / Direct |
| `language` | Char 32, default `english` | |
| `generation_status` | Char 16, choices | `queued → processing → completed \| failed`; default `queued` |
| `review_status` | Char 16, choices | `pending → approved \| rejected`; default `pending` |
| `output_json` | JSON, null | contract in §4 |
| `validation_result` | JSON, null | `{is_valid, errors: [{category, message}]}` (§6.4) |
| `retrieved_context` | JSON, null | snapshot of chunks sent to the LLM (debugging) |
| `error_message` | Text, blank | |
| `job_operation_name` | Char 255, blank | Cloud Run operation name from trigger |
| `created_at`, `updated_at`, `completed_at` (null) | | |

Ordering `-created_at`. Indexes on `sender_company`, `receiver_company`, `generation_status`.

**Status pill mapping (derived, frontend):** `queued`/`processing` → Processing (amber, spinning `circle-notch`); `failed` → Failed (red `x-circle`); `completed`+`pending` → Needs review (violet `flag`); `completed`+`approved` → Approved (green `check-circle`); `completed`+`rejected` → Rejected (red `prohibit`). The design's "Draft" pill is unused (no draft state — creation immediately queues).

### 3.3 `GenerationSource`

| Field | Type | Notes |
|---|---|---|
| `material` | FK MarketingMaterial, CASCADE | `related_name="sources"` |
| `company` | FK Company, CASCADE | denormalized, like `DocumentChunk.company` |
| `document` | FK Document, CASCADE | |
| `chunk` | FK DocumentChunk, **SET_NULL**, null | worker 1 deletes+recreates chunks on reprocess, so this may dangle |
| `source_role` | Char 16 | `sender \| receiver` |
| `page_number` | PositiveInt, null | denormalized from chunk |
| `snippet` | Text | quoted excerpt shown in Sources tab (denormalized chunk content, truncated ~500 chars) |
| `used_fact` | Char 1000 | LLM's explanation of the fact used |
| `relevance_score` | Float, null | cosine distance at retrieval time |
| `created_at` | | |

## 4. Output JSON contract (canonical)

Produced by the worker, rendered by the frontend preview, shown raw in the JSON tab. Deliberate deviations from the design's Layout-JSON example (§7): `word_count` is not stored (validator and frontend meters compute counts from text); the design's `assets` key becomes `image_slots` (matches the Template model); the design's embedded `validation` object lives in the separate `validation_result` field instead; `source_references` is added (feeds the Sources tab). Body sections use `title`, matching the design.

```json
{
  "template_id": "newsletter_article_v1",
  "theme": { "primary_color": "#5b5bd6", "accent_color": "#0f172a" },
  "article": {
    "headline": "…",
    "subheadline": "…",
    "body_sections": [ { "title": "…", "text": "…" } ],
    "cta": "…"
  },
  "image_slots": [
    { "slot_id": "hero_image", "description": "…", "source": "generated_placeholder" }
  ],
  "source_references": [
    { "source_id": "SENDER_SOURCE_1", "used_fact": "…" }
  ]
}
```

`template_id` **and `theme`** are stamped server-side from the template after every model response (never trusted from, or generated by, the model — `theme` is excluded from the response schema entirely; it's template-owned and asking the model to echo it only invites repair churn). `image_slots[].slot_id` must cover every slot defined by the template; `source` must be the template-defined source for that slot. `source_references[].source_id` must be one of the labels of the retrieved context items — this is validated strictly (§6.3), so a stored `completed` material never contains an unknown id.

## 5. Backend APIs

Top-level resources on the existing `/api/` router (`backend/config/api_router.py`) — materials span two companies, so they are not nested under one. Conventions follow the codebase: `IsAuthenticated`, session/token auth, no pagination, `@extend_schema` annotations, typed `ModelSerializer`s.

### 5.1 `TemplateViewSet` — `/api/templates/`

`list`, `retrieve`, `create` only. Create accepts `{name, description?, constraints, image_slots, theme}`; slug is generated server-side. Serializer validates constraint keys/values (positive ints **with upper bounds** — `body_section_count ≤ 10`, `body_section_max_words ≤ 300`, `headline/subheadline/cta_max_words ≤ 60` — so no template can request output that exceeds the fixed generation token budget), slot shape (slug-format `slot_id`, unique within the template, valid `source`), and hex theme colors.

### 5.2 `MaterialViewSet` — `/api/materials/`

- **`GET /api/materials/`** — filters: `?company=<id>` (sender **or** receiver), `?sender=<id>`, `?receiver=<id>`, `?generation_status=`, `?review_status=`, `?search=` (title, DRF `SearchFilter`). List serializer is slim: no `output_json`/`retrieved_context`/`validation_result`; includes compact `sender_company`/`receiver_company` summaries `{id, name, logo_url}` and `template_slug`.
- **`POST /api/materials/`** — `{title, description?, sender_company, receiver_company, template, prompt, tone?, cta_style?, language?}`. Validation: sender ≠ receiver; both companies have ≥1 document with `status=processed` (400 with a clear message otherwise); template `is_active`. On success: save (`queued`/`pending`), call `trigger_generation(material)`, return **201** with the detail payload. If the trigger raises, the material is marked `failed` with the error (still 201; the failure is visible on the detail page).
- **`GET /api/materials/{id}/`** — full payload: all fields incl. `output_json`, `validation_result`, the same compact `sender_company`/`receiver_company` summaries `{id, name, logo_url}` as the list serializer (the header metadata line, preview eyebrow/logo chip, and Sources column headers all need names + logo), template summary `{id, name, slug, constraints, image_slots, theme}` (the detail page computes meters from it), and nested `sources[]`: `{id, source_role, page_number, snippet, used_fact, document: {id, file_name, company_id}}`. Signed GCS URLs are **not** embedded (they'd be re-signed on every poll); the frontend calls the document view-URL endpoint (§5.3) on click and appends `#page=N`.
- **`PATCH /api/materials/{id}/`** — updatable: `title`, `description`, `prompt`, `review_status`. Setting `review_status` to any value is rejected with 400 unless `generation_status == completed`. Editing `prompt` does not auto-regenerate (the UI offers Regenerate after saving).
- **`POST /api/materials/{id}/regenerate/`** — 409 if currently `queued`/`processing` **and** `updated_at` is newer than a staleness threshold (15 min — comfortably above the 600s job timeout). Stale `queued`/`processing` rows (job never started, or SIGKILLed mid-run so it couldn't write `failed`) may be regenerated; without this, stuck rows would be permanently unrecoverable through the API. On accept: reset `generation_status=queued`, `review_status=pending`, clear `output_json`/`validation_result`/`retrieved_context`/`error_message`/`completed_at`, delete existing sources, call `trigger_generation`, return **202**.
- **`DELETE /api/materials/{id}/`** — sources cascade.

### 5.3 Document view URL (new, on the documents app)

`GET /api/companies/{company_pk}/documents/{pk}/view-url/` — new `@action` on the existing `DocumentViewSet` returning `{url}` via a `signed_get_url(document.storage_path)` helper (same GCS module the logo flow uses), guarded by `gcs.is_configured()` (503 otherwise) and empty `storage_path` (404). **This endpoint does not exist today** — the documents API only issues signed *upload* URLs — yet both the material Sources tab and the design's Documents-tab open-in-new-tab action (§4) require it. Building it here unblocks both.

### 5.4 Company search (wizard)

No new endpoint — `GET /api/companies/?search=` already filters by name (`CompanyViewSet.search_fields`).

### 5.5 Worker trigger — `materials/worker_trigger.py`

Mirror of `documents/worker_trigger.py`: if `MATERIAL_GENERATOR_JOB` is empty → `call_command("generate_material", "--material-id", …)` inline (local/tests); else `run_v2.JobsClient().run_job()` with `ContainerOverride(args=["manage.py", "generate_material", "--material-id", str(pk)])`, storing the operation name in `job_operation_name`. **Deviation from the documents version:** callers do not suppress trigger exceptions — on failure the material is marked `failed` with the error message, so rows can't hang in `queued` invisibly.

Transaction semantics (the view runs under `ATOMIC_REQUESTS`):
- The view wraps `trigger_generation` in its own `transaction.atomic()` savepoint, so if the trigger (or the inline pipeline) raises, the mark-`failed` write still succeeds and the create still returns 201 with the failure visible on the detail page.
- In job mode, dispatch happens before the request transaction commits. The race (job container reading the row before commit) is accepted: Cloud Run Job cold start (~90s, per worker 1 ops experience) vastly exceeds commit latency. If it ever fires, the command exits non-zero and the row is recoverable via stale-regenerate (§5.2).
- In inline mode the entire pipeline (embedding + 1–3 Gemini calls) runs synchronously inside the request — POST may block for tens of seconds. Dev-only convenience, same semantics as the documents inline trigger.

## 6. Worker 2 — generation pipeline

### 6.1 Entry point

Management command `materials/management/commands/generate_material.py` with `--material-id` (required), `--force`, `--top-k`. Delegates to `MaterialGenerationService`. Non-zero exit on failure (exception re-raised), matching `process_document`.

### 6.2 Code layout — `materials/generation/`

| Module | Responsibility |
|---|---|
| `service.py` | `MaterialGenerationService` — orchestration + state machine |
| `retrieval.py` | pgvector top-k search per company → `RetrievedContextItem` DTOs |
| `schema.py` | builds the structured-output JSON schema from the template (`body_section_count` → array min/max items, slot ids → enum; `theme` and `template_id` are excluded — stamped server-side) |
| `prompts.py` | system instruction + JSON user payload |
| `llm.py` | thin Gemini wrapper: Vertex `genai.Client`, `generate_content` with `response_mime_type="application/json"` + `response_schema`, parses/returns dict |
| `validation.py` | deterministic validator → `ValidationResult{is_valid, errors:[{category, message}]}` |
| `repair.py` | corrective LLM call: invalid JSON + errors + constraints → fixed JSON |

Embeddings are **reused** from worker 1: `documents.processing.embeddings.EmbeddingService.embed_query()` (`RETRIEVAL_QUERY`, 768-d, L2-normalized — the exact counterpart of the stored `RETRIEVAL_DOCUMENT` vectors).

### 6.3 Flow

1. **Claim** — a short standalone `transaction.atomic()` block (the command runs outside `ATOMIC_REQUESTS`, and `select_for_update()` requires an explicit transaction): lock row → check status → set `processing`, clear `error_message` → commit. Generation runs **outside** this transaction so the row lock isn't held for the multi-minute pipeline (API PATCH/delete stay unblocked). Allowed from `queued`/`failed`; `completed` or `processing` without `--force` → log + skip with **exit 0** (a duplicate trigger racing a running job must not fail the Cloud Run execution); any status with `--force` (the manual escape hatch for rows stranded in `processing` by a crashed job).
2. **Retrieve** — one query string from prompt + sender/receiver names + tone; embed once; per company: `DocumentChunk.objects.filter(company_id=…)` ordered by `CosineDistance` (pgvector), top-k (default `MATERIAL_RETRIEVAL_TOP_K`). (`embedding` is non-nullable — every persisted chunk has one.) Items labeled `SENDER_SOURCE_n` / `RECEIVER_SOURCE_n`. Zero items on either side → raise with an actionable message ("no processed document chunks for X").
3. **Generate** — single `gemini-2.5-flash` call. System instruction: senior B2B marketing strategist; use only provided context; no unsupported claims; cite only provided `source_id`s; respect constraints. User payload (JSON): task, prompt, tone/cta_style/language, sender/receiver `{id, name, industry, description}`, template constraints + slots, and both context lists (`{source_id, file_name, page_number, chunk_type, content}`).
4. **Validate** — categories: `structure` (required fields/types), `word_limit` (per template constraints; counts by `str.split()`), `image_slot` (every template slot present, `source` matches template), `source` (non-empty; every cited id known). Strict `source` validation means unknown ids go through the repair loop, and the save step never sees one — there is no save-time skip or fallback.
5. **Repair** — up to `MATERIAL_MAX_REPAIR_ATTEMPTS` (2) corrective calls, re-validate after each; `template_id` and `theme` re-stamped after every model response.
6. **Save** — atomic. Valid → `completed`, `completed_at=now`, store `output_json`, `validation_result`, `retrieved_context`; replace `GenerationSource` rows by mapping the cited `source_id`s back to retrieval items (all guaranteed to map, per step 4). Invalid after repairs → `failed`, `error_message="Validation failed: …"`, but `output_json` + `validation_result` still stored (JSON tab works for debugging); no `GenerationSource` rows are written. Any exception → `failed` + `error_message`, re-raise.

`review_status` is never touched by the worker.

### 6.4 `validation_result` shape

`{is_valid: bool, errors: [{category, message}]}` with the four categories from §6.3 step 4 — mapping one-to-one onto the detail page's Quality checks: "JSON schema valid" (no `structure` errors), "Word limits passed" (`word_limit`), "Image slots present" (`image_slot`), "Sources attached" (`source`). (Theme is server-stamped, so it has no validation category; hex validation happens at template create, §5.1.)

### 6.5 Settings (env-driven, in `base.py` next to the embedding block)

| Setting | Default |
|---|---|
| `MATERIAL_GENERATOR_JOB` | `""` (inline) |
| `MATERIAL_GENERATOR_REGION` | `us-central1` |
| `MATERIAL_LLM_MODEL` | `gemini-2.5-flash` |
| `MATERIAL_GENERATION_TEMPERATURE` | `0.2` |
| `MATERIAL_GENERATION_MAX_OUTPUT_TOKENS` | `4096` |
| `MATERIAL_RETRIEVAL_TOP_K` | `8` |
| `MATERIAL_MAX_REPAIR_ATTEMPTS` | `2` |

No new dependencies: `google-genai`, `pgvector`, `google-cloud-run` are already in `backend/pyproject.toml`.

### 6.6 Deployment

Follow the worker-1 CI pattern (`.github/workflows/cd.yml`): deploy a second Cloud Run Job `collateral-ai-material-generator` (same backend image; `--command python --args manage.py,generate_material`; **1 CPU / 1Gi / 600s** task timeout; **`--max-retries 0`** — deliberate deviation from the doc-processor job: the command exits non-zero on deterministic failures like validation exhaustion, and an automatic re-run would silently burn 3 more LLM calls and flip a row the UI already shows as `failed` back to `processing`; recovery is the user-facing Regenerate button; env incl. `GOOGLE_CLOUD_PROJECT`, `VERTEX_LOCATION`, DB/GCS vars) and pass `MATERIAL_GENERATOR_JOB` + `MATERIAL_GENERATOR_REGION` to the web service. No Pulumi changes: the service account already holds `roles/aiplatform.user` (Gemini) and `roles/run.developer` (job triggering).

## 7. Frontend

Vite + React 19 SPA, TanStack Router/Query, openapi-fetch typed client. **Ordering constraint:** backend serializers must exist first, then `pnpm gen:api` regenerates `frontend/src/lib/api/schema.d.ts` before typed hooks compile.

### 7.1 Routes (`frontend/src/router.tsx`, under `appRoute`)

| Route | Page | Design ref |
|---|---|---|
| `/companies/$companyId` (existing) | Generated Materials tab: replace "Coming soon" with `<MaterialsTab>` | §4 |
| `/materials` (stub exists) | Marketing Requests table | §6 |
| `/materials/$materialId` (new) | Result Detail | §7 |
| `/create` (stub exists) | 4-step wizard (design says `/materials/new`; we keep the existing `/create` nav stub) | §5 |
| `/templates` (stub exists) | Templates list | §8 |
| `/templates/new` (new) | Template builder | §8b |

### 7.2 API layer

- `lib/api/materials.ts`: `useMaterials(filters)` (key `["materials", filters]`), `useMaterial(id)` (key `["materials", id]`) — both use the documents polling pattern: `refetchInterval` 3000 while any/this item is `queued`/`processing`, else `false`; `useCreateMaterial`, `useUpdateMaterial`, `useRegenerateMaterial`, `useDeleteMaterial` mutations invalidating `["materials"]`.
- `lib/api/templates.ts`: `useTemplates()`, `useCreateTemplate()`.

### 7.3 Pages & components

- **`components/materials-tab.tsx`** — two columns, *As Sender* (indigo tile `#eef0fe`/`#5b5bd6`, `arrow-up-right`) / *As Receiver* (violet tile `#f1eafe`/`#7c3aed`, `arrow-down-left`); clickable cards (title, counterpart name, status pill) → detail. Data: `useMaterials({company: id})`, split client-side by comparing `sender_company.id`.
- **`routes/materials-list.tsx`** — header + "New Request" button → `/create`; filter chips **All / Needs review / Approved / Rejected / Processing / Failed** (derived-pill counts; deviation from design's chip set, which predates the review workflow); table Title | Sender | Receiver | Status | Created, rows → detail. Hand-rolled table per `companies-list` pattern.
- **`routes/material-detail.tsx`** — breadcrumb (Marketing Requests / title); header: title + derived pill + metadata line (sender → receiver · template slug · generated time); actions: Regenerate (`arrows-clockwise`, ghost; disabled while processing), Edit prompt (`pencil-simple`, ghost → dialog with textarea → PATCH), **Approve** (green filled) / **Reject** (ghost destructive) — shown when `completed`; clicking the active one reverts to `pending`. (Reject is an addition to the design per the brief's approved/rejected/pending requirement.) Main panel tabs **Preview / Layout JSON / Sources** (underline tabs per `company-detail` pattern; Copy link on JSON tab) + 320px right rail: Quality checks (from `validation_result` categories), Constraint meters (word counts computed from `output_json` vs template constraints; green under ⅔ of the limit, amber at ≥⅔ — reproduces the design's examples: Subheadline 59% green, Body 68% amber), Actions (Copy JSON, Delete → `AlertDialog` → navigate `/materials`). States: `queued/processing` → centered progress panel (polling); after 15 min without change the panel enables Regenerate (the stale-row escape hatch, §5.2); `failed` → error banner (`error_message` + Regenerate) **above** the tabbed panel — when `output_json` exists the Layout JSON tab and validation-driven Quality checks stay accessible (that's why the worker persists them); Preview renders only if `output_json` exists, Sources only if `sources[]` is non-empty; constraint meters hidden when there's no output.
- **`components/newsletter-preview.tsx`** — client-side preview (§7 Preview tab): centered card ≤460px, themed from `output_json.theme` (server-stamped = template theme). Slot rendering is generic so builder-created templates work on day one: slots render in template order — the first `generated_placeholder` slot is the full-width striped hero block (labeled with slot label + spec); `source=sender`/`receiver` slots render as floating `CompanyLogo` chips for the respective company; any further `generated_placeholder` slots render as smaller striped blocks between body sections. Then eyebrow "SENDER × RECEIVER", headline/subheadline, titled body sections, CTA strip.
- **Sources tab** — two columns (Sender/Receiver) of source cards: `file-pdf` icon, file name, mono `p.N`, open-in-new-tab button (fetches the new document view-URL endpoint §5.3, opens `url#page=N`), italic quoted snippet.
- **`routes/create-material.tsx`** — 4-step wizard, `max-w-[820px]`, local `useState`. Step 1: Sender/Receiver search pickers (Input + `useDebouncedValue` + `useCompanies(search)` result list; selected row `bg-#f4f4fd` + left border + `check-circle`; row subline "industry · N docs" and the grounding strip use processed-doc counts fetched via `useDocuments(companyId)` for the selected/listed companies); Continue blocked until both selected, distinct, and each has ≥1 processed doc. Step 2: template cards from `useTemplates()` (constraint list rendered from `constraints`), disabled dashed "Brochure (Tri-fold) — Coming soon" card. Step 3: **Title input and optional Description input — deliberate additions to the design's step** (the design never says where a material's title comes from, but the model requires one and the brief's create page lists name + description) — then prompt textarea, Tone chips (Professional/Friendly/Executive/Technical), CTA style chips (Soft/Direct), Language select (English). Step 4: summary rows + full-width "Generate Marketing Material" (`magic-wand`) → `useCreateMaterial` → navigate to detail (which polls). API 400s render inline above the footer.
- **`routes/templates-list.tsx`** — header + "New Template" → `/templates/new`; active template card(s) from `useTemplates()` (constraints, image slots, theme swatches, skeletal layout preview); right column: two disabled "Coming soon" cards.
- **`routes/template-new.tsx`** — fixed-contract builder: Basics (name, read-only auto-slug preview, description); Text fields (Headline/Subheadline/CTA rows with `≤ N words` steppers; body-section rows addable/removable via dashed "Add text field" — adding a field = adding a body section, min 1, max 10; **all body rows share a single word-limit stepper value** — editing any body row's stepper updates all of them; row count → `body_section_count`, shared value → `body_section_max_words`; stepper bounds mirror the §5.1 serializer bounds); Image slots (rows: slot label + spec input + source select + delete; dashed "Add image slot"; **`slot_id` is derived client-side by slugifying the label**, uniquified with a numeric suffix on collision — same rule as the template slug); Theme colors (primary/accent hex inputs + swatches). Sticky live skeletal preview + summary chips. **No drag-reorder** (fixed contract ⇒ fixed order; dnd-kit dropped). Save → `useCreateTemplate` → `/templates`.
- **`components/status-pill.tsx`** — extend with a `materialPillStatus(generation_status, review_status)` helper + new entries (Needs review = violet `flag`, Approved = green, Rejected = red `prohibit`, Processing reuses amber spinner, Failed reuses red). New violet tokens in `index.css` `@theme`: `review: #7c3aed`, `review-soft: #f1eafe` (design's Needs-Review colors, currently missing).

Reused as-is: `CompanyLogo`, `AlertDialog`, `Button`, `Card`, `Input`, `useDebouncedValue`, underline-tab and hand-rolled-table patterns. Icons: Phosphor.

## 8. Error handling summary

| Failure | Behavior |
|---|---|
| Trigger dispatch fails (create/regenerate) | material → `failed` + `error_message`; visible on detail page |
| No retrievable context for a company | worker raises actionable message → `failed` |
| Gemini call fails / empty / invalid JSON | exception → `failed` + `error_message`, non-zero job exit |
| Validation fails after repairs | `failed`, but `output_json` + `validation_result` persisted |
| Create-time misuse (sender=receiver, no processed docs, inactive template) | 400 with field errors, shown in wizard |
| `review_status` change before completion | 400 |
| Regenerate while actively processing | 409 (fresh `queued`/`processing` only) |
| Row stuck in `queued`/`processing` (job never started / SIGKILLed) | regenerate allowed once `updated_at` older than 15 min; UI enables Regenerate on the processing panel after 15 min |
| Duplicate worker execution racing a running job | claim step skips with exit 0 |
| Polling | stops on `completed`/`failed` |

## 9. Testing

Backend (pytest + factory-boy, mirroring `documents/tests/`):

- **Factories:** `TemplateFactory` (seed-shaped defaults), `MarketingMaterialFactory`, `GenerationSourceFactory`.
- **API tests:** template create/validation (constraint bounds, slot_id rules, hex colors); material list filters (`?company=` OR-semantics, statuses, search); create happy path with mocked `trigger_generation` (called once) + all 400 validations; trigger-failure marks `failed` (and still returns 201); PATCH rules (review transitions, prompt edit); regenerate (reset + re-trigger; 409 while fresh-processing; allowed when stale); delete cascade; document view-url action (signed URL returned; 503 when GCS unconfigured).
- **Generation service tests** (mocked `llm.py` client + `EmbeddingService`, seeded chunks via `DocumentChunkFactory`): happy path end-to-end state changes incl. server-stamped `template_id`/`theme`; repair loop invoked on invalid (incl. unknown `source_id`) then valid; validation-exhausted → `failed` with output persisted and no source rows; empty-context error; `--force` re-run; `completed`/`processing` skip with exit 0 without `--force`.
- **Validator unit tests:** each of the four categories, word-limit boundaries, slot matching, unknown source ids.
- **Trigger wrapper test:** inline mode dispatches `call_command`; job mode builds correct job name + override args (mocked `run_v2`).

Frontend: the repo has vitest with colocated unit tests for every `lib/api` module (`auth`, `companies`, `documents` all have `*.test.ts`) — materials/templates follow that convention: tests for `lib/api/materials.ts` and `lib/api/templates.ts` covering query keys, the polling `refetchInterval` predicate (polls while queued/processing, stops on terminal states), and mutation invalidations. No page/component tests (none exist in the repo). End-to-end verification: run the compose stack and exercise all five pages (documents already processed → create material → poll → review/approve → sources open at page).

## 10. Out of scope / future

- Template edit/delete, brochure/email-campaign templates, fully dynamic template fields
- Worker-generated HTML email + sending
- Gemini API-key mode
- Real image generation for `generated_placeholder` slots (preview shows placeholders)
- pgvector ANN index (HNSW) — fine at MVP scale, revisit when chunk counts grow
- Pagination on material lists (codebase-wide convention is unpaginated)
