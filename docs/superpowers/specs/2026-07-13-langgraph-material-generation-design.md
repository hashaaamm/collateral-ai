# Design: LangGraph + LangSmith for Worker 2 (material generation)

Date: 2026-07-13
Status: Approved (pending spec review)
Scope owner: Worker 2 (material generation) only

## 1. Goal & scope

Re-architect **Worker 2** (`MaterialGenerationService`) as a LangGraph `StateGraph`
running on a **provider-swappable LangChain model layer**, trace every run to
**LangSmith Cloud**, and add an **offline eval harness** (deterministic +
LLM-judge groundedness) that doubles as a prompt-tuning and model-comparison tool.

This is an AI-engineering homework deliverable. The design optimizes for two
things simultaneously: (1) a genuinely good foundation, and (2) a clear
demonstration of modern LLM-engineering skill — graph orchestration, structured
output, RAG, tracing, and evaluation.

**In scope:** Worker 2 generation pipeline, its model call, tracing, eval harness,
seed data.

**Out of scope (YAGNI):** Worker 1 (document processing), human-in-the-loop
interrupts, LangGraph checkpointer/persistence, online eval on live traffic,
production eval automation/CI gating, prompt registry.

**Explicit constraints from the user:**
- **No backward compatibility.** Clean cutover — no feature flag, no dual code
  path, no shims. `llm.py` and `repair.py` are deleted; the graph is the only path.
- **Must not break.** A hard verification gate (Section 11) is part of "done":
  full test suite green, existing API tests green, and a real end-to-end
  generation run through the new graph producing a valid, saved `MarketingMaterial`.

## 2. Background: what exists today

`generate_material` management command → `MaterialGenerationService.generate()`:

1. `_claim()` — short `select_for_update` transaction: lock the row, check status
   (`QUEUED`/`FAILED` claimable unless `--force`), set `PROCESSING`, commit. The
   lock is deliberately **not** held across the pipeline.
2. `_run_pipeline()` — embed query → pgvector retrieve (sender + receiver) →
   Gemini structured-output call → validate → bounded `while` repair loop →
   `_save_completed()`.
3. `_save_completed()` — atomic write of output, validation result, retrieved
   context snapshot, and `GenerationSource` rows.

The pipeline runs as a GKE Autopilot K8s Job; the backend forwards a fixed set of
env vars into the worker pod via `_FORWARDED_ENV` in `worker_jobs.py`.

Provider today: raw `google-genai` against Vertex AI (keyless ADC). No LangChain /
LangGraph / LangSmith anywhere in the dependency tree.

## 3. Architecture — the graph

The graph replaces **only** `_run_pipeline`. `_claim` and `_save_completed` stay
as raw Django (the row-lock transaction and the atomic save have no place inside a
graph). The command flow becomes:

```
generate_material command
  → service.generate()
      → _claim()                         (unchanged, raw Django)
      → build_generation_graph().invoke(state)   (NEW)
      → _save_completed()                (unchanged, raw Django)
```

Graph topology:

```
       ┌──────────┐   ┌──────────┐   ┌──────────┐
START →│ retrieve │ → │ generate │ → │ validate │
       └──────────┘   └──────────┘   └────┬─────┘
                          ▲                │ (conditional edge on is_valid / attempts)
                          │                ├─ valid ───────────────→ END
                       ┌──┴────┐           │
                       │ repair│ ←─ invalid AND attempts < max
                       └───────┘           │
                                           └─ invalid AND attempts ≥ max → END (fail)
```

The **`validate → repair → validate` cycle** is the core LangGraph win: a
conditional edge routing on `is_valid` and `attempts`, replacing the imperative
`while` loop. A cyclic graph is what justifies LangGraph over a linear chain.

### Why the repair loop stays (design rationale)

Structured output — on **any** provider (Gemini `response_schema`, OpenAI strict
`json_schema`, Anthropic tool-use) — enforces the JSON **shape** only. The two
real failure modes are **semantic** and not expressible in JSON Schema:

- **Word limits** (`headline_max_words`, `body_section_max_words`, etc.) — JSON
  Schema has no "max words" keyword. A schema-valid headline can be 25 words when
  the limit is 10.
- **Source grounding** — `used_fact` accuracy, and `source_id` membership in the
  runtime-computed allowed set.

Pydantic validators / `OutputValidator` **detect** these after generation but do
not **correct** them. The only way to turn a violation into valid output (without
truncating copy mid-sentence, which is unacceptable for marketing text) is to send
it back to the model — the repair call. Switching LLM providers does **not**
remove this need; a stronger model only lowers the violation *rate*, so repair
remains the backstop. This is why the loop is kept, and the rationale is
deliberately "structured output handles shape, repair handles the semantics schema
can't."

## 4. State shape

A typed `GenerationState` (TypedDict) threads through nodes — no hidden globals:

```
material_id: int
material: MarketingMaterial          # the claimed row (with select_related)
template: MaterialTemplate
top_k: int

query_embedding: list[float]
sender_chunks: list[RetrievedChunk]
receiver_chunks: list[RetrievedChunk]
source_map: dict[str, RetrievedChunk]
allowed_ids: set[str]
response_schema: dict

output: dict                         # current model output (post-stamp)
validation_errors: list[dict]
is_valid: bool
attempts: int                        # repair counter

context_snapshot: dict               # sender/receiver context for persistence
```

## 5. Node breakdown — reuse, don't rewrite

Each node is a thin wrapper around existing, proven code. Reusing the domain logic
(rather than swapping in LangChain's default retriever/parser) is deliberate: it
demonstrates integrating real logic into the framework, not a tutorial.

| Node | Wraps | Source module |
| --- | --- | --- |
| `retrieve` | `EmbeddingService.embed_query` + `RetrievalService.retrieve` (sender & receiver), build `source_map`/`allowed_ids`, build `response_schema`; raise if either side has no chunks | `retrieval.py` (unchanged), `schema.py` |
| `generate` | LangChain model call with `SYSTEM_INSTRUCTION` + `build_generation_payload`; then `_stamp` | `model.py` (new), `prompts.py` (unchanged) |
| `validate` | `OutputValidator.validate`; write `is_valid`/`validation_errors` | `validation.py` (unchanged) |
| `repair` | LangChain model call with `REPAIR_SYSTEM_INSTRUCTION` + `build_repair_payload`; increment `attempts`; then `_stamp` | `model.py` (new), `prompts.py` (unchanged) |

`retrieval.py`, `validation.py`, `prompts.py` are untouched. `schema.py` gets the
optional dynamic-enum hardening (Section 7). `llm.py` and `repair.py` are
**deleted** and replaced by `model.py` + the graph nodes.

## 6. Model layer — provider-swappable, dynamic structured output

New `GenerationModel` (in `model.py`) wraps a LangChain chat model. Default is
`ChatVertexAI` (same Vertex/keyless-ADC auth, same `settings.MATERIAL_*`
knobs). Because the interface is LangChain's, the provider becomes a **setting**,
not a hardcode — `ChatVertexAI` → `ChatAnthropic` / `ChatOpenAI` (or Claude on
Vertex Model Garden, which preserves keyless-ADC) is a config change.

Per call, structured output is bound **dynamically per template**:

```python
schema = build_response_schema(constraints=..., image_slots=...)  # existing fn
structured = model.with_structured_output(schema)                 # dynamic, per-template
output = structured.invoke([system_msg, human_msg])
```

Open implementation questions (resolved during implementation, do not affect the
design):
- Whether `ChatVertexAI.with_structured_output` accepts the Vertex OpenAPI-subset
  dict directly, or needs a small `vertex_schema_to_json_schema()` converter
  (uppercase→lowercase types, same `minItems`/`maxItems`). Add the converter only
  if needed.
- Passing `thinking_budget=0` through `ChatVertexAI` (via `model_kwargs`) to
  preserve the current token-budget behavior. Verify early.

New settings:
- `MATERIAL_LLM_PROVIDER` (default `vertex`) — selects the chat-model class.
- Existing `MATERIAL_LLM_MODEL`, `MATERIAL_GENERATION_TEMPERATURE`,
  `MATERIAL_GENERATION_MAX_OUTPUT_TOKENS` continue to drive the model.

## 7. Bonus hardening — dynamic-enum source_id (recommended)

`build_response_schema` currently types `source_id` as a free `STRING`. Since the
allowed source ids are known at call time, constrain `source_id` to a **dynamic
enum** of the actually-retrieved ids. This makes the model *structurally unable* to
emit a hallucinated citation, removing one whole class of grounding failure before
it reaches validation. (Word-limit violations still require repair.) The
`OutputValidator` source check remains as a defense-in-depth backstop.

## 8. Tracing — LangSmith Cloud

Env-driven, zero code in the hot path. When the LangGraph app runs with tracing
env set, every `invoke` auto-emits a trace with the node path, repair cycles,
retrieved chunks, prompts, outputs, and token counts. Tracing is a **no-op when the
env vars are absent**, so local/CI runs stay clean.

Env vars (local: gitignored `.env`; the live key is never committed):
- `LANGSMITH_TRACING=true`
- `LANGSMITH_API_KEY=...`
- `LANGSMITH_PROJECT=collateral-material-gen`

**Integration requirement:** the K8s worker pod only receives env vars listed in
`_FORWARDED_ENV` in `worker_jobs.py`. The three `LANGSMITH_*` vars must be added
there for tracing to work in the real worker, not just local runs. (Secret
handling follows the existing pattern; the key lives in the environment forwarded
to the pod, consistent with how `DJANGO_SECRET_KEY` is handled today.)

## 9. Eval subsystem — offline, dev-time only

The eval harness is **offline / dev-time**. It never runs on live user requests;
the LLM-judge never touches the live path. It answers "did my change make the
system better on average?", against a fixed golden dataset. Two supported
workflows:

1. **Prompt / retrieval tuning** — edit `SYSTEM_INSTRUCTION` or `top_k`, run
   `run_eval --label <name>`, compare experiments in the LangSmith UI.
2. **Model comparison** — `run_eval --label gemini-flash` vs
   `--label claude-sonnet`, compare `repair_attempts` and `groundedness` on the
   golden set, pick on data.

New module `collateral_ai/materials/generation/eval/`:

- `seed.py` + `seed_eval_dataset` management command — **self-generated** golden
  data (created by us, not the user): a factory/fixture builds ~6–8 examples
  (`Company` + `Document` + `DocumentChunk` + `MaterialTemplate` +
  `MarketingMaterial`) covering varied templates (different section counts / image
  slots) plus at least one adversarial case (sparse context, to test grounding
  under-pressure). Pushes them to a LangSmith dataset `material-gen-golden`.
- `evaluators.py`:
  - Deterministic: `schema_valid`, `sources_grounded` (no hallucinated
    `source_id`), `counts_match` (sections/slots vs template), `repair_attempts`.
  - LLM-judge: `groundedness_judge` — scores whether each `used_fact` is supported
    by its cited chunk (judge model from `MATERIAL_EVAL_JUDGE_MODEL`).
- `datasets.py` — dataset create/lookup helpers.
- `run_eval` management command — runs the graph over the dataset via LangSmith
  `evaluate()`, uploads a named experiment (`--label`, default git short-SHA) so
  the comparison view works.

Deliverable for the writeup: one documented v1 → change → v2 iteration with the
LangSmith comparison view (prompt or model change).

## 10. File layout

```
materials/generation/
  graph.py          # NEW: GenerationState, node fns, build_generation_graph()
  model.py          # NEW: provider-swappable ChatVertexAI wrapper (replaces llm.py)
  service.py        # SLIMMED: _claim → graph.invoke → _save_completed
  schema.py         # UNCHANGED except optional dynamic-enum source_id (Section 7)
  prompts.py        # UNCHANGED
  retrieval.py      # UNCHANGED
  validation.py     # UNCHANGED
  llm.py            # DELETED
  repair.py         # DELETED
  eval/
    __init__.py
    seed.py
    evaluators.py
    datasets.py
materials/management/commands/
  seed_eval_dataset.py   # NEW
  run_eval.py            # NEW
```

## 11. Migration & verification (no backward compatibility; must not break)

**Migration:** in-place, behavior-preserving on the output contract. The graph
produces the **same** `output` dict and `context_snapshot` that `_save_completed`
already consumes, so the DB contract, statuses (`QUEUED`/`PROCESSING`/`COMPLETED`/
`FAILED`), the `--force`/`--top-k` flags, and the API are identical. No parallel or
flagged path; `llm.py`/`repair.py` are deleted in the same change.

**Verification gate (part of "done"):**
1. Full backend test suite green.
2. New tests:
   - Per-node unit tests with a fake model returning canned outputs (no network).
   - Graph-level test of the repair cycle: invalid-then-valid model → exactly one
     repair → valid; always-invalid model → fails after `max_repair_attempts`.
   - Eval runner smoke test against the seeded dataset with the model faked.
3. Existing API tests (`test_material_views.py`) stay green.
4. **Real end-to-end run**: execute `generate_material --material-id <seed>` (force)
   against a real Vertex call and confirm a valid `MarketingMaterial` is saved with
   `COMPLETED` status and populated `GenerationSource` rows.
5. Lint/format gates pass (ruff PLC0415/SLF001 etc.), and `uv.lock` is regenerated
   and committed after adding dependencies (CI blocks otherwise).

## 12. Dependencies & config

- `pyproject.toml`: add `langgraph`, `langchain-google-vertexai`, `langsmith`
  (+ `langchain-core` transitively). Regenerate and commit `uv.lock`.
- `config/settings/base.py`: add `MATERIAL_LLM_PROVIDER` (default `vertex`),
  `MATERIAL_EVAL_JUDGE_MODEL`, and read the `LANGSMITH_*` vars.
- `worker_jobs.py`: add `LANGSMITH_TRACING`, `LANGSMITH_API_KEY`,
  `LANGSMITH_PROJECT` to `_FORWARDED_ENV`.
- `.env` (gitignored): holds the LangSmith key locally. The user's shared key
  should be rotated since it appeared in chat.

## 13. Risks

- **`with_structured_output` schema-dialect fit** — mitigated by the
  Vertex→JSON-Schema converter fallback.
- **`thinking_budget=0` passthrough** via `ChatVertexAI` — verify early; affects
  token budget.
- **LangChain/Vertex version churn** — pin versions; the model layer is isolated
  in `model.py` so churn is contained.

## 14. The homework story

A cyclic LangGraph pipeline with runtime self-correction; a provider-agnostic
model layer; structured output for shape plus a repair loop for the semantic
constraints schema cannot enforce; LangSmith tracing on live runs; and an offline
eval harness used to tune the prompt *and* compare models on data.
