# Worker readability refactor — design

**Date:** 2026-07-14
**Status:** Approved
**Scope:** the two K8s worker flows — document ingestion (`process_document`) and material generation (`generate_material`)

## Context

Both worker flows are functionally solid (shipped, tested, in prod) but hard to walk through:
the step sequence is not visible in one place, ownership per layer is implicit, and four
specific spots confuse readers. The owner needs to explain this code confidently in an
interview. This is a **behavior-preserving readability refactor** — same idea, cleaner code,
nothing over-engineered.

The layering story the refactor makes explicit:

> **command = process boundary, service = DB state machine, pipeline/graph = compute flow,
> sub-services = one capability each.**

## Design patterns in play (interview vocabulary)

These patterns are already present; the refactor makes each one visible rather than adding
new ones:

- **Facade** — `DocumentProcessingService.process()` and `MaterialGenerationService.generate()`
  are single entry points hiding a multi-class subsystem; every caller (K8s command, eval
  harness) enters through them. Strictly they are *application services acting as facades*:
  unlike a pure GoF facade they are the only sanctioned entry and also own transactions and
  status transitions. The refactor makes each facade method read as the flow it fronts.
- **Pipeline** — ingestion is a linear step pipeline (the orchestrator method); generation's
  pipeline is declared as LangGraph edges.
- **State machine** — two levels: the DB status fields (`DocumentStatus`,
  `GenerationStatus`) owned by the services, and LangGraph's conditional edge
  (validate → repair / END) for the in-memory repair loop.
- **Dependency injection** — `MaterialGenerationService` takes optional
  embedder/retriever/model overrides; after the refactor the graph nodes receive an explicit
  `GenerationDeps` instead of closing over variables.
- **Strategy (seam)** — `GenerationModel.generate_structured` is provider-swappable behind
  one interface (`vertex` today, per the grounding constraint).

Deliberately absent: inheritance-based Template Method and a generic Step framework — plain
composition was chosen over both to avoid indirection.

## Goals

1. Each worker's end-to-end flow readable top-to-bottom in a single orchestrator.
2. Every file can answer "what do I own" (module docstrings state it).
3. Fix the four confusing spots:
   - timing instrumentation drowning `DocumentProcessingService.process()`
   - three near-duplicate raw-dict payload loops in `_build_payloads`
   - `build_generation_graph` as a 130-line closure factory with nested node functions
   - validation running twice (inside the graph, then again in `_run_pipeline`)
4. A short architecture doc with flow diagrams as the interview cheat sheet.

## Non-goals

- No new frameworks, base classes, or step abstractions (a shared Step/Pipeline framework
  was considered and rejected as over-engineering).
- No file merging/splitting beyond what is listed below (collapsing sub-services into fewer,
  bigger files was considered and rejected).
- No changes to RAG behavior, prompts, response schema, model calls, or the eval harness.
- No changes to how jobs are dispatched (`worker_trigger.py` untouched).

## Behavior invariants (must hold after refactor)

- Same DB writes: statuses, `output_json`, `validation_result`, `retrieved_context`,
  `GenerationSource` rows, `DocumentChunk` rows — byte-identical shapes.
- Missing row → `Document.DoesNotExist` / `MarketingMaterial.DoesNotExist` → `CommandError`.
- Any pipeline failure → status `FAILED` + `error_message` + re-raise (non-zero exit → K8s
  job failure/retry semantics unchanged).
- Generation claim-skip (not QUEUED/FAILED, no `--force`) → return `False` → exit 0.
- Claim remains a short standalone transaction; the row lock is never held during generation.
- Document summary stays best-effort: its failure never fails ingestion.
- `review_status` is never touched by the worker.
- Keyless ADC + google-genai direct for all Vertex calls (grounding constraint — do not
  reintroduce langchain wrappers for generation).

## Design

### Ingestion — `documents/processing/pipeline.py`

`process()` becomes the story, nothing else:

```python
def process(self, document_id: int, *, force: bool = False) -> None:
    document = self._start(document_id)          # fetch + mark PROCESSING
    try:
        pdf_bytes = self._download(document)
        extraction = self._extract(document, pdf_bytes)
        payloads = self._build_payloads(document, extraction)
        embeddings = self._embed(payloads)
        self._save_chunks(document, payloads, embeddings)
        summary = self._summarize(document.id, payloads)
        self._finish(document, extraction, payloads, summary)
    except Exception as exc:
        self._fail(document, exc)
        raise
```

- Every `time.monotonic()` / `logger.info("timing: …")` pair moves inside the step helper it
  measures. Where no result-count is needed a tiny `_timed()` context manager is used; steps
  that log counts (bytes, pages, chunks) keep a single log line inside the helper. The
  orchestrator contains zero instrumentation.
- The empty-content guard moves into `_build_payloads`; the embedding/chunk count-mismatch
  guard moves into `_embed`. The `# noqa: TRY301` workarounds disappear naturally (raises no
  longer sit directly in the `try`).
- `_build_payloads` delegates to `_text_payloads` / `_table_payloads` / `_image_payloads`
  (the three sources stay explicit — no clever unification). Each builds a frozen
  `ChunkPayload` dataclass (`chunk_type`, `page_number`, `content`, `metadata`) so the shared
  shape is declared once and `p["content"]` becomes `p.content`.
- `_start` = fetch (`select_related("company")`) + mark `PROCESSING` (clears
  `error_message`). `DoesNotExist` propagates before the `try`, so no spurious `FAILED`
  write — matching current behavior.
- `_finish` = the final `PROCESSED` update with summary + counts. `_fail` = the `FAILED`
  update + logging.
- `_save_chunks` and `_summarize` keep their current bodies (adjusted for `ChunkPayload`
  attribute access).

### Generation — `materials/generation/graph.py`

Keeps LangGraph (approved choice — merged in PR #28, and the edge wiring is the explicit
flow definition). Stops being a closure factory. New file order reads top-to-bottom:
**state → nodes → routing → wiring**.

- New frozen dataclasses:
  - `GenerationDeps(embedder, retriever, model, validator, max_repair_attempts)` —
    constructed by the service, passed to `build_generation_graph`.
  - `RetrievedContext` — groups the nine retrieval outputs (query embedding, sender/receiver
    chunks, sender/receiver document summaries, `source_map`, `allowed_ids`,
    `response_schema`, `context_snapshot`).
- `GenerationState` shrinks from 17 flat keys to ~8: inputs (`material_id`, `material`,
  `template`, `top_k`), `retrieval: RetrievedContext`, `output: dict`,
  `validation: ValidationResult`, `attempts: int`.
- Nodes become module-level named functions — `retrieve(state, deps)`,
  `generate(state, deps)`, `validate(state, deps)`, `repair(state, deps)` — and the routing
  function `route_after_validate(state, deps)` sits beside them. All are bound with
  `functools.partial` inside `build_generation_graph(deps)`, which shrinks to just the edge
  wiring (~10 lines).
- **Double validation removed:** the validate node stores the full `ValidationResult` under
  `validation` (instead of unpacked `is_valid` / `validation_errors`). The service reuses it;
  `result.to_dict()` produces byte-identical `validation_result` JSON in both the failure and
  success branches (validator is deterministic), so persisted data is unchanged.
- Inline imports of `build_retrieval_query` (prompts) and `trim_to_word_limits` (validation)
  hoist to module top — no import cycle exists (verify once at implementation). The lazy
  `langgraph` import inside `build_generation_graph` **stays**, with a one-line comment: it
  keeps web pods from paying the langgraph import at startup.
- `_stamp`, `_require_chunks`, `_document_summaries` remain module-level helpers.

### Generation — `materials/generation/service.py`

Already well-documented; keeps its claim/save shape. Two touch-ups:

- `_run_pipeline` reads `final["validation"]` and `final["retrieval"]` instead of
  re-running the validator; passes a `GenerationDeps` to `build_generation_graph`.
- `_save_completed` binds `src = source_map[ref["source_id"]]` once per reference (loop or
  helper) instead of indexing the map seven times per row.
- Module docstring gains the ownership line (service owns the DB state machine; graph owns
  compute).

### New doc — `docs/workers-flow.md`

The interview cheat sheet:

- Two mermaid flow diagrams: ingestion (linear) and generation (with the validate ⇄ repair
  cycle and max-attempts exit).
- The four-layer ownership one-liner and the "Design patterns in play" list (Facade,
  Pipeline, State machine, Dependency injection, Strategy seam).
- A table of failure/skip semantics (what exits 0, what exits non-zero, what K8s does).

### Untouched files

`chunking.py`, `embeddings.py`, `summarization.py`, `storage.py`, `extraction.py`,
`validation.py`, `retrieval.py`, `expansion.py`, `prompts.py`, `model.py`, `schema.py`,
both management commands, both `worker_trigger.py`, everything under `eval/`.

## Testing

- Existing suites are the safety net; coverage is not weakened.
- `test_graph.py` / `test_service.py`: mechanical updates for the new state keys
  (`retrieval.*`, `validation`) — assertions keep testing the same behaviors.
- `test_pipeline.py`: passes unchanged or near-unchanged (payload dataclass may require
  attribute access in assertions).
- Gates before push: full backend suite, ruff (PLC0415/SLF001 enforced in CI), pre-commit,
  `pnpm install` not needed (backend-only change).

## Risks

- **State-shape churn:** grouping state keys touches every graph test — mitigated by
  mechanical, reviewable updates.
- **Silent behavior drift in `validation_result` JSON:** mitigated by reusing
  `ValidationResult.to_dict()` (already the success-path serializer) and asserting shape in
  existing tests.
- **Import hoisting startup cost:** only `langgraph` is startup-sensitive; it stays lazy.
