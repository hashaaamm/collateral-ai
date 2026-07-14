# Retrieval Context Enrichment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enrich material-generation grounding with query-time neighbor chunk expansion (small-to-big) and ingestion-time per-document summaries, without changing the chunk-granular citation contract.

**Architecture:** A new `expansion.py` module stitches each retrieved seed chunk with its adjacent chunks (exact overlap removal via word offsets newly persisted in chunk metadata; paragraph-break fallback otherwise). A new `DocumentSummaryService` produces a ~150-word summary per document during ingestion (best-effort, never fatal), surfaced to the prompt as orientation-only background. Everything is env-togglable: `MATERIAL_NEIGHBOR_WINDOW=0` + `MATERIAL_INCLUDE_DOC_SUMMARIES=false` reproduces today's behavior exactly.

**Tech Stack:** Django 5 / DRF backend, pgvector, google-genai direct against Vertex (keyless ADC), LangGraph pipeline, pytest + factory-boy, LangSmith eval harness.

**Spec:** `docs/superpowers/specs/2026-07-14-retrieval-context-enrichment-design.md`

## Global Constraints

- All commands below run from `backend/` unless noted. Tests: `docker compose run --rm django pytest <path> -v`.
- **Worktree gotcha:** this repo is being worked in a git worktree; the local stack's fixed container names collide with the main checkout's. If `docker compose run` fails with a name conflict, stop the main checkout's stack first (`docker compose down` there).
- LLM calls use **google-genai direct** (`genai.Client(vertexai=True, ...)`) — never LangChain chat models (known grounding degradation, see `generation/model.py` docstring).
- Ruff gates merges. `PLC0415` (lazy imports) is pre-exempted for `collateral_ai/documents/processing/*` and `collateral_ai/materials/generation/*`. Imports are one-per-line (`isort.force-single-line`). `BLE001` needs an explicit `# noqa` where we deliberately swallow exceptions.
- Magic numbers are fine in tests (`PLR2004` exempted under `**/tests/**`).
- Commit style: conventional commits (`feat:`, `test:`, `docs:`), each task commits separately.
- No backfill of existing data (user: all companies/materials/docs will be deleted soon).
- Run `pre-commit run --all-files` from the repo root before pushing.

---

### Task 1: Persist word offsets in chunk metadata at ingestion

The chunker already computes `word_start`/`word_end` per chunk; `_build_payloads` drops them. Exact stitching (Task 2) needs them.

**Files:**
- Modify: `backend/collateral_ai/documents/processing/pipeline.py` (`_build_payloads`)
- Modify: `backend/config/settings/base.py` (bump `DOCUMENT_CHUNKING_VERSION` default)
- Test: `backend/collateral_ai/documents/tests/processing/test_pipeline.py`

**Interfaces:**
- Consumes: `ChunkingService.chunk_text()` dicts, which already contain `word_start` and `word_end` (see `documents/processing/chunking.py`).
- Produces: `DocumentChunk.metadata` for `text` and `table` chunks contains integer keys `word_start` and `word_end`. Task 2's `_same_block()` relies on exactly these key names plus the existing `chunk_index`.

- [ ] **Step 1: Write the failing test**

Add to `backend/collateral_ai/documents/tests/processing/test_pipeline.py`:

```python
def test_chunks_persist_word_offsets():
    doc = DocumentFactory(status=DocumentStatus.PROCESSING, storage_path="p/x.pdf")
    p1, p2 = _patches()
    with p1, p2:
        DocumentProcessingService().process(doc.id)
    chunk = DocumentChunk.objects.filter(document=doc, chunk_type="text").first()
    assert chunk is not None
    assert chunk.metadata["word_start"] == 0
    assert chunk.metadata["word_end"] > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose run --rm django pytest collateral_ai/documents/tests/processing/test_pipeline.py::test_chunks_persist_word_offsets -v`
Expected: FAIL with `KeyError: 'word_start'`

- [ ] **Step 3: Implement**

In `backend/collateral_ai/documents/processing/pipeline.py`, `_build_payloads`, add the two keys to both the text-block and table metadata dicts (NOT the image_caption one):

```python
                    "metadata": {
                        **base,
                        "source": "pdf_text",
                        "chunk_index": c["chunk_index"],
                        "word_start": c["word_start"],
                        "word_end": c["word_end"],
                    },
```

and for tables:

```python
                    "metadata": {
                        **base,
                        "source": "pdf_table",
                        "chunk_index": c["chunk_index"],
                        "word_start": c["word_start"],
                        "word_end": c["word_end"],
                    },
```

In `backend/config/settings/base.py`, bump the chunking version default (metadata shape changed):

```python
DOCUMENT_CHUNKING_VERSION = env("DOCUMENT_CHUNKING_VERSION", default="v2")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose run --rm django pytest collateral_ai/documents/tests/processing/ -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add backend/collateral_ai/documents/processing/pipeline.py backend/config/settings/base.py backend/collateral_ai/documents/tests/processing/test_pipeline.py
git commit -m "feat(documents): persist word offsets in chunk metadata (chunking v2)"
```

---

### Task 2: Stitching function (pure, no DB)

**Files:**
- Create: `backend/collateral_ai/materials/generation/expansion.py`
- Test: `backend/collateral_ai/materials/tests/generation/test_expansion.py`

**Interfaces:**
- Consumes: `DocumentChunk`-shaped objects with `.content`, `.chunk_type`, `.metadata` (dict, possibly missing offset keys).
- Produces: `stitch(pieces: list[DocumentChunk]) -> str` — pieces must be id-ordered chunks of ONE document + chunk_type. Also exports `TABLE_PREFIX = "Extracted table\n\n"` and `NON_EXPANDING_CHUNK_TYPES = frozenset({"image_caption"})`. Task 3's `NeighborExpander` calls `stitch()`.

- [ ] **Step 1: Write the failing tests**

Create `backend/collateral_ai/materials/tests/generation/test_expansion.py`:

```python
from __future__ import annotations

from collateral_ai.documents.models import DocumentChunk
from collateral_ai.materials.generation.expansion import TABLE_PREFIX
from collateral_ai.materials.generation.expansion import stitch


def piece(content, *, chunk_type="text", index=None, start=None, end=None):
    metadata = {}
    if index is not None:
        metadata["chunk_index"] = index
    if start is not None:
        metadata["word_start"] = start
        metadata["word_end"] = end
    return DocumentChunk(content=content, chunk_type=chunk_type, metadata=metadata)


def test_stitch_single_piece_is_identity():
    assert stitch([piece("hello world")]) == "hello world"


def test_stitch_same_block_removes_overlap_exactly():
    a = piece("w0 w1 w2 w3 w4 w5", index=0, start=0, end=6)
    b = piece("w4 w5 w6 w7 w8 w9", index=1, start=4, end=10)
    assert stitch([a, b]) == "w0 w1 w2 w3 w4 w5 w6 w7 w8 w9"


def test_stitch_three_pieces_chain():
    a = piece("w0 w1 w2 w3", index=0, start=0, end=4)
    b = piece("w2 w3 w4 w5", index=1, start=2, end=6)
    c = piece("w4 w5 w6 w7", index=2, start=4, end=8)
    assert stitch([a, b, c]) == "w0 w1 w2 w3 w4 w5 w6 w7"


def test_stitch_without_offsets_joins_with_paragraph_break():
    assert stitch([piece("one two"), piece("three four")]) == "one two\n\nthree four"


def test_stitch_across_block_boundary_joins_with_paragraph_break():
    a = piece("end of block a", index=3, start=200, end=204)
    b = piece("start of block b", index=0, start=0, end=4)
    assert stitch([a, b]) == "end of block a\n\nstart of block b"


def test_stitch_same_table_keeps_single_prefix():
    a = piece(f"{TABLE_PREFIX}r1 r2 r3 r4", chunk_type="table", index=0, start=0, end=4)
    b = piece(f"{TABLE_PREFIX}r3 r4 r5 r6", chunk_type="table", index=1, start=2, end=6)
    assert stitch([a, b]) == f"{TABLE_PREFIX}r1 r2 r3 r4 r5 r6"


def test_stitch_different_tables_keep_their_prefixes():
    a = piece(f"{TABLE_PREFIX}r1 r2", chunk_type="table", index=0, start=0, end=2)
    b = piece(f"{TABLE_PREFIX}q1 q2", chunk_type="table", index=0, start=0, end=2)
    assert stitch([a, b]) == f"{TABLE_PREFIX}r1 r2\n\n{TABLE_PREFIX}q1 q2"
```

(No `django_db` marker — unsaved model instances only.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose run --rm django pytest collateral_ai/materials/tests/generation/test_expansion.py -v`
Expected: FAIL with `ModuleNotFoundError: ... expansion`

- [ ] **Step 3: Implement**

Create `backend/collateral_ai/materials/generation/expansion.py`:

```python
"""Small-to-big neighbor expansion for retrieved chunks (spec §3).

Adjacent chunks from the same chunking block are stitched exactly — the
50-word overlap appears once — using the word offsets persisted in chunk
metadata. Everything else (block/page boundaries, legacy chunks without
offsets, distinct tables) is joined with a paragraph break.
"""

from __future__ import annotations

from collateral_ai.documents.models import DocumentChunk

TABLE_PREFIX = "Extracted table\n\n"
NON_EXPANDING_CHUNK_TYPES = frozenset({"image_caption"})
_OFFSET_KEYS = ("chunk_index", "word_start", "word_end")


def _has_offsets(meta: dict) -> bool:
    return all(isinstance(meta.get(key), int) for key in _OFFSET_KEYS)


def _same_block(prev_meta: dict, meta: dict) -> bool:
    """Contiguous chunks of one chunking block: index +1, overlapping word ranges."""
    if not (_has_offsets(prev_meta) and _has_offsets(meta)):
        return False
    return (
        meta["chunk_index"] == prev_meta["chunk_index"] + 1
        and prev_meta["word_start"] <= meta["word_start"] <= prev_meta["word_end"]
    )


def stitch(pieces: list[DocumentChunk]) -> str:
    """Join id-ordered chunks of one document + chunk_type into a passage."""
    is_table = pieces[0].chunk_type == "table"
    segments: list[list[str]] = []
    current: list[str] = []
    prev_meta: dict = {}
    for piece in pieces:
        body = piece.content.removeprefix(TABLE_PREFIX) if is_table else piece.content
        words = body.split()
        meta = piece.metadata or {}
        overlap = (
            prev_meta["word_end"] - meta["word_start"]
            if current and _same_block(prev_meta, meta)
            else None
        )
        if overlap is not None and overlap <= len(words):
            current.extend(words[overlap:])
        else:
            if current:
                segments.append(current)
            current = words
        prev_meta = meta
    segments.append(current)
    prefix = TABLE_PREFIX if is_table else ""
    return "\n\n".join(prefix + " ".join(segment) for segment in segments)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose run --rm django pytest collateral_ai/materials/tests/generation/test_expansion.py -v`
Expected: 7 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/collateral_ai/materials/generation/expansion.py backend/collateral_ai/materials/tests/generation/test_expansion.py
git commit -m "feat(materials): exact chunk stitching for neighbor expansion"
```

---

### Task 3: NeighborExpander (DB neighbor selection + dedupe)

**Files:**
- Modify: `backend/collateral_ai/materials/generation/expansion.py`
- Test: `backend/collateral_ai/materials/tests/generation/test_expansion.py`

**Interfaces:**
- Consumes: `stitch()` from Task 2; saved `DocumentChunk` rows.
- Produces: `NeighborExpander(window: int).expand(seeds: list[DocumentChunk]) -> dict[int, str]` mapping seed pk → expanded passage. Seeds MUST be rank-ordered (best first). Seeds with no fresh neighbors are omitted from the dict. Task 4 calls this from `RetrievalService`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/collateral_ai/materials/tests/generation/test_expansion.py`:

```python
import pytest

from collateral_ai.documents.tests.factories import DocumentChunkFactory
from collateral_ai.documents.tests.factories import DocumentFactory
from collateral_ai.materials.generation.expansion import NeighborExpander


def _doc_with_chunks(n):
    doc = DocumentFactory()
    return doc, [DocumentChunkFactory(document=doc, content=f"c{i}") for i in range(n)]


@pytest.mark.django_db
def test_expand_window_zero_returns_empty():
    _, chunks = _doc_with_chunks(3)
    assert NeighborExpander(window=0).expand([chunks[1]]) == {}


@pytest.mark.django_db
def test_expand_attaches_adjacent_chunks():
    _, c = _doc_with_chunks(3)
    # Factory chunks carry no word offsets -> paragraph-break joins.
    assert NeighborExpander(window=1).expand([c[1]]) == {c[1].pk: "c0\n\nc1\n\nc2"}


@pytest.mark.django_db
def test_expand_skips_neighbors_that_are_seeds():
    _, c = _doc_with_chunks(4)
    result = NeighborExpander(window=1).expand([c[1], c[2]])
    assert result == {c[1].pk: "c0\n\nc1", c[2].pk: "c2\n\nc3"}


@pytest.mark.django_db
def test_expand_shared_neighbor_goes_to_higher_ranked_seed():
    _, c = _doc_with_chunks(5)
    result = NeighborExpander(window=1).expand([c[1], c[3]])
    assert result == {c[1].pk: "c0\n\nc1\n\nc2", c[3].pk: "c3\n\nc4"}


@pytest.mark.django_db
def test_expand_never_crosses_documents_or_chunk_types():
    doc_a, a = _doc_with_chunks(1)
    DocumentChunkFactory(document=doc_a, content="tbl", chunk_type="table")
    _, b = _doc_with_chunks(1)
    assert NeighborExpander(window=2).expand([a[0], b[0]]) == {}


@pytest.mark.django_db
def test_expand_ignores_image_captions():
    doc = DocumentFactory()
    caps = [
        DocumentChunkFactory(document=doc, chunk_type="image_caption", content=f"cap{i}")
        for i in range(3)
    ]
    assert NeighborExpander(window=1).expand([caps[1]]) == {}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose run --rm django pytest collateral_ai/materials/tests/generation/test_expansion.py -v`
Expected: new tests FAIL with `ImportError: cannot import name 'NeighborExpander'`; the 7 stitch tests still PASS

- [ ] **Step 3: Implement**

Append to `backend/collateral_ai/materials/generation/expansion.py`:

```python
class NeighborExpander:
    """Assigns each rank-ordered seed its unclaimed ±window neighbors, stitched."""

    def __init__(self, *, window: int) -> None:
        self.window = window

    def expand(self, seeds: list[DocumentChunk]) -> dict[int, str]:
        """Map seed chunk id -> expanded passage; seeds must be rank-ordered.

        Seeds with no fresh neighbors are omitted (their content stands alone).
        """
        if self.window <= 0 or not seeds:
            return {}
        ordered = self._ordered_ids(seeds)
        claimed = {seed.pk for seed in seeds}
        assignment: dict[int, list[int]] = {}
        for seed in seeds:
            key = (seed.document_id, seed.chunk_type)
            if key not in ordered:
                continue
            ids = ordered[key]
            pos = ids.index(seed.pk)
            lo = max(0, pos - self.window)
            wanted = ids[lo:pos] + ids[pos + 1 : pos + 1 + self.window]
            fresh = [pk for pk in wanted if pk not in claimed]
            if fresh:
                claimed.update(fresh)
                assignment[seed.pk] = fresh
        if not assignment:
            return {}
        neighbor_ids = [pk for pks in assignment.values() for pk in pks]
        neighbors = DocumentChunk.objects.in_bulk(neighbor_ids)
        return {
            seed.pk: stitch(
                sorted(
                    [seed, *(neighbors[pk] for pk in assignment[seed.pk])],
                    key=lambda chunk: chunk.pk,
                ),
            )
            for seed in seeds
            if seed.pk in assignment
        }

    def _ordered_ids(self, seeds: list[DocumentChunk]) -> dict[tuple[int, str], list[int]]:
        keys = {
            (seed.document_id, seed.chunk_type)
            for seed in seeds
            if seed.chunk_type not in NON_EXPANDING_CHUNK_TYPES
        }
        if not keys:
            return {}
        rows = (
            DocumentChunk.objects.filter(
                document_id__in={doc_id for doc_id, _ in keys},
            )
            .order_by("pk")
            .values_list("document_id", "chunk_type", "pk")
        )
        ordered: dict[tuple[int, str], list[int]] = {}
        for doc_id, chunk_type, pk in rows:
            if (doc_id, chunk_type) in keys:
                ordered.setdefault((doc_id, chunk_type), []).append(pk)
        return ordered
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose run --rm django pytest collateral_ai/materials/tests/generation/test_expansion.py -v`
Expected: 13 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/collateral_ai/materials/generation/expansion.py backend/collateral_ai/materials/tests/generation/test_expansion.py
git commit -m "feat(materials): neighbor selection and dedupe for chunk expansion"
```

---

### Task 4: Wire expansion into RetrievalService

**Files:**
- Modify: `backend/collateral_ai/materials/generation/retrieval.py`
- Modify: `backend/config/settings/base.py`
- Test: `backend/collateral_ai/materials/tests/generation/test_retrieval.py`

**Interfaces:**
- Consumes: `NeighborExpander` (Task 3), new setting `MATERIAL_NEIGHBOR_WINDOW`.
- Produces: `RetrievedChunk` gains field `expanded_content: str = ""`; `to_prompt_dict()["content"]` now returns `expanded_content or content`. `RetrievedChunk.content` stays the bare seed chunk (used for `GenerationSource.snippet` — no change needed there). `retrieve()` signature unchanged.

- [ ] **Step 1: Write the failing tests**

Append to `backend/collateral_ai/materials/tests/generation/test_retrieval.py`:

```python
def test_retrieve_expands_seed_with_neighbors(settings):
    settings.MATERIAL_NEIGHBOR_WINDOW = 1
    company = CompanyFactory()
    doc = DocumentFactory(company=company)
    DocumentChunkFactory(document=doc, content="before", embedding=embedding(-1.0))
    DocumentChunkFactory(document=doc, content="seed", embedding=embedding(1.0))
    DocumentChunkFactory(document=doc, content="after", embedding=embedding(-1.0))
    results = RetrievalService().retrieve(
        company_id=company.pk,
        query_embedding=embedding(1.0),
        source_role=SourceRole.SENDER,
        source_prefix="SENDER_SOURCE",
        top_k=1,
    )
    assert len(results) == 1
    assert results[0].content == "seed"
    assert results[0].expanded_content == "before\n\nseed\n\nafter"
    assert results[0].to_prompt_dict()["content"] == "before\n\nseed\n\nafter"


def test_retrieve_window_zero_keeps_bare_chunks(settings):
    settings.MATERIAL_NEIGHBOR_WINDOW = 0
    company = CompanyFactory()
    doc = DocumentFactory(company=company)
    DocumentChunkFactory(document=doc, content="before", embedding=embedding(-1.0))
    DocumentChunkFactory(document=doc, content="seed", embedding=embedding(1.0))
    results = RetrievalService().retrieve(
        company_id=company.pk,
        query_embedding=embedding(1.0),
        source_role=SourceRole.SENDER,
        source_prefix="SENDER_SOURCE",
        top_k=1,
    )
    assert results[0].expanded_content == "seed"
    assert results[0].to_prompt_dict()["content"] == "seed"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose run --rm django pytest collateral_ai/materials/tests/generation/test_retrieval.py -v`
Expected: the two new tests FAIL (`AttributeError` on `MATERIAL_NEIGHBOR_WINDOW` / `expanded_content`); existing tests PASS

- [ ] **Step 3: Implement**

In `backend/config/settings/base.py`, after `MATERIAL_RETRIEVAL_TOP_K`:

```python
MATERIAL_NEIGHBOR_WINDOW = env.int("MATERIAL_NEIGHBOR_WINDOW", default=1)
```

In `backend/collateral_ai/materials/generation/retrieval.py`:

Add imports (one per line, matching isort style):

```python
from django.conf import settings

from collateral_ai.materials.generation.expansion import NeighborExpander
```

Extend the dataclass (new field LAST, with a default, so positional construction elsewhere is unaffected) and change `to_prompt_dict`:

```python
@dataclass(frozen=True)
class RetrievedChunk:
    source_id: str
    chunk_id: int
    document_id: int
    company_id: int
    file_name: str
    page_number: int
    chunk_type: str
    content: str
    relevance_score: float
    source_role: str
    expanded_content: str = ""

    def to_prompt_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "file_name": self.file_name,
            "page_number": self.page_number,
            "chunk_type": self.chunk_type,
            "content": self.expanded_content or self.content,
        }
```

Rework `RetrievalService`:

```python
class RetrievalService:
    def __init__(self) -> None:
        self.neighbor_window = int(settings.MATERIAL_NEIGHBOR_WINDOW)

    def retrieve(
        self,
        *,
        company_id: int,
        query_embedding: list[float],
        source_role: str,
        source_prefix: str,
        top_k: int,
    ) -> list[RetrievedChunk]:
        # `embedding` is non-nullable — every persisted chunk has one (spec §6.3).
        chunks = list(
            DocumentChunk.objects.filter(company_id=company_id)
            .select_related("document")
            .annotate(distance=CosineDistance("embedding", query_embedding))
            .order_by("distance")[:top_k],
        )
        expanded = NeighborExpander(window=self.neighbor_window).expand(chunks)
        return [
            RetrievedChunk(
                source_id=f"{source_prefix}_{index}",
                chunk_id=chunk.pk,
                document_id=chunk.document_id,
                company_id=chunk.company_id,
                file_name=chunk.document.file_name,
                page_number=chunk.page_number,
                chunk_type=chunk.chunk_type,
                content=chunk.content,
                relevance_score=float(chunk.distance),
                source_role=source_role,
                expanded_content=expanded.get(chunk.pk, chunk.content),
            )
            for index, chunk in enumerate(chunks, start=1)
        ]
```

- [ ] **Step 4: Run the materials + documents suites**

Run: `docker compose run --rm django pytest collateral_ai/materials/ collateral_ai/documents/ -v`
Expected: ALL PASS (existing retrieval/service/graph tests must not regress)

- [ ] **Step 5: Commit**

```bash
git add backend/collateral_ai/materials/generation/retrieval.py backend/config/settings/base.py backend/collateral_ai/materials/tests/generation/test_retrieval.py
git commit -m "feat(materials): neighbor-expanded retrieval context (MATERIAL_NEIGHBOR_WINDOW)"
```

---

### Task 5: Document.summary field + DocumentSummaryService

**Files:**
- Modify: `backend/collateral_ai/documents/models.py`
- Create: `backend/collateral_ai/documents/migrations/0003_document_summary.py` (via makemigrations)
- Create: `backend/collateral_ai/documents/processing/summarization.py`
- Modify: `backend/config/settings/base.py`
- Test: `backend/collateral_ai/documents/tests/processing/test_summarization.py`

**Interfaces:**
- Consumes: settings `DOCUMENT_SUMMARY_MODEL`, `DOCUMENT_SUMMARY_INPUT_MAX_WORDS`, `DOCUMENT_SUMMARY_MAX_WORDS`; google-genai client pattern from `documents/processing/embeddings.py`.
- Produces: `Document.summary: TextField(blank=True, default="")`. `DocumentSummaryService().summarize(texts: list[str]) -> str` — returns `""` for empty input (no LLM call) and the stripped response text otherwise; raises on API errors (caller handles). Tasks 6–8 rely on `Document.summary`.

- [ ] **Step 1: Add the model field and migration**

In `backend/collateral_ai/documents/models.py`, after `error_message`:

```python
    summary = models.TextField(blank=True, default="")
```

Run: `docker compose run --rm django python manage.py makemigrations documents --name document_summary`
Expected: creates `backend/collateral_ai/documents/migrations/0003_document_summary.py` adding the field.

- [ ] **Step 2: Add settings**

In `backend/config/settings/base.py`, after `DOCUMENT_CHUNKING_VERSION`:

```python
DOCUMENT_SUMMARY_MODEL = env("DOCUMENT_SUMMARY_MODEL", default="gemini-2.5-flash")
DOCUMENT_SUMMARY_INPUT_MAX_WORDS = env.int("DOCUMENT_SUMMARY_INPUT_MAX_WORDS", default=20000)
DOCUMENT_SUMMARY_MAX_WORDS = env.int("DOCUMENT_SUMMARY_MAX_WORDS", default=150)
```

- [ ] **Step 3: Write the failing tests**

Create `backend/collateral_ai/documents/tests/processing/test_summarization.py`:

```python
from __future__ import annotations

from unittest import mock

from collateral_ai.documents.processing.summarization import DocumentSummaryService


def _client_returning(text):
    client = mock.MagicMock()
    client.models.generate_content.return_value = mock.MagicMock(text=text)
    return client


def test_summarize_returns_stripped_text():
    with mock.patch.object(
        DocumentSummaryService,
        "_client",
        return_value=_client_returning("  A summary.  "),
    ):
        assert DocumentSummaryService().summarize(["chunk one", "chunk two"]) == "A summary."


def test_summarize_empty_input_skips_llm_call():
    with mock.patch.object(DocumentSummaryService, "_client") as client:
        assert DocumentSummaryService().summarize(["", "   "]) == ""
    client.assert_not_called()


def test_summarize_clips_input_to_max_words(settings):
    settings.DOCUMENT_SUMMARY_INPUT_MAX_WORDS = 3
    client = _client_returning("s")
    with mock.patch.object(DocumentSummaryService, "_client", return_value=client):
        DocumentSummaryService().summarize(["w0 w1", "w2 w3 w4"])
    assert client.models.generate_content.call_args.kwargs["contents"] == "w0 w1 w2"


def test_summarize_empty_response_returns_empty():
    with mock.patch.object(
        DocumentSummaryService,
        "_client",
        return_value=_client_returning(None),
    ):
        assert DocumentSummaryService().summarize(["text"]) == ""
```

Run: `docker compose run --rm django pytest collateral_ai/documents/tests/processing/test_summarization.py -v`
Expected: FAIL with `ModuleNotFoundError: ... summarization`

- [ ] **Step 4: Implement**

Create `backend/collateral_ai/documents/processing/summarization.py`:

```python
"""Per-document summary for generation grounding (google-genai, keyless ADC).

Summaries are orientation-only background for material generation (spec §5.2);
they are best-effort and must never block ingestion — the pipeline catches
failures and stores a blank summary.
"""

from __future__ import annotations

from django.conf import settings

SUMMARY_SYSTEM_INSTRUCTION = (
    "You summarize business documents for a B2B marketing content system. "
    "Write a factual plain-prose summary of at most {max_words} words. "
    "Capture: what the company and product are, key capabilities, positioning, "
    "concrete metrics and proof points, target industries, and the pain points "
    "addressed. No markdown, no bullet points, no hype."
)


class DocumentSummaryService:
    def __init__(self) -> None:
        self.model = settings.DOCUMENT_SUMMARY_MODEL
        self.input_max_words = int(settings.DOCUMENT_SUMMARY_INPUT_MAX_WORDS)
        self.max_words = int(settings.DOCUMENT_SUMMARY_MAX_WORDS)

    def _client(self):
        from google import genai

        return genai.Client(
            vertexai=True,
            project=settings.GOOGLE_CLOUD_PROJECT,
            location=settings.VERTEX_LOCATION,
        )

    def summarize(self, texts: list[str]) -> str:
        words = " ".join(text for text in texts if text).split()
        if not words:
            return ""
        from google.genai import types

        response = self._client().models.generate_content(
            model=self.model,
            contents=" ".join(words[: self.input_max_words]),
            config=types.GenerateContentConfig(
                system_instruction=SUMMARY_SYSTEM_INSTRUCTION.format(
                    max_words=self.max_words,
                ),
                temperature=0.1,
                max_output_tokens=1024,
                # Thinking disabled: short factual summary, spend tokens on output.
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        return (getattr(response, "text", None) or "").strip()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `docker compose run --rm django pytest collateral_ai/documents/ -v`
Expected: ALL PASS (including migration application)

- [ ] **Step 6: Commit**

```bash
git add backend/collateral_ai/documents/models.py backend/collateral_ai/documents/migrations/0003_document_summary.py backend/collateral_ai/documents/processing/summarization.py backend/config/settings/base.py backend/collateral_ai/documents/tests/processing/test_summarization.py
git commit -m "feat(documents): Document.summary field and summarization service"
```

---

### Task 6: Summary step in the ingestion pipeline

**Files:**
- Modify: `backend/collateral_ai/documents/processing/pipeline.py`
- Test: `backend/collateral_ai/documents/tests/processing/test_pipeline.py`

**Interfaces:**
- Consumes: `DocumentSummaryService.summarize()` (Task 5).
- Produces: processed documents carry `summary` (blank on summarizer failure). Order: extract → chunk → embed → save chunks → summarize → mark PROCESSED.

- [ ] **Step 1: Update the shared patch helper and write failing tests**

In `backend/collateral_ai/documents/tests/processing/test_pipeline.py`, extend `_patches` to also stub the summarizer (existing pipeline tests must not hit the real client):

```python
def _patches(pdf=b"", embeddings=None, summary="Doc summary."):
    return (
        mock.patch(
            "collateral_ai.documents.processing.pipeline.StorageService.download",
            return_value=pdf or make_pdf("Alpha beta gamma delta."),
        ),
        mock.patch(
            "collateral_ai.documents.processing.embeddings.EmbeddingService.embed_documents",
            side_effect=lambda texts: [[0.1] * 768 for _ in texts],
        ),
        mock.patch(
            "collateral_ai.documents.processing.pipeline.DocumentSummaryService.summarize",
            return_value=summary,
        ),
    )
```

Update every existing `p1, p2 = _patches()` / `with p1, p2:` usage to `p1, p2, p3 = _patches()` / `with p1, p2, p3:` (three call sites: `test_process_creates_chunks_and_marks_processed`, `test_reprocess_replaces_chunks`, `test_chunks_persist_word_offsets`).

Add:

```python
def test_process_stores_document_summary():
    doc = DocumentFactory(status=DocumentStatus.PROCESSING, storage_path="p/x.pdf")
    p1, p2, p3 = _patches()
    with p1, p2, p3:
        DocumentProcessingService().process(doc.id)
    doc.refresh_from_db()
    assert doc.status == DocumentStatus.PROCESSED
    assert doc.summary == "Doc summary."


def test_summary_failure_does_not_fail_processing():
    doc = DocumentFactory(status=DocumentStatus.PROCESSING, storage_path="p/x.pdf")
    p1, p2, _ = _patches()
    fail = mock.patch(
        "collateral_ai.documents.processing.pipeline.DocumentSummaryService.summarize",
        side_effect=RuntimeError("llm down"),
    )
    with p1, p2, fail:
        DocumentProcessingService().process(doc.id)
    doc.refresh_from_db()
    assert doc.status == DocumentStatus.PROCESSED
    assert doc.summary == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose run --rm django pytest collateral_ai/documents/tests/processing/test_pipeline.py -v`
Expected: every test using `_patches` ERRORS with `AttributeError: <module ...pipeline> does not have the attribute 'DocumentSummaryService'` — the patch target only exists once Step 3's import lands. That is the expected red state for this task.

- [ ] **Step 3: Implement**

In `backend/collateral_ai/documents/processing/pipeline.py`:

Add the import (with the other processing imports):

```python
from collateral_ai.documents.processing.summarization import DocumentSummaryService
```

In `__init__`:

```python
        self.summarizer = DocumentSummaryService()
```

In `process()`, after the `self._save_chunks(...)` timing block and before the PROCESSED update:

```python
            t = time.monotonic()
            summary = self._summarize(payloads)
            logger.info("timing: summary %.2fs", time.monotonic() - t)
```

Add `summary=summary,` to the `Document.objects.filter(id=document.id).update(status=DocumentStatus.PROCESSED, ...)` call.

Add the method:

```python
    def _summarize(self, payloads: list[dict[str, Any]]) -> str:
        """Best-effort: a missing summary must never fail ingestion (spec §5.2)."""
        try:
            return self.summarizer.summarize([p["content"] for p in payloads])
        except Exception:  # noqa: BLE001 — any summarizer error degrades to no summary
            logger.warning("summary generation failed; continuing without one")
            return ""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose run --rm django pytest collateral_ai/documents/ -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add backend/collateral_ai/documents/processing/pipeline.py backend/collateral_ai/documents/tests/processing/test_pipeline.py
git commit -m "feat(documents): generate document summary during ingestion (non-fatal)"
```

---

### Task 7: Summary fetch helper + prompt payload + system instruction

**Files:**
- Modify: `backend/collateral_ai/materials/generation/retrieval.py`
- Modify: `backend/collateral_ai/materials/generation/prompts.py`
- Test: `backend/collateral_ai/materials/tests/generation/test_retrieval.py`
- Create: `backend/collateral_ai/materials/tests/generation/test_prompts.py`

**Interfaces:**
- Consumes: `Document.summary` (Task 5); `RetrievedChunk.document_id`.
- Produces: `fetch_document_summaries(chunks) -> list[dict[str, str]]` in `retrieval.py` — distinct contributing documents in rank order, `{"file_name": ..., "summary": ...}`, blank summaries omitted. `build_generation_payload` gains keyword args `sender_document_summaries` / `receiver_document_summaries` (both `list[dict] | None`, default `None`); payload keys of the same names appear only when non-empty. Task 8 wires both into the graph.

- [ ] **Step 1: Write the failing tests**

Append to `backend/collateral_ai/materials/tests/generation/test_retrieval.py` (add `from collateral_ai.materials.generation.retrieval import RetrievedChunk` and `... import fetch_document_summaries` to the imports):

```python
def _retrieved(document_id):
    return RetrievedChunk(
        source_id="SENDER_SOURCE_1",
        chunk_id=1,
        document_id=document_id,
        company_id=1,
        file_name="f.pdf",
        page_number=1,
        chunk_type="text",
        content="c",
        relevance_score=0.1,
        source_role=SourceRole.SENDER,
    )


def test_fetch_document_summaries_distinct_nonblank_only():
    with_summary = DocumentFactory(file_name="a.pdf", summary="About A.")
    blank = DocumentFactory(file_name="b.pdf")
    chunks = [_retrieved(with_summary.pk), _retrieved(blank.pk), _retrieved(with_summary.pk)]
    assert fetch_document_summaries(chunks) == [
        {"file_name": "a.pdf", "summary": "About A."},
    ]


def test_fetch_document_summaries_preserves_rank_order():
    first = DocumentFactory(file_name="first.pdf", summary="S1")
    second = DocumentFactory(file_name="second.pdf", summary="S2")
    chunks = [_retrieved(second.pk), _retrieved(first.pk)]
    names = [d["file_name"] for d in fetch_document_summaries(chunks)]
    assert names == ["second.pdf", "first.pdf"]
```

Create `backend/collateral_ai/materials/tests/generation/test_prompts.py`:

```python
from __future__ import annotations

import json
from unittest.mock import MagicMock

from collateral_ai.materials.generation.prompts import SYSTEM_INSTRUCTION
from collateral_ai.materials.generation.prompts import build_generation_payload


def _material():
    material = MagicMock()
    material.prompt = "Introduce our product."
    material.tone = "professional"
    material.cta_style = "direct"
    material.language = "en"
    for attr, name in (
        ("sender_company", "Sender Co"),
        ("receiver_company", "Receiver Co"),
    ):
        company = MagicMock()
        company.pk = 1
        company.name = name
        company.industry = "software"
        company.description = "A company."
        setattr(material, attr, company)
    material.template.name = "Newsletter"
    material.template.constraints = {"headline_max_words": 10}
    return material


def test_payload_includes_document_summaries():
    payload = json.loads(
        build_generation_payload(
            material=_material(),
            sender_chunks=[],
            receiver_chunks=[],
            sender_document_summaries=[{"file_name": "a.pdf", "summary": "About A."}],
            receiver_document_summaries=[{"file_name": "b.pdf", "summary": "About B."}],
        ),
    )
    assert payload["sender_document_summaries"] == [
        {"file_name": "a.pdf", "summary": "About A."},
    ]
    assert payload["receiver_document_summaries"] == [
        {"file_name": "b.pdf", "summary": "About B."},
    ]


def test_payload_omits_empty_summaries():
    payload = json.loads(
        build_generation_payload(
            material=_material(),
            sender_chunks=[],
            receiver_chunks=[],
        ),
    )
    assert "sender_document_summaries" not in payload
    assert "receiver_document_summaries" not in payload


def test_system_instruction_marks_summaries_uncitable():
    assert "sender_document_summaries" in SYSTEM_INSTRUCTION
    assert "orientation-only" in SYSTEM_INSTRUCTION
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose run --rm django pytest collateral_ai/materials/tests/generation/test_retrieval.py collateral_ai/materials/tests/generation/test_prompts.py -v`
Expected: FAIL (`ImportError: fetch_document_summaries`; `TypeError: unexpected keyword argument`; instruction assert fails)

- [ ] **Step 3: Implement**

In `backend/collateral_ai/materials/generation/retrieval.py`, add the import `from collateral_ai.documents.models import Document` and the function:

```python
def fetch_document_summaries(chunks: list[RetrievedChunk]) -> list[dict[str, str]]:
    """Distinct contributing documents (rank order) with a non-blank summary."""
    doc_ids: list[int] = []
    for chunk in chunks:
        if chunk.document_id not in doc_ids:
            doc_ids.append(chunk.document_id)
    documents = Document.objects.in_bulk(doc_ids)
    return [
        {"file_name": doc.file_name, "summary": doc.summary}
        for doc_id in doc_ids
        if (doc := documents.get(doc_id)) and doc.summary
    ]
```

In `backend/collateral_ai/materials/generation/prompts.py`:

Add to `SYSTEM_INSTRUCTION`, directly after the "Use ONLY the provided sender_context..." rule:

```python
- sender_document_summaries / receiver_document_summaries (when present) are \
orientation-only background about whole source documents. They carry no \
source_id and must NEVER be cited — every claim must still trace to a cited \
source_id from sender_context or receiver_context.
```

Extend `build_generation_payload`:

```python
def build_generation_payload(
    *,
    material: MarketingMaterial,
    sender_chunks: list[RetrievedChunk],
    receiver_chunks: list[RetrievedChunk],
    sender_document_summaries: list[dict] | None = None,
    receiver_document_summaries: list[dict] | None = None,
) -> str:
```

and before `return json.dumps(payload, indent=2)`:

```python
    if sender_document_summaries:
        payload["sender_document_summaries"] = sender_document_summaries
    if receiver_document_summaries:
        payload["receiver_document_summaries"] = receiver_document_summaries
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose run --rm django pytest collateral_ai/materials/ -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add backend/collateral_ai/materials/generation/retrieval.py backend/collateral_ai/materials/generation/prompts.py backend/collateral_ai/materials/tests/generation/test_retrieval.py backend/collateral_ai/materials/tests/generation/test_prompts.py
git commit -m "feat(materials): document summaries in generation payload (orientation-only)"
```

---

### Task 8: Graph wiring + include-summaries toggle

**Files:**
- Modify: `backend/collateral_ai/materials/generation/graph.py`
- Modify: `backend/config/settings/base.py`
- Modify: `docs/superpowers/specs/2026-07-14-retrieval-context-enrichment-design.md` (config table row)
- Test: `backend/collateral_ai/materials/tests/generation/test_graph.py`

**Interfaces:**
- Consumes: `fetch_document_summaries` (Task 7); new setting `MATERIAL_INCLUDE_DOC_SUMMARIES` (bool, default True).
- Produces: `GenerationState` keys `sender_document_summaries` / `receiver_document_summaries` (`list[dict]`); both also appear in `context_snapshot` (hence in the persisted `retrieved_context`). The generate node forwards them to `build_generation_payload`. The repair node is unchanged.

- [ ] **Step 1: Write the failing tests**

Append to `backend/collateral_ai/materials/tests/generation/test_graph.py` (add `import json` and `from collateral_ai.documents.tests.factories import DocumentFactory` to the imports):

```python
def _graph(embedder, retriever, model, validator):
    return build_generation_graph(
        embedder=embedder,
        retriever=retriever,
        model=model,
        validator=validator,
        max_repair_attempts=2,
    )


@pytest.mark.django_db
def test_graph_passes_document_summaries_to_generation():
    doc = DocumentFactory(file_name="sender.pdf", summary="Sender doc summary.")
    tmpl = _template()
    material = _material(tmpl)
    model = MagicMock()
    model.generate_structured.return_value = _valid_output()
    embedder, retriever, validator = _services(model)
    retriever.retrieve.side_effect = lambda **kw: (
        [FakeChunk(source_id="SENDER_SOURCE_1", document_id=doc.pk)]
        if kw["source_role"] == "sender"
        else [
            FakeChunk(
                source_id="RECEIVER_SOURCE_1",
                source_role="receiver",
                document_id=doc.pk,
            ),
        ]
    )
    final = _graph(embedder, retriever, model, validator).invoke(
        _initial_state(tmpl, material),
    )
    payload = json.loads(
        model.generate_structured.call_args_list[0].kwargs["user_input"],
    )
    expected = [{"file_name": "sender.pdf", "summary": "Sender doc summary."}]
    assert payload["sender_document_summaries"] == expected
    assert final["context_snapshot"]["sender_document_summaries"] == expected


@pytest.mark.django_db
def test_graph_summaries_disabled_by_setting(settings):
    settings.MATERIAL_INCLUDE_DOC_SUMMARIES = False
    doc = DocumentFactory(file_name="sender.pdf", summary="Sender doc summary.")
    tmpl = _template()
    material = _material(tmpl)
    model = MagicMock()
    model.generate_structured.return_value = _valid_output()
    embedder, retriever, validator = _services(model)
    retriever.retrieve.side_effect = lambda **kw: (
        [FakeChunk(source_id="SENDER_SOURCE_1", document_id=doc.pk)]
        if kw["source_role"] == "sender"
        else [
            FakeChunk(
                source_id="RECEIVER_SOURCE_1",
                source_role="receiver",
                document_id=doc.pk,
            ),
        ]
    )
    _graph(embedder, retriever, model, validator).invoke(
        _initial_state(tmpl, material),
    )
    payload = json.loads(
        model.generate_structured.call_args_list[0].kwargs["user_input"],
    )
    assert "sender_document_summaries" not in payload
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose run --rm django pytest collateral_ai/materials/tests/generation/test_graph.py -v`
Expected: two new tests FAIL (`KeyError: 'sender_document_summaries'` / missing setting); existing five graph tests PASS

- [ ] **Step 3: Implement**

In `backend/config/settings/base.py`, after `MATERIAL_NEIGHBOR_WINDOW`:

```python
MATERIAL_INCLUDE_DOC_SUMMARIES = env.bool("MATERIAL_INCLUDE_DOC_SUMMARIES", default=True)
```

In `backend/collateral_ai/materials/generation/graph.py`:

Add imports:

```python
from django.conf import settings

from collateral_ai.materials.generation.retrieval import fetch_document_summaries
```

Add to `GenerationState`:

```python
    sender_document_summaries: list[dict]
    receiver_document_summaries: list[dict]
```

In the `retrieve` node, after the empty-chunks check and before `source_map = ...`:

```python
        include_summaries = bool(settings.MATERIAL_INCLUDE_DOC_SUMMARIES)
        sender_summaries = (
            fetch_document_summaries(sender_chunks) if include_summaries else []
        )
        receiver_summaries = (
            fetch_document_summaries(receiver_chunks) if include_summaries else []
        )
```

Extend `context_snapshot` and the node's return dict:

```python
        context_snapshot = {
            "sender_context": [c.to_prompt_dict() for c in sender_chunks],
            "receiver_context": [c.to_prompt_dict() for c in receiver_chunks],
            "sender_document_summaries": sender_summaries,
            "receiver_document_summaries": receiver_summaries,
        }
        return {
            "query_embedding": query_embedding,
            "sender_chunks": sender_chunks,
            "receiver_chunks": receiver_chunks,
            "sender_document_summaries": sender_summaries,
            "receiver_document_summaries": receiver_summaries,
            "source_map": source_map,
            "allowed_ids": allowed_ids,
            "response_schema": response_schema,
            "context_snapshot": context_snapshot,
        }
```

In the `generate` node:

```python
            user_input=build_generation_payload(
                material=state["material"],
                sender_chunks=state["sender_chunks"],
                receiver_chunks=state["receiver_chunks"],
                sender_document_summaries=state.get("sender_document_summaries", []),
                receiver_document_summaries=state.get("receiver_document_summaries", []),
            ),
```

In the spec's §7 config table (`docs/superpowers/specs/2026-07-14-retrieval-context-enrichment-design.md`), add:

```markdown
| `MATERIAL_INCLUDE_DOC_SUMMARIES` | `true` | include document summaries in the payload; `false` for eval A/B and rollback |
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose run --rm django pytest collateral_ai/materials/ -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add backend/collateral_ai/materials/generation/graph.py backend/config/settings/base.py backend/collateral_ai/materials/tests/generation/test_graph.py docs/superpowers/specs/2026-07-14-retrieval-context-enrichment-design.md
git commit -m "feat(materials): wire summaries through generation graph with toggle"
```

---

### Task 9: Eval seeder — grouped documents + summaries

Today each golden chunk lives in its own document, so expansion finds no neighbors and summaries are blank — the eval couldn't measure the enrichment. Group each company's facts into ONE document and give it a summary.

**Files:**
- Modify: `backend/collateral_ai/materials/generation/eval/seed.py`
- Test: `backend/collateral_ai/materials/tests/generation/test_seed.py`

**Interfaces:**
- Consumes: `DocumentFactory` (supports `summary=` since Task 5).
- Produces: golden materials whose sender/receiver each have one document holding all fact chunks (adjacent ids → expansion fires) and a non-blank `Document.summary` (summaries fire). Sparse adversarial case unchanged (single chunk, no summary).

- [ ] **Step 1: Write the failing test**

Append to `backend/collateral_ai/materials/tests/generation/test_seed.py`:

```python
@pytest.mark.django_db
def test_build_golden_materials_groups_chunks_and_sets_summaries():
    seed.build_golden_materials(embedder=_FakeEmbedder())
    material = MarketingMaterial.objects.exclude(title__icontains="sparse").first()
    chunks = DocumentChunk.objects.filter(company=material.sender_company)
    assert chunks.count() >= 3
    assert len({c.document_id for c in chunks}) == 1
    assert chunks.first().document.summary != ""
```

Run: `docker compose run --rm django pytest collateral_ai/materials/tests/generation/test_seed.py -v`
Expected: new test FAILS on `len({c.document_id ...}) == 1` (each chunk currently gets its own document)

- [ ] **Step 2: Implement**

In `backend/collateral_ai/materials/generation/eval/seed.py`:

Add the import:

```python
from collateral_ai.documents.tests.factories import DocumentFactory
```

Add a summary per company to `_PAIRS` (two new keys per pair):

```python
_PAIRS = [
    {
        "sender": "Sentinel Pay",
        "receiver": "Meridian Retail",
        "sender_summary": (
            "Sentinel Pay sells a real-time payment-fraud detection API for "
            "online merchants: 38ms p99 risk scoring, nightly retraining on 4 "
            "billion transactions, SOC 2 Type II and PCI-DSS Level 1 "
            "certification, and prebuilt connectors for Stripe, Adyen, and "
            "Braintree."
        ),
        "receiver_summary": (
            "Meridian Retail is an EMEA retailer processing 2.1M card "
            "transactions daily; its fraud tool's 4.2% false-positive rate "
            "costs $3M/yr in declined orders, and a Q3 APAC expansion needs "
            "multi-region latency under 50ms."
        ),
        "sender_facts": [...unchanged...],
        "receiver_facts": [...unchanged...],
    },
    {
        "sender": "Nimbus Analytics",
        "receiver": "Harborview Logistics",
        "sender_summary": (
            "Nimbus Analytics is a cloud data warehouse whose columnar engine "
            "runs analytical queries 12x faster than Postgres at TB scale, "
            "with zero-copy cloning of 10TB warehouses in seconds and "
            "per-second compute billing with 60s autosuspend."
        ),
        "receiver_summary": (
            "Harborview Logistics runs same-day shipping operations slowed by "
            "a 6-hour nightly ETL and 40-second peak dashboard queries; it "
            "wants sub-second dashboards for 500 warehouse managers."
        ),
        "sender_facts": [...unchanged...],
        "receiver_facts": [...unchanged...],
    },
    {
        "sender": "Pulse Observability",
        "receiver": "Cobalt Bank",
        "sender_summary": (
            "Pulse Observability is a tracing platform ingesting 5M spans/sec "
            "with 15-second end-to-end trace latency, anomaly detection that "
            "cut a customer's MTTR from 45 to 8 minutes, and 30-day "
            "high-cardinality retention at $0.10/GB."
        ),
        "receiver_summary": (
            "Cobalt Bank operates 1,200 microservices, misses SLA on 3% of "
            "incidents due to slow root-cause analysis, pages on-call 60 "
            "times weekly, and must retain audit logs for 7 years."
        ),
        "sender_facts": [...unchanged...],
        "receiver_facts": [...unchanged...],
    },
]
```

(`[...unchanged...]` above means: keep the existing fact lists exactly as they are in the file — only ADD the two summary keys to each dict.)

Replace `_seed_chunks`:

```python
def _seed_chunks(embedder, company, facts, *, summary=""):
    document = DocumentFactory(
        company=company,
        file_name=f"{company.name} overview.pdf",
        summary=summary,
    )
    for i, fact in enumerate(facts, start=1):
        DocumentChunkFactory(
            document=document,
            company=company,
            content=fact,
            page_number=i,
            embedding=embedder.embed_query(fact),
        )
```

Update the two call sites in the pair loop:

```python
            _seed_chunks(embedder, sender, pair["sender_facts"], summary=pair["sender_summary"])
            _seed_chunks(embedder, receiver, pair["receiver_facts"], summary=pair["receiver_summary"])
```

The sparse adversarial call stays exactly as-is (no summary kwarg → blank).

Also update the module docstring's last sentence to mention that each company's facts now live in one document with a summary, so neighbor expansion and document summaries are exercised by the eval.

- [ ] **Step 3: Run tests to verify they pass**

Run: `docker compose run --rm django pytest collateral_ai/materials/tests/generation/test_seed.py -v`
Expected: ALL PASS (including the two pre-existing seed tests)

- [ ] **Step 4: Commit**

```bash
git add backend/collateral_ai/materials/generation/eval/seed.py backend/collateral_ai/materials/tests/generation/test_seed.py
git commit -m "feat(eval): golden dataset exercises neighbor expansion and summaries"
```

---

### Task 10: Full verification + eval gate

**Files:** none created — verification and (manual) eval runs.

- [ ] **Step 1: Full backend suite**

Run: `docker compose run --rm django pytest`
Expected: ALL PASS

- [ ] **Step 2: Lint**

Run from repo root: `pre-commit run --all-files`
Expected: all hooks pass (ruff, formatting). Fix anything it flags and re-run.

- [ ] **Step 3: Eval A/B (needs `.env` with `LANGSMITH_API_KEY` + GCP ADC; makes real LLM calls, ~13 materials × 2 arms on gemini-2.5-flash — a few cents)**

```bash
# 1. Re-seed the golden dataset (now with grouped docs + summaries)
docker compose run --rm django python manage.py seed_eval_dataset

# 2. Baseline arm — today's behavior exactly
docker compose run --rm \
  -e MATERIAL_NEIGHBOR_WINDOW=0 \
  -e MATERIAL_INCLUDE_DOC_SUMMARIES=false \
  django python manage.py run_eval --label baseline-bare-chunks

# 3. Enriched arm — defaults (window=1 + summaries)
docker compose run --rm django python manage.py run_eval --label enriched-w1-summaries
```

- [ ] **Step 4: Record the verdict**

Open the two experiments side-by-side in LangSmith (dataset `material-gen-golden`). Record in the PR description: per-metric scores (groundedness, specificity, schema_valid, sources_grounded, counts_match, no_inline_citations) for both arms, plus prompt token counts from the traces. Decision rule from the spec: if the enriched arm does not beat baseline, ship with `MATERIAL_NEIGHBOR_WINDOW=0` and `MATERIAL_INCLUDE_DOC_SUMMARIES=false` in the prod env (dark) rather than revert.

---

## Self-Review Notes

- Spec §3 (expansion, dedupe, stitching) → Tasks 2–4. §4 (citation contract) → Task 4 keeps `content` as the seed; `GenerationSource.snippet` in `service.py` reads `.content`, so no change there — verified against `service.py:166`. §5.1 → Task 1. §5.2 → Tasks 5–6. §6 → Task 7. §7 → settings spread across Tasks 1, 4, 5, 8 (each with its consumer); the `MATERIAL_INCLUDE_DOC_SUMMARIES` addition also patches the spec table (Task 8). §10 eval gate → Tasks 9–10 (Task 9 exists because the current seeder gives every chunk its own document, which would make the eval blind to both features).
- Type consistency: `expand() -> dict[int, str]` consumed in Task 4 via `expanded.get(chunk.pk, chunk.content)`; `fetch_document_summaries -> list[dict[str, str]]` consumed in Task 8 and asserted in tests with the same `{"file_name", "summary"}` shape throughout.
