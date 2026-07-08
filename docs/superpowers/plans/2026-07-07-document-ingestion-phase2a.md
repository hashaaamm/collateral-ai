# Document Ingestion — Phase 2a (Processing Core) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn an uploaded PDF into embedded, retrievable `DocumentChunk` rows entirely locally — `python manage.py process_document --document-id <id>` downloads the PDF, extracts text/tables/images, chunks, embeds via Gemini (Vertex AI), stores vectors in Postgres+pgvector, and updates the `Document` status/counts.

**Architecture:** A new `collateral_ai.documents.processing` package with focused services (storage, extraction, chunking, embeddings, pipeline) orchestrated by a `process_document` management command. Embeddings use `google-genai` in **Vertex AI mode** (keyless ADC). Vectors are stored in a `DocumentChunk.embedding` pgvector column (768-dim). Phase 2a wires `complete` to run the command **inline** for local/dev; the prod Cloud Run Job trigger + Pulumi infra is Phase 2b.

**Tech Stack:** Django 6 + DRF, PyMuPDF (`fitz`), pdfplumber, `google-genai` (Vertex mode), `pgvector` (Django `VectorField`), local `pgvector/pgvector:pg16` image.

## Global Constraints

- Backend Django 6.0.x; deps are **exact-pinned** in `backend/pyproject.toml` (match the existing style).
- Embeddings: model `gemini-embedding-001`, **768** dims, task_type `RETRIEVAL_DOCUMENT` for documents / `RETRIEVAL_QUERY` for queries, L2-normalized, batched (default 64). Never mix models/dims in the vector column.
- Vertex AI mode via ADC (no API key): `genai.Client(vertexai=True, project=..., location=...)`. Local dev uses `gcloud auth application-default login` creds or a key file; **tests MUST mock the genai client — no real Vertex calls in tests.**
- Chunking is deterministic (word-overlap 300/50, version `v1`), no LLM.
- Status lifecycle (from Phase 1 `DocumentStatus`): `pending → processing → processed | failed`. The worker owns `processing → processed|failed`.
- `DocumentChunk.embedding` is `pgvector.django.VectorField(dimensions=768)`; the pgvector extension is enabled via a migration using `pgvector.django.VectorExtension`.
- Backend tests run via `just pytest <path>` from `backend/` (Docker, settings `config.settings.test`), joining the running Compose project: prefix `COMPOSE_PROJECT_NAME=collateralai`. Adding deps / swapping the postgres image requires an image rebuild (`just build`).
- TDD: failing test first; commit per green task. DRY, YAGNI.
- **Out of scope (Phase 2b):** Cloud Run Job, Pulumi (`aiplatform` API, IAM, Job resource), the prod `complete`→Job trigger, CI job-image update, prod `CREATE EXTENSION` on Cloud SQL, prod deploy. Also out of scope: the retrieval/search endpoint (chunks are stored ready for it).

## File Structure

**Backend (new):**
- `collateral_ai/documents/processing/__init__.py`
- `collateral_ai/documents/processing/storage.py` — GCS byte download/upload (ADC).
- `collateral_ai/documents/processing/chunking.py` — `ChunkingService`.
- `collateral_ai/documents/processing/extraction.py` — `PdfExtractionService` + extraction DTOs.
- `collateral_ai/documents/processing/embeddings.py` — `EmbeddingService` (Vertex).
- `collateral_ai/documents/processing/pipeline.py` — `DocumentProcessingService`.
- `collateral_ai/documents/management/__init__.py`, `management/commands/__init__.py`, `management/commands/process_document.py`.
- `collateral_ai/documents/tests/processing/__init__.py` + test modules per service.
- `collateral_ai/documents/tests/fixtures.py` — builds a tiny in-memory PDF for tests.

**Backend (modified):**
- `pyproject.toml` — add `pymupdf`, `pdfplumber`, `google-genai`, `pgvector`.
- `config/settings/base.py` — embedding/chunking/Vertex settings.
- `compose/production/postgres/Dockerfile` — `FROM postgres:16` → `FROM pgvector/pgvector:pg16`.
- `collateral_ai/documents/models.py` — add `DocumentChunk`.
- `collateral_ai/documents/migrations/0002_*.py` — `VectorExtension` + `DocumentChunk`.
- `collateral_ai/documents/api/views.py` — `complete` runs the pipeline inline (local) instead of the stub.

---

### Task 1: Dependencies, settings, and local pgvector image

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `backend/config/settings/base.py`
- Modify: `backend/compose/production/postgres/Dockerfile`

**Interfaces:**
- Produces settings: `EMBEDDING_MODEL`, `EMBEDDING_DIMENSIONS`, `EMBEDDING_BATCH_SIZE`, `DOCUMENT_CHUNK_MAX_WORDS`, `DOCUMENT_CHUNK_OVERLAP_WORDS`, `DOCUMENT_CHUNKING_VERSION`, `GOOGLE_CLOUD_PROJECT`, `VERTEX_LOCATION`.

- [ ] **Step 1: Add dependencies**

In `backend/pyproject.toml` `dependencies`, add (keep alphabetical-ish, exact pins):

```toml
  "google-genai==1.28.0",
  "pdfplumber==0.11.7",
  "pgvector==0.4.1",
  "pymupdf==1.26.4",
```

(If a pin fails to resolve, use the latest on PyPI and re-run `uv lock`.)

- [ ] **Step 2: Add settings**

Append to `backend/config/settings/base.py` (end, under "Your stuff"):

```python
# Document processing / embeddings
# ------------------------------------------------------------------------------
GOOGLE_CLOUD_PROJECT = env("GOOGLE_CLOUD_PROJECT", default="")
VERTEX_LOCATION = env("VERTEX_LOCATION", default="us-central1")
EMBEDDING_MODEL = env("EMBEDDING_MODEL", default="gemini-embedding-001")
EMBEDDING_DIMENSIONS = env.int("EMBEDDING_DIMENSIONS", default=768)
EMBEDDING_BATCH_SIZE = env.int("EMBEDDING_BATCH_SIZE", default=64)
DOCUMENT_CHUNK_MAX_WORDS = env.int("DOCUMENT_CHUNK_MAX_WORDS", default=300)
DOCUMENT_CHUNK_OVERLAP_WORDS = env.int("DOCUMENT_CHUNK_OVERLAP_WORDS", default=50)
DOCUMENT_CHUNKING_VERSION = env("DOCUMENT_CHUNKING_VERSION", default="v1")
```

- [ ] **Step 3: Swap the local Postgres image to pgvector**

In `backend/compose/production/postgres/Dockerfile`, change the first line:

```dockerfile
FROM pgvector/pgvector:pg16
```

(Everything else in that Dockerfile stays.)

- [ ] **Step 4: Rebuild and verify the extension is available**

```
cd backend
COMPOSE_PROJECT_NAME=collateralai docker compose -f docker-compose.local.yml run --rm django uv lock
COMPOSE_PROJECT_NAME=collateralai just build
COMPOSE_PROJECT_NAME=collateralai docker compose -f docker-compose.local.yml down postgres && COMPOSE_PROJECT_NAME=collateralai docker compose -f docker-compose.local.yml up -d postgres
```

Verify pgvector is present in the running DB:

```
COMPOSE_PROJECT_NAME=collateralai docker compose -f docker-compose.local.yml exec postgres psql -U "$(grep POSTGRES_USER .envs/.local/.postgres | cut -d= -f2)" -d "$(grep POSTGRES_DB .envs/.local/.postgres | cut -d= -f2)" -c "CREATE EXTENSION IF NOT EXISTS vector; SELECT extname FROM pg_extension WHERE extname='vector';"
```

Expected: prints one row `vector`. (Recreating the postgres container may require re-running `just gcs-init` if the emulator shares the compose project; harmless.)

- [ ] **Step 5: Verify settings import cleanly**

Run: `cd backend && COMPOSE_PROJECT_NAME=collateralai just manage check`
Expected: `System check identified no issues`.

- [ ] **Step 6: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock backend/config/settings/base.py backend/compose/production/postgres/Dockerfile
git commit -m "feat(documents): add processing deps, embedding settings, local pgvector image"
```

---

### Task 2: `DocumentChunk` model + pgvector extension migration

**Files:**
- Modify: `backend/collateral_ai/documents/models.py`
- Create: `backend/collateral_ai/documents/migrations/0002_documentchunk.py` (generated + hand-edited to add `VectorExtension`)
- Modify: `backend/collateral_ai/documents/tests/factories.py`
- Create: `backend/collateral_ai/documents/tests/test_chunk_model.py`

**Interfaces:**
- Produces: `DocumentChunk` with fields `document` (FK Document, CASCADE, related_name="chunks"), `company` (FK companies.Company, CASCADE, related_name="document_chunks"), `chunk_type` (str), `page_number` (int), `content` (str), `embedding` (VectorField 768), `metadata` (dict), `created_at`. `DocumentChunkFactory`.

- [ ] **Step 1: Add the model**

Append to `backend/collateral_ai/documents/models.py`:

```python
from pgvector.django import VectorField


class DocumentChunk(models.Model):
    """One embedded chunk of a processed document (text, table, or image caption)."""

    document = models.ForeignKey(
        Document, on_delete=models.CASCADE, related_name="chunks",
    )
    company = models.ForeignKey(
        "companies.Company", on_delete=models.CASCADE, related_name="document_chunks",
    )
    chunk_type = models.CharField(_("chunk type"), max_length=32)
    page_number = models.PositiveIntegerField()
    content = models.TextField()
    embedding = VectorField(dimensions=768)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("document chunk")
        verbose_name_plural = _("document chunks")
        ordering = ["document_id", "page_number", "id"]

    def __str__(self) -> str:
        return f"{self.document_id} p{self.page_number} {self.chunk_type}"
```

(Put the `from pgvector.django import VectorField` import at the top with the other imports.)

- [ ] **Step 2: Generate the migration**

Run: `cd backend && COMPOSE_PROJECT_NAME=collateralai just manage makemigrations documents`
Expected: creates `migrations/0002_documentchunk.py`.

- [ ] **Step 3: Add the pgvector extension operation to the migration**

Edit `migrations/0002_documentchunk.py` — add the import and make `VectorExtension()` the FIRST operation (the `vector` type must exist before the table is created):

```python
from pgvector.django import VectorExtension
```

and in `operations = [`, put `VectorExtension(),` as the first entry, before `migrations.CreateModel(...)`.

- [ ] **Step 4: Write the failing model test**

Add `DocumentChunkFactory` to `backend/collateral_ai/documents/tests/factories.py`:

```python
from collateral_ai.documents.models import DocumentChunk


class DocumentChunkFactory(DjangoModelFactory[DocumentChunk]):
    document = SubFactory(DocumentFactory)
    chunk_type = "text"
    page_number = 1
    content = "hello world"
    embedding = [0.0] * 768

    class Meta:
        model = DocumentChunk

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        # company defaults to the document's company when not given
        kwargs.setdefault("company", kwargs["document"].company)
        return super()._create(model_class, *args, **kwargs)
```

`backend/collateral_ai/documents/tests/test_chunk_model.py`:

```python
from __future__ import annotations

import pytest

from collateral_ai.documents.models import DocumentChunk
from collateral_ai.documents.tests.factories import DocumentChunkFactory

pytestmark = pytest.mark.django_db


def test_chunk_persists_embedding_dimensions():
    chunk = DocumentChunkFactory(embedding=[0.1] * 768)
    chunk.refresh_from_db()
    assert len(list(chunk.embedding)) == 768


def test_chunk_company_defaults_to_document_company():
    chunk = DocumentChunkFactory()
    assert chunk.company_id == chunk.document.company_id


def test_chunks_cascade_delete_with_document():
    chunk = DocumentChunkFactory()
    doc = chunk.document
    doc.delete()
    assert not DocumentChunk.objects.filter(pk=chunk.pk).exists()
```

- [ ] **Step 5: Run to verify fail → migrate → pass**

Run: `cd backend && COMPOSE_PROJECT_NAME=collateralai just pytest collateral_ai/documents/tests/test_chunk_model.py -v`
Expected: PASS (3 tests). (Pytest applies migrations to the test DB, which runs `VectorExtension` first, then creates the table. If it errors that the `vector` type is unknown, the `VectorExtension()` op isn't first — fix ordering.)

- [ ] **Step 6: Commit**

```bash
git add backend/collateral_ai/documents/models.py backend/collateral_ai/documents/migrations/0002_documentchunk.py backend/collateral_ai/documents/tests/factories.py backend/collateral_ai/documents/tests/test_chunk_model.py
git commit -m "feat(documents): DocumentChunk model + pgvector extension migration"
```

---

### Task 3: Storage service (GCS byte download/upload)

**Files:**
- Create: `backend/collateral_ai/documents/processing/__init__.py` (empty)
- Create: `backend/collateral_ai/documents/processing/storage.py`
- Create: `backend/collateral_ai/documents/tests/processing/__init__.py` (empty)
- Create: `backend/collateral_ai/documents/tests/processing/test_storage.py`

**Interfaces:**
- Produces: `StorageService` with `download(object_path: str) -> bytes` and `upload(object_path: str, content: bytes, content_type: str) -> str`, backed by `collateral_ai.companies.gcs._bucket()` (ADC; runtime SA has `storage.objectAdmin`).

- [ ] **Step 1: Write the failing test**

`backend/collateral_ai/documents/tests/processing/test_storage.py`:

```python
from __future__ import annotations

from unittest import mock

from collateral_ai.documents.processing.storage import StorageService


def test_download_returns_blob_bytes():
    blob = mock.Mock()
    blob.download_as_bytes.return_value = b"pdf-bytes"
    bucket = mock.Mock()
    bucket.blob.return_value = blob
    with mock.patch(
        "collateral_ai.documents.processing.storage._bucket", return_value=bucket,
    ):
        assert StorageService().download("path/x.pdf") == b"pdf-bytes"
    bucket.blob.assert_called_once_with("path/x.pdf")


def test_upload_sends_content_and_returns_path():
    blob = mock.Mock()
    bucket = mock.Mock()
    bucket.blob.return_value = blob
    with mock.patch(
        "collateral_ai.documents.processing.storage._bucket", return_value=bucket,
    ):
        out = StorageService().upload("p/img.png", b"bytes", "image/png")
    blob.upload_from_string.assert_called_once_with(b"bytes", content_type="image/png")
    assert out == "p/img.png"
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && COMPOSE_PROJECT_NAME=collateralai just pytest collateral_ai/documents/tests/processing/test_storage.py -v`
Expected: FAIL (module missing).

- [ ] **Step 3: Implement**

`backend/collateral_ai/documents/processing/storage.py`:

```python
"""GCS byte I/O for the document worker (ADC, via the companies bucket helper)."""
from __future__ import annotations

from collateral_ai.companies.gcs import _bucket


class StorageService:
    def download(self, object_path: str) -> bytes:
        return _bucket().blob(object_path).download_as_bytes()

    def upload(self, object_path: str, content: bytes, content_type: str) -> str:
        _bucket().blob(object_path).upload_from_string(content, content_type=content_type)
        return object_path
```

- [ ] **Step 4: Run to verify pass**

Run: `cd backend && COMPOSE_PROJECT_NAME=collateralai just pytest collateral_ai/documents/tests/processing/test_storage.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/collateral_ai/documents/processing/__init__.py backend/collateral_ai/documents/processing/storage.py backend/collateral_ai/documents/tests/processing
git commit -m "feat(documents): worker storage service (GCS byte I/O via ADC)"
```

---

### Task 4: Chunking service

**Files:**
- Create: `backend/collateral_ai/documents/processing/chunking.py`
- Create: `backend/collateral_ai/documents/tests/processing/test_chunking.py`

**Interfaces:**
- Produces: `ChunkingService()` with `chunk_text(text: str, page_number: int, prefix: str = "") -> list[dict]`, each dict `{page_number, chunk_index, content, word_start, word_end}`. Reads `max_words`/`overlap_words`/`version` from settings. Attrs `.max_words`, `.overlap_words`, `.version`.

- [ ] **Step 1: Write the failing test**

`backend/collateral_ai/documents/tests/processing/test_chunking.py`:

```python
from __future__ import annotations

from collateral_ai.documents.processing.chunking import ChunkingService


def test_short_text_single_chunk():
    chunks = ChunkingService().chunk_text("one two three", page_number=2)
    assert len(chunks) == 1
    assert chunks[0]["content"] == "one two three"
    assert chunks[0]["page_number"] == 2
    assert chunks[0]["chunk_index"] == 0


def test_long_text_splits_with_overlap(settings):
    settings.DOCUMENT_CHUNK_MAX_WORDS = 10
    settings.DOCUMENT_CHUNK_OVERLAP_WORDS = 3
    words = " ".join(str(i) for i in range(25))
    chunks = ChunkingService().chunk_text(words, page_number=1)
    assert len(chunks) == 3
    # overlap: second chunk starts 3 words before the first chunk's end (index 7)
    assert chunks[0]["word_end"] == 10
    assert chunks[1]["word_start"] == 7


def test_prefix_is_prepended():
    chunks = ChunkingService().chunk_text("a b", page_number=1, prefix="TABLE")
    assert chunks[0]["content"].startswith("TABLE\n\n")


def test_empty_text_no_chunks():
    assert ChunkingService().chunk_text("   ", page_number=1) == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && COMPOSE_PROJECT_NAME=collateralai just pytest collateral_ai/documents/tests/processing/test_chunking.py -v`
Expected: FAIL (module missing).

- [ ] **Step 3: Implement**

`backend/collateral_ai/documents/processing/chunking.py`:

```python
"""Deterministic word-overlap chunking (no LLM)."""
from __future__ import annotations

from typing import Any

from django.conf import settings


class ChunkingService:
    def __init__(self) -> None:
        self.max_words = settings.DOCUMENT_CHUNK_MAX_WORDS
        self.overlap_words = settings.DOCUMENT_CHUNK_OVERLAP_WORDS
        self.version = settings.DOCUMENT_CHUNKING_VERSION

    def chunk_text(self, text: str, page_number: int, prefix: str = "") -> list[dict[str, Any]]:
        words = text.split()
        if not words:
            return []
        chunks: list[dict[str, Any]] = []
        start = 0
        chunk_index = 0
        while start < len(words):
            end = start + self.max_words
            content = " ".join(words[start:end]).strip()
            if prefix:
                content = f"{prefix}\n\n{content}"
            chunks.append({
                "page_number": page_number,
                "chunk_index": chunk_index,
                "content": content,
                "word_start": start,
                "word_end": min(end, len(words)),
            })
            chunk_index += 1
            if end >= len(words):
                break
            start = max(0, end - self.overlap_words)
        return chunks
```

- [ ] **Step 4: Run to verify pass**

Run: `cd backend && COMPOSE_PROJECT_NAME=collateralai just pytest collateral_ai/documents/tests/processing/test_chunking.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/collateral_ai/documents/processing/chunking.py backend/collateral_ai/documents/tests/processing/test_chunking.py
git commit -m "feat(documents): deterministic word-overlap chunking service"
```

---

### Task 5: PDF extraction service

**Files:**
- Create: `backend/collateral_ai/documents/tests/fixtures.py`
- Create: `backend/collateral_ai/documents/processing/extraction.py`
- Create: `backend/collateral_ai/documents/tests/processing/test_extraction.py`

**Interfaces:**
- Consumes: `StorageService` (for image upload). `Document` (for `company_id`/`id`/`file_name` when naming image paths).
- Produces: DTOs `ExtractedTextBlock(page_number, text)`, `ExtractedTable(page_number, markdown)`, `ExtractedImage(page_number, storage_path, caption)`, `ExtractionResult(page_count, text_blocks, tables, images)`. `PdfExtractionService(storage)` with `extract(pdf_bytes: bytes, document) -> ExtractionResult`.

- [ ] **Step 1: Add a tiny-PDF test fixture builder**

`backend/collateral_ai/documents/tests/fixtures.py`:

```python
from __future__ import annotations


def make_pdf(text: str = "Hello world from a test PDF.") -> bytes:
    """A minimal one-page PDF containing `text`, built with PyMuPDF."""
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data
```

- [ ] **Step 2: Write the failing test**

`backend/collateral_ai/documents/tests/processing/test_extraction.py`:

```python
from __future__ import annotations

from unittest import mock

from collateral_ai.documents.processing.extraction import PdfExtractionService
from collateral_ai.documents.tests.fixtures import make_pdf


class _Doc:
    id = 1
    company_id = 1
    file_name = "test.pdf"


def test_extract_text_and_page_count():
    storage = mock.Mock()
    result = PdfExtractionService(storage=storage).extract(make_pdf("Alpha Beta Gamma"), _Doc())
    assert result.page_count == 1
    joined = " ".join(b.text for b in result.text_blocks)
    assert "Alpha Beta Gamma" in joined
    # our minimal fixture has no embedded images/tables
    assert result.images == []


def test_extract_handles_empty_pdf():
    storage = mock.Mock()
    result = PdfExtractionService(storage=storage).extract(make_pdf(" "), _Doc())
    assert result.page_count == 1
    assert isinstance(result.tables, list)
```

- [ ] **Step 3: Run to verify it fails**

Run: `cd backend && COMPOSE_PROJECT_NAME=collateralai just pytest collateral_ai/documents/tests/processing/test_extraction.py -v`
Expected: FAIL (module missing).

- [ ] **Step 4: Implement**

`backend/collateral_ai/documents/processing/extraction.py`:

```python
"""PDF extraction: text + images (PyMuPDF), tables (pdfplumber)."""
from __future__ import annotations

import io
import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ExtractedTextBlock:
    page_number: int
    text: str


@dataclass
class ExtractedTable:
    page_number: int
    markdown: str


@dataclass
class ExtractedImage:
    page_number: int
    storage_path: str
    caption: str


@dataclass
class ExtractionResult:
    page_count: int
    text_blocks: list[ExtractedTextBlock]
    tables: list[ExtractedTable]
    images: list[ExtractedImage]


class PdfExtractionService:
    def __init__(self, storage) -> None:
        self.storage = storage

    def extract(self, pdf_bytes: bytes, document) -> ExtractionResult:
        return ExtractionResult(
            page_count=self._page_count(pdf_bytes),
            text_blocks=self._text_blocks(pdf_bytes),
            tables=self._tables(pdf_bytes),
            images=self._images(pdf_bytes, document),
        )

    def _page_count(self, pdf_bytes: bytes) -> int:
        import fitz

        with fitz.open(stream=pdf_bytes, filetype="pdf") as pdf:
            return pdf.page_count

    def _text_blocks(self, pdf_bytes: bytes) -> list[ExtractedTextBlock]:
        import fitz

        blocks: list[ExtractedTextBlock] = []
        with fitz.open(stream=pdf_bytes, filetype="pdf") as pdf:
            for i, page in enumerate(pdf, start=1):
                text = page.get_text("text").strip()
                if text:
                    blocks.append(ExtractedTextBlock(page_number=i, text=text))
        return blocks

    def _tables(self, pdf_bytes: bytes) -> list[ExtractedTable]:
        import pdfplumber

        tables: list[ExtractedTable] = []
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for i, page in enumerate(pdf.pages, start=1):
                for t_index, table in enumerate(page.extract_tables() or [], start=1):
                    md = self._table_to_markdown(table)
                    if md.strip():
                        tables.append(ExtractedTable(
                            page_number=i,
                            markdown=f"Table {t_index} on page {i}\n\n{md}",
                        ))
        return tables

    def _table_to_markdown(self, table: list[list[Any]]) -> str:
        rows = [[("" if c is None else str(c).replace("\n", " ").strip()) for c in row]
                for row in table if row]
        if not rows:
            return ""
        cols = max(len(r) for r in rows)
        rows = [r + [""] * (cols - len(r)) for r in rows]
        lines = ["| " + " | ".join(rows[0]) + " |", "| " + " | ".join(["---"] * cols) + " |"]
        lines += ["| " + " | ".join(r) + " |" for r in rows[1:]]
        return "\n".join(lines)

    def _images(self, pdf_bytes: bytes, document) -> list[ExtractedImage]:
        import fitz

        images: list[ExtractedImage] = []
        with fitz.open(stream=pdf_bytes, filetype="pdf") as pdf:
            for page_index, page in enumerate(pdf, start=1):
                for img_index, info in enumerate(page.get_images(full=True), start=1):
                    xref = info[0]
                    try:
                        extracted = pdf.extract_image(xref)
                    except Exception:
                        logger.exception("image extract failed xref=%s doc=%s", xref, document.id)
                        continue
                    data = extracted.get("image")
                    ext = extracted.get("ext", "png")
                    if not data:
                        continue
                    path = (
                        f"media/companies/{document.company_id}/documents/{document.id}"
                        f"/images/page_{page_index}_image_{img_index}.{ext}"
                    )
                    self.storage.upload(path, data, self._content_type(ext))
                    images.append(ExtractedImage(
                        page_number=page_index,
                        storage_path=path,
                        caption=f"Image from page {page_index} of {document.file_name}.",
                    ))
        return images

    def _content_type(self, ext: str) -> str:
        e = ext.lower().strip(".")
        return {"jpg": "image/jpeg", "jpeg": "image/jpeg"}.get(e, f"image/{e}")
```

- [ ] **Step 5: Run to verify pass**

Run: `cd backend && COMPOSE_PROJECT_NAME=collateralai just pytest collateral_ai/documents/tests/processing/test_extraction.py -v`
Expected: PASS (2 tests).

- [ ] **Step 6: Commit**

```bash
git add backend/collateral_ai/documents/tests/fixtures.py backend/collateral_ai/documents/processing/extraction.py backend/collateral_ai/documents/tests/processing/test_extraction.py
git commit -m "feat(documents): PDF extraction service (text/tables/images)"
```

---

### Task 6: Embedding service (Vertex AI)

**Files:**
- Create: `backend/collateral_ai/documents/processing/embeddings.py`
- Create: `backend/collateral_ai/documents/tests/processing/test_embeddings.py`

**Interfaces:**
- Produces: `EmbeddingService()` with `embed_documents(texts: list[str]) -> list[list[float]]` (task_type `RETRIEVAL_DOCUMENT`) and `embed_query(query: str) -> list[float]` (task_type `RETRIEVAL_QUERY`). Attrs `.model`, `.dimensions`, `.batch_size`. Uses a `_client()` returning a Vertex `genai.Client`, patched in tests.

- [ ] **Step 1: Write the failing test**

`backend/collateral_ai/documents/tests/processing/test_embeddings.py`:

```python
from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

from collateral_ai.documents.processing.embeddings import EmbeddingService


def _fake_client(vecs):
    client = mock.Mock()
    client.models.embed_content.return_value = SimpleNamespace(
        embeddings=[SimpleNamespace(values=v) for v in vecs],
    )
    return client


def test_embed_documents_normalizes_and_returns_vectors():
    raw = [[3.0] + [0.0] * 767, [0.0, 4.0] + [0.0] * 766]
    with mock.patch(
        "collateral_ai.documents.processing.embeddings.EmbeddingService._client",
        return_value=_fake_client(raw),
    ):
        out = EmbeddingService().embed_documents(["a", "b"])
    assert len(out) == 2
    assert all(len(v) == 768 for v in out)
    # L2-normalized: the single non-zero component becomes 1.0
    assert abs(out[0][0] - 1.0) < 1e-6
    assert abs(out[1][1] - 1.0) < 1e-6


def test_embed_documents_uses_retrieval_document_task_type():
    with mock.patch(
        "collateral_ai.documents.processing.embeddings.EmbeddingService._client",
        return_value=_fake_client([[1.0] + [0.0] * 767]),
    ) as client_factory:
        EmbeddingService().embed_documents(["x"])
    cfg = client_factory.return_value.models.embed_content.call_args.kwargs["config"]
    assert cfg.task_type == "RETRIEVAL_DOCUMENT"
    assert cfg.output_dimensionality == 768


def test_embed_documents_skips_blank_texts():
    with mock.patch(
        "collateral_ai.documents.processing.embeddings.EmbeddingService._client",
        return_value=_fake_client([[1.0] + [0.0] * 767]),
    ):
        out = EmbeddingService().embed_documents(["   ", "real"])
    assert len(out) == 1
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && COMPOSE_PROJECT_NAME=collateralai just pytest collateral_ai/documents/tests/processing/test_embeddings.py -v`
Expected: FAIL (module missing).

- [ ] **Step 3: Implement**

`backend/collateral_ai/documents/processing/embeddings.py`:

```python
"""Gemini embeddings via Vertex AI (keyless ADC)."""
from __future__ import annotations

import logging
from collections.abc import Iterable

from django.conf import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    def __init__(self) -> None:
        self.model = settings.EMBEDDING_MODEL
        self.dimensions = int(settings.EMBEDDING_DIMENSIONS)
        self.batch_size = int(settings.EMBEDDING_BATCH_SIZE)

    def _client(self):
        from google import genai

        return genai.Client(
            vertexai=True,
            project=settings.GOOGLE_CLOUD_PROJECT,
            location=settings.VERTEX_LOCATION,
        )

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts, task_type="RETRIEVAL_DOCUMENT")

    def embed_query(self, query: str) -> list[float]:
        out = self._embed([query], task_type="RETRIEVAL_QUERY")
        if not out:
            raise ValueError("Gemini returned no query embedding.")
        return out[0]

    def _embed(self, texts: list[str], task_type: str) -> list[list[float]]:
        clean = [t.strip() for t in texts if t and t.strip()]
        if not clean:
            return []
        from google.genai import types

        client = self._client()
        out: list[list[float]] = []
        for batch in self._batched(clean, self.batch_size):
            resp = client.models.embed_content(
                model=self.model,
                contents=batch,
                config=types.EmbedContentConfig(
                    task_type=task_type,
                    output_dimensionality=self.dimensions,
                ),
            )
            if not resp.embeddings:
                raise RuntimeError("Gemini returned no embeddings for batch.")
            for emb in resp.embeddings:
                values = list(emb.values)
                if len(values) != self.dimensions:
                    raise ValueError(
                        f"embedding dim mismatch expected={self.dimensions} actual={len(values)}",
                    )
                out.append(self._normalize(values))
        return out

    def _normalize(self, vec: list[float]) -> list[float]:
        mag = sum(v * v for v in vec) ** 0.5
        return vec if mag == 0 else [v / mag for v in vec]

    def _batched(self, values: list[str], size: int) -> Iterable[list[str]]:
        for i in range(0, len(values), size):
            yield values[i:i + size]
```

- [ ] **Step 4: Run to verify pass**

Run: `cd backend && COMPOSE_PROJECT_NAME=collateralai just pytest collateral_ai/documents/tests/processing/test_embeddings.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/collateral_ai/documents/processing/embeddings.py backend/collateral_ai/documents/tests/processing/test_embeddings.py
git commit -m "feat(documents): Vertex AI embedding service (gemini-embedding-001, 768d)"
```

---

### Task 7: Pipeline + `process_document` command + inline `complete`

**Files:**
- Create: `backend/collateral_ai/documents/processing/pipeline.py`
- Create: `backend/collateral_ai/documents/management/__init__.py` (empty)
- Create: `backend/collateral_ai/documents/management/commands/__init__.py` (empty)
- Create: `backend/collateral_ai/documents/management/commands/process_document.py`
- Modify: `backend/collateral_ai/documents/api/views.py` (`complete` runs the pipeline inline)
- Create: `backend/collateral_ai/documents/tests/processing/test_pipeline.py`
- Modify: `backend/collateral_ai/documents/tests/api/test_views.py` (complete triggers processing)

**Interfaces:**
- Consumes: `StorageService`, `PdfExtractionService`, `ChunkingService`, `EmbeddingService`, `Document`, `DocumentChunk`, `DocumentStatus`.
- Produces: `DocumentProcessingService().process(document_id: int, force: bool = False) -> None` — sets `processing`, extracts→chunks→embeds→replaces `DocumentChunk`s, updates counts + `processed`; on exception sets `failed` + `error_message` and re-raises. `process_document` management command with `--document-id` (required) and `--force`.

- [ ] **Step 1: Write the failing pipeline test**

`backend/collateral_ai/documents/tests/processing/test_pipeline.py`:

```python
from __future__ import annotations

from unittest import mock

import pytest

from collateral_ai.documents.models import Document
from collateral_ai.documents.models import DocumentChunk
from collateral_ai.documents.processing.pipeline import DocumentProcessingService
from collateral_ai.documents.statuses import DocumentStatus
from collateral_ai.documents.tests.factories import DocumentFactory
from collateral_ai.documents.tests.fixtures import make_pdf

pytestmark = pytest.mark.django_db


def _patches(pdf=b"", embeddings=None):
    return (
        mock.patch(
            "collateral_ai.documents.processing.pipeline.StorageService.download",
            return_value=pdf or make_pdf("Alpha beta gamma delta."),
        ),
        mock.patch(
            "collateral_ai.documents.processing.embeddings.EmbeddingService.embed_documents",
            side_effect=lambda texts: [[0.1] * 768 for _ in texts],
        ),
    )


def test_process_creates_chunks_and_marks_processed():
    doc = DocumentFactory(status=DocumentStatus.PROCESSING, storage_path="p/x.pdf")
    p1, p2 = _patches()
    with p1, p2:
        DocumentProcessingService().process(doc.id)
    doc.refresh_from_db()
    assert doc.status == DocumentStatus.PROCESSED
    assert doc.page_count == 1
    assert doc.chunks_count == DocumentChunk.objects.filter(document=doc).count() > 0
    assert doc.error_message == ""


def test_process_marks_failed_on_error():
    doc = DocumentFactory(status=DocumentStatus.PROCESSING, storage_path="p/x.pdf")
    with mock.patch(
        "collateral_ai.documents.processing.pipeline.StorageService.download",
        side_effect=RuntimeError("boom"),
    ), pytest.raises(RuntimeError):
        DocumentProcessingService().process(doc.id)
    doc.refresh_from_db()
    assert doc.status == DocumentStatus.FAILED
    assert "boom" in doc.error_message


def test_reprocess_replaces_chunks():
    doc = DocumentFactory(status=DocumentStatus.PROCESSING, storage_path="p/x.pdf")
    p1, p2 = _patches()
    with p1, p2:
        DocumentProcessingService().process(doc.id)
        first = DocumentChunk.objects.filter(document=doc).count()
        DocumentProcessingService().process(doc.id, force=True)
    assert DocumentChunk.objects.filter(document=doc).count() == first
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && COMPOSE_PROJECT_NAME=collateralai just pytest collateral_ai/documents/tests/processing/test_pipeline.py -v`
Expected: FAIL (module missing).

- [ ] **Step 3: Implement the pipeline**

`backend/collateral_ai/documents/processing/pipeline.py`:

```python
"""Document processing orchestration: download → extract → chunk → embed → persist."""
from __future__ import annotations

import logging
from typing import Any

from django.db import transaction
from django.utils import timezone

from collateral_ai.documents.models import Document
from collateral_ai.documents.models import DocumentChunk
from collateral_ai.documents.processing.chunking import ChunkingService
from collateral_ai.documents.processing.embeddings import EmbeddingService
from collateral_ai.documents.processing.extraction import PdfExtractionService
from collateral_ai.documents.processing.storage import StorageService
from collateral_ai.documents.statuses import DocumentStatus

logger = logging.getLogger(__name__)


class DocumentProcessingService:
    def __init__(self) -> None:
        self.storage = StorageService()
        self.extractor = PdfExtractionService(storage=self.storage)
        self.chunker = ChunkingService()
        self.embedder = EmbeddingService()

    def process(self, document_id: int, force: bool = False) -> None:
        document = Document.objects.select_related("company").get(id=document_id)
        Document.objects.filter(id=document.id).update(
            status=DocumentStatus.PROCESSING, error_message="", updated_at=timezone.now(),
        )
        try:
            pdf_bytes = self.storage.download(document.storage_path)
            extraction = self.extractor.extract(pdf_bytes=pdf_bytes, document=document)
            payloads = self._build_payloads(document, extraction)
            if not payloads:
                raise ValueError("No extractable content found in PDF.")
            embeddings = self.embedder.embed_documents([p["content"] for p in payloads])
            if len(embeddings) != len(payloads):
                raise ValueError(
                    f"embedding/chunk count mismatch {len(embeddings)}!={len(payloads)}",
                )
            self._save_chunks(document, payloads, embeddings)
            Document.objects.filter(id=document.id).update(
                status=DocumentStatus.PROCESSED,
                page_count=extraction.page_count,
                chunks_count=len(payloads),
                tables_count=len(extraction.tables),
                images_count=len(extraction.images),
                error_message="",
                updated_at=timezone.now(),
            )
        except Exception as exc:
            logger.exception("processing failed document=%s", document_id)
            Document.objects.filter(id=document.id).update(
                status=DocumentStatus.FAILED, error_message=str(exc), updated_at=timezone.now(),
            )
            raise

    def _build_payloads(self, document, extraction) -> list[dict[str, Any]]:
        payloads: list[dict[str, Any]] = []
        base = {
            "document_id": str(document.id),
            "company_id": str(document.company_id),
            "embedding_model": self.embedder.model,
            "embedding_dimensions": self.embedder.dimensions,
            "chunking_version": self.chunker.version,
        }
        for block in extraction.text_blocks:
            for c in self.chunker.chunk_text(block.text, block.page_number):
                payloads.append({
                    "chunk_type": "text", "page_number": c["page_number"],
                    "content": c["content"],
                    "metadata": {**base, "source": "pdf_text", "chunk_index": c["chunk_index"]},
                })
        for table in extraction.tables:
            for c in self.chunker.chunk_text(table.markdown, table.page_number, prefix="Extracted table"):
                payloads.append({
                    "chunk_type": "table", "page_number": c["page_number"],
                    "content": c["content"],
                    "metadata": {**base, "source": "pdf_table", "chunk_index": c["chunk_index"]},
                })
        for i, image in enumerate(extraction.images):
            payloads.append({
                "chunk_type": "image_caption", "page_number": image.page_number,
                "content": image.caption,
                "metadata": {**base, "source": "pdf_image", "chunk_index": i,
                             "image_storage_path": image.storage_path},
            })
        return payloads

    @transaction.atomic
    def _save_chunks(self, document, payloads, embeddings) -> None:
        DocumentChunk.objects.filter(document=document).delete()
        DocumentChunk.objects.bulk_create([
            DocumentChunk(
                document=document, company=document.company,
                chunk_type=p["chunk_type"], page_number=p["page_number"],
                content=p["content"], embedding=e, metadata=p["metadata"],
            )
            for p, e in zip(payloads, embeddings, strict=True)
        ], batch_size=500)
```

- [ ] **Step 4: Run the pipeline test to verify pass**

Run: `cd backend && COMPOSE_PROJECT_NAME=collateralai just pytest collateral_ai/documents/tests/processing/test_pipeline.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Add the management command**

`backend/collateral_ai/documents/management/commands/process_document.py`:

```python
from django.core.management.base import BaseCommand
from django.core.management.base import CommandError

from collateral_ai.documents.models import Document
from collateral_ai.documents.processing.pipeline import DocumentProcessingService


class Command(BaseCommand):
    help = "Process an uploaded PDF: extract, chunk, embed, and store DocumentChunks."

    def add_arguments(self, parser):
        parser.add_argument("--document-id", required=True, type=int)
        parser.add_argument("--force", action="store_true")

    def handle(self, *args, **options):
        document_id = options["document_id"]
        try:
            DocumentProcessingService().process(document_id, force=options["force"])
        except Document.DoesNotExist as exc:
            raise CommandError(f"Document not found: {document_id}") from exc
        except Exception as exc:
            raise CommandError(f"process_document failed for {document_id}: {exc}") from exc
        self.stdout.write(self.style.SUCCESS(f"process_document completed for {document_id}"))
```

- [ ] **Step 6: Wire `complete` to run the pipeline inline (local)**

In `backend/collateral_ai/documents/api/views.py`, replace the `complete` action body so it triggers processing. For Phase 2a this runs **inline** (Phase 2b swaps in the Cloud Run Job trigger behind a setting). Import at top: `from django.core.management import call_command`. New `complete`:

```python
    @extend_schema(request=None, responses={202: OpenApiResponse(response=DocumentSerializer)})
    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None, company_pk=None):
        doc = self.get_object()
        doc.status = DocumentStatus.PROCESSING
        doc.error_message = ""
        doc.save(update_fields=["status", "error_message", "updated_at"])
        # Phase 2a: process inline. Phase 2b routes this to a Cloud Run Job in prod.
        try:
            call_command("process_document", document_id=doc.pk)
        except Exception:  # noqa: BLE001 — pipeline marks the row failed; report 202 either way
            pass
        doc.refresh_from_db()
        return Response(self.get_serializer(doc).data, status=status.HTTP_202_ACCEPTED)
```

- [ ] **Step 7: Update the `complete` API test to assert processing is triggered**

Replace `test_complete_marks_processing_and_returns_202` in `tests/api/test_views.py` with a version that mocks the pipeline (the endpoint no longer just flips status):

```python
def test_complete_triggers_processing_and_returns_202(auth_client):
    doc = DocumentFactory(status=DocumentStatus.PENDING)
    with mock.patch(
        "collateral_ai.documents.api.views.call_command",
    ) as call_command:
        resp = auth_client.post(f"{docs_url(doc.company_id)}{doc.pk}/complete/")
    assert resp.status_code == HTTPStatus.ACCEPTED
    call_command.assert_called_once_with("process_document", document_id=doc.pk)
```

(Keep `test_complete_retries_failed_doc` but likewise wrap it in `mock.patch("...views.call_command")` so it doesn't run the real pipeline.)

- [ ] **Step 8: Run the full documents suite**

Run: `cd backend && COMPOSE_PROJECT_NAME=collateralai just pytest collateral_ai/documents -v`
Expected: PASS (all documents tests, incl. the new processing package).

- [ ] **Step 9: Commit**

```bash
git add backend/collateral_ai/documents/processing/pipeline.py backend/collateral_ai/documents/management backend/collateral_ai/documents/api/views.py backend/collateral_ai/documents/tests/processing/test_pipeline.py backend/collateral_ai/documents/tests/api/test_views.py
git commit -m "feat(documents): processing pipeline + process_document command + inline complete"
```

---

## Self-Review

**Spec coverage (Phase 2a scope):**
- pgvector enablement + local image → Task 1, 2. ✓
- `DocumentChunk` model (embedding 768, company denorm, metadata, cascade) → Task 2. ✓
- Storage / extraction (text+tables+images) / chunking / Vertex embeddings services → Tasks 3–6. ✓
- Pipeline orchestration (status lifecycle, replace-chunks, counts, failure path) + `process_document` command → Task 7. ✓
- `complete` triggers processing (inline for local) → Task 7. ✓
- Settings + deps → Task 1. ✓
- Cloud Run Job / Pulumi / prod trigger / CI job image / prod `CREATE EXTENSION` / retrieval endpoint → **Phase 2b / out of scope.** ✓

**Placeholder scan:** No TBD/TODO; every code step shows complete code. Test PDFs are built by the `make_pdf` fixture (Task 5), so extraction/pipeline tests need no checked-in binary.

**Type consistency:** `DocumentProcessingService.process(document_id, force)`, `EmbeddingService.embed_documents(texts)->list[list[float]]`, `ChunkingService.chunk_text(text, page_number, prefix)`, `StorageService.download/upload`, `PdfExtractionService.extract(pdf_bytes, document)->ExtractionResult` are consistent across the pipeline and tests. `DocumentChunk` field names match Task 2 in the pipeline `bulk_create`. Metadata keys are internal (not asserted cross-task).

**Carried to Phase 2b:** `complete`'s inline `call_command` becomes a setting-gated branch (Cloud Run Job in prod / inline in dev); the pipeline itself is unchanged.
