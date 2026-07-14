# Design: Retrieval context enrichment (neighbor expansion + document summaries)

Date: 2026-07-14
Status: Approved (pending spec review)
Scope owner: Worker 2 retrieval context + Worker 1 summary step

## 1. Goal & scope

Material generation today grounds the LLM on the raw top-k retrieved chunks and
nothing else. A 300-word chunk often lacks its surrounding context — a table
with no introduction, a sentence whose referent lives in the previous chunk.
This project enriches the generation context two ways, without breaking the
chunk-granular citation contract:

1. **Neighbor expansion (small-to-big):** each retrieved chunk is expanded with
   its adjacent chunks at query time, so the model sees a coherent passage
   instead of a bare fragment.
2. **Per-document summaries:** each document gets a short LLM-generated summary
   at ingestion; the summaries of documents that contributed chunks are added
   to the generation prompt as orientation-only background.

**In scope:** `RetrievalService` expansion, chunk metadata additions at
ingestion, `Document.summary` + summarization step in Worker 1, generation
prompt changes, unit tests, before/after eval run.

**Out of scope (YAGNI):** backfill of existing documents (all companies,
materials, and documents will be deleted soon — confirmed by user), whole-file
context, page-level parent retrieval, a `ParentBlock` parent-child index,
re-ranking, changes to the validator or repair loop, frontend changes.

**Explicit constraints from the user:**
- Ignore old data; no backfill or legacy migration path beyond a graceful
  fallback when word offsets are absent.
- Verification is an eval gate: `run_eval` before/after comparison, not
  unit tests alone.

## 2. Background: what exists today

- **Ingestion (Worker 1):** `DocumentProcessingService` extracts text blocks /
  tables / image captions, chunks them (`ChunkingService`, 300 words max,
  50-word overlap), embeds (Vertex 768d), and bulk-creates `DocumentChunk`
  rows. The chunker computes `word_start`/`word_end` per chunk but
  `_build_payloads` drops them; only `chunk_index` (which **resets per block**)
  is persisted in `metadata`. Chunk ids follow payload insertion order, which
  is reading order within a document.
- **Generation (Worker 2):** LangGraph `retrieve → generate → validate ⇄ repair`.
  `RetrievalService.retrieve()` returns top-k (`MATERIAL_RETRIEVAL_TOP_K`,
  default 8) chunks per company by pgvector cosine distance. Each becomes a
  `RetrievedChunk` with a `SENDER_SOURCE_n`/`RECEIVER_SOURCE_n` id. Only these
  chunk texts reach the prompt. The validator restricts citations to those ids;
  `GenerationSource` rows persist cited chunks; `retrieved_context` snapshots
  what the model saw.
- **Model:** raw `google-genai` against Vertex (`MATERIAL_LLM_MODEL`, default
  `gemini-2.5-flash`). Generation must stay on google-genai direct (known
  ChatVertexAI structured-output grounding bug).

## 3. Neighbor expansion (Worker 2, query time)

### 3.1 Neighbor selection

For each seed chunk from the top-k:

- Candidates: chunks of the **same document and same `chunk_type`**, adjacent
  to the seed in **id order**, `MATERIAL_NEIGHBOR_WINDOW` (default 1) on each
  side. Id order approximates reading order because ingestion bulk-creates
  payloads in block order. Expansion never crosses documents or chunk types.
- `image_caption` chunks do not expand (window ignored).
- Query shape: one id-list query per contributing document (ids + minimal
  fields, ordered), neighbor resolution in Python, then a single batch fetch of
  neighbor contents. No per-seed content queries.

### 3.2 Dedupe rules

- A neighbor that is itself a seed is **skipped** — its content is already in
  the prompt under its own `source_id`.
- A neighbor shared by two seed windows (seeds two apart) attaches only to the
  **higher-ranked** seed (lower cosine distance).
- Net effect: no chunk's text appears twice in the prompt.

### 3.3 Stitching

- Ingestion starts persisting `word_start`/`word_end` in chunk `metadata`
  (§5.1). Where a neighbor and seed come from the same block (contiguous
  `chunk_index`, aligned word ranges), stitch **exactly** by word range so the
  50-word overlap appears once.
- Across block/page boundaries, or when offsets are absent (legacy chunks),
  join with a paragraph break (`\n\n`). This is the graceful-degradation path,
  not an error.
- The same-block rule handles tables naturally: continuation chunks of the
  **same table** stitch exactly and drop the repeated `"Extracted table"`
  prefix; a neighbor from a **different** table is paragraph-joined and keeps
  its prefix (it genuinely is a new table).

### 3.4 Data shape

`RetrievedChunk` keeps `content` (the seed chunk, unchanged) and gains
`expanded_content` (seed + stitched neighbors). `to_prompt_dict()` sends
`expanded_content`, so both the prompt and the `retrieved_context` snapshot
reflect what the model actually saw. `expanded_content == content` when the
window is 0 or no neighbors exist.

## 4. Citation contract (unchanged externally)

- `source_id` values, `allowed_ids`, `build_response_schema`, the validator,
  and the repair loop are untouched.
- `GenerationSource.snippet` remains the **seed** chunk's content `[:500]` —
  the retrieval anchor with its correct `page_number`.
- Accepted trade-off: a cited `used_fact` may originate from neighbor text
  inside the expanded passage. The document + page anchor is still correct and
  the full passage is auditable in `retrieved_context`.

## 5. Ingestion changes (Worker 1)

### 5.1 Chunk metadata

`_build_payloads` persists `word_start` and `word_end` (already computed by
`ChunkingService.chunk_text`) in `metadata` for text and table chunks. Bump
`DOCUMENT_CHUNKING_VERSION`.

### 5.2 Document summaries

- New `Document.summary` text field (`blank=True`, default `""`). One
  migration.
- New `DocumentSummaryService` (`documents/processing/summarization.py`): a
  thin google-genai direct client. Input: the already-built chunk payload
  contents concatenated in order, capped at `DOCUMENT_SUMMARY_INPUT_MAX_WORDS`
  (default 20 000) words. Prompt: summarize for B2B marketing grounding —
  products, positioning, metrics, industry, pain points — in at most
  `DOCUMENT_SUMMARY_MAX_WORDS` (default 150) words. Plain text call, no
  structured output.
- Pipeline order: extract → chunk → embed → save chunks → **summarize** →
  mark `PROCESSED`. Summarization is wrapped in try/except: on failure, log a
  warning, leave `summary=""`, and continue — a missing summary must never
  fail ingestion or block chunk availability.

## 6. Generation prompt changes

- `build_generation_payload` adds `sender_document_summaries` and
  `receiver_document_summaries`: `[{file_name, summary}]` for the **distinct
  documents that contributed retrieved chunks**, omitting documents whose
  summary is blank. Nothing is added when all summaries are blank.
- `SYSTEM_INSTRUCTION` gains one rule: document summaries are orientation-only
  background; every claim must still trace to a cited chunk `source_id`.
  Summaries carry no `source_id`, so the existing validator already rejects
  any attempt to cite them.

## 7. Configuration

All env-overridable via `base.py`, following existing naming:

| Setting | Default | Purpose |
|---|---|---|
| `MATERIAL_NEIGHBOR_WINDOW` | `1` | chunks each side of a seed; `0` restores today's behavior |
| `MATERIAL_INCLUDE_DOC_SUMMARIES` | `true` | include document summaries in the payload; `false` for eval A/B and rollback |
| `DOCUMENT_SUMMARY_MODEL` | `gemini-2.5-flash` | summarizer model |
| `DOCUMENT_SUMMARY_INPUT_MAX_WORDS` | `20000` | cap on summarizer input |
| `DOCUMENT_SUMMARY_MAX_WORDS` | `150` | target summary length |

`MATERIAL_NEIGHBOR_WINDOW=0` plus blank summaries reproduces current behavior
exactly — this is both the rollback path and the eval A/B knob.

## 8. Cost

- Generation prompt grows from ~7k to ~18–20k input tokens with window 1 and
  ≤16 sources (dedupe pulls it down; summaries add ≤150 words per contributing
  document): ~$0.002 → ~$0.006 per material on gemini-2.5-flash input pricing.
  Output cost unchanged.
- Summaries: one flash call per document at ingestion, ~$0.002–0.01 per
  document depending on size, once per document ever.
- No infra changes, no new services, no idle cost.

## 9. Error handling

- Summarization failure: warning log, blank summary, document still
  `PROCESSED`.
- Expansion is deterministic DB + string code — no LLM calls, no new failure
  modes in the generation path. Absent word offsets degrade to paragraph-break
  joins.

## 10. Testing & verification

**Unit tests:**
- Stitching: exact overlap removal via word ranges; block-boundary paragraph
  join; offsets-absent fallback; table prefix stripping; window=0 no-op.
- Dedupe: seed-neighbor skip; shared middle neighbor attaches to
  higher-ranked seed; no duplicated text across the prompt.
- Neighbor query scoping: never crosses document or chunk_type; image_caption
  never expands.
- Payload: summaries listed per distinct contributing document; blank
  summaries omitted; system-instruction rule present.
- Pipeline: summary step runs after chunk save; failure is non-fatal;
  `word_start`/`word_end` persisted; chunking version bumped.

**Eval gate (acceptance):**
- Run `run_eval` on `main` (baseline) and on this branch (window 1 +
  summaries). Compare judge scores and prompt token counts; record both in the
  PR description. If enrichment does not beat baseline, ship with
  `MATERIAL_NEIGHBOR_WINDOW=0` (dark) rather than revert.
