"""Document processing orchestration: download → extract → chunk → embed → persist.

`process()` is the flow, readable top to bottom; each private step owns its own
work, logging, and timing. This service owns the Document status state machine
(PROCESSING → PROCESSED / FAILED); sub-services own one capability each.
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING
from typing import Any

from django.db import transaction
from django.utils import timezone

from collateral_ai.documents.models import Document
from collateral_ai.documents.models import DocumentChunk
from collateral_ai.documents.processing.chunking import ChunkingService
from collateral_ai.documents.processing.embeddings import EmbeddingService
from collateral_ai.documents.processing.extraction import PdfExtractionService
from collateral_ai.documents.processing.storage import StorageService
from collateral_ai.documents.processing.summarization import DocumentSummaryService
from collateral_ai.documents.statuses import DocumentStatus

if TYPE_CHECKING:
    from collections.abc import Iterator

    from collateral_ai.documents.processing.extraction import ExtractionResult

logger = logging.getLogger(__name__)


@contextmanager
def _timed(label: str) -> Iterator[None]:
    """Log `timing: <label> <seconds>` around a step (always, even on failure)."""
    t = time.monotonic()
    try:
        yield
    finally:
        logger.info("timing: %s %.2fs", label, time.monotonic() - t)


@dataclass(frozen=True)
class ChunkPayload:
    """One embeddable unit: a text chunk, table chunk, or image caption."""

    chunk_type: str
    page_number: int
    content: str
    metadata: dict[str, Any]


class DocumentProcessingService:
    def __init__(self) -> None:
        self.storage = StorageService()
        self.extractor = PdfExtractionService(storage=self.storage)
        self.chunker = ChunkingService()
        self.embedder = EmbeddingService()
        self.summarizer = DocumentSummaryService()

    def process(self, document_id: int, *, force: bool = False) -> None:
        document = self._start(document_id)
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

    def _start(self, document_id: int) -> Document:
        """Fetch + mark PROCESSING. DoesNotExist propagates (no FAILED write)."""
        t0 = time.monotonic()
        document = Document.objects.select_related("company").get(id=document_id)
        Document.objects.filter(id=document.id).update(
            status=DocumentStatus.PROCESSING,
            error_message="",
            updated_at=timezone.now(),
        )
        logger.info(
            "timing: db connect+fetch %.2fs (document=%s)",
            time.monotonic() - t0,
            document_id,
        )
        return document

    def _download(self, document: Document) -> bytes:
        t = time.monotonic()
        pdf_bytes = self.storage.download(document.storage_path)
        logger.info(
            "timing: gcs download %.2fs (%d bytes)",
            time.monotonic() - t,
            len(pdf_bytes),
        )
        return pdf_bytes

    def _extract(self, document: Document, pdf_bytes: bytes) -> ExtractionResult:
        t = time.monotonic()
        extraction = self.extractor.extract(pdf_bytes=pdf_bytes, document=document)
        logger.info(
            "timing: extraction %.2fs (pages=%d)",
            time.monotonic() - t,
            extraction.page_count,
        )
        return extraction

    def _build_payloads(
        self,
        document: Document,
        extraction: ExtractionResult,
    ) -> list[ChunkPayload]:
        base = {
            "document_id": str(document.id),
            "company_id": str(document.company_id),
            "embedding_model": self.embedder.model,
            "embedding_dimensions": self.embedder.dimensions,
            "chunking_version": self.chunker.version,
        }
        payloads = [
            *self._text_payloads(base, extraction),
            *self._table_payloads(base, extraction),
            *self._image_payloads(base, extraction),
        ]
        if not payloads:
            msg = "No extractable content found in PDF."
            raise ValueError(msg)
        return payloads

    def _text_payloads(
        self,
        base: dict[str, Any],
        extraction: ExtractionResult,
    ) -> list[ChunkPayload]:
        return [
            ChunkPayload(
                chunk_type="text",
                page_number=c["page_number"],
                content=c["content"],
                metadata={
                    **base,
                    "source": "pdf_text",
                    "chunk_index": c["chunk_index"],
                    "word_start": c["word_start"],
                    "word_end": c["word_end"],
                },
            )
            for block in extraction.text_blocks
            for c in self.chunker.chunk_text(block.text, block.page_number)
        ]

    def _table_payloads(
        self,
        base: dict[str, Any],
        extraction: ExtractionResult,
    ) -> list[ChunkPayload]:
        return [
            ChunkPayload(
                chunk_type="table",
                page_number=c["page_number"],
                content=c["content"],
                metadata={
                    **base,
                    "source": "pdf_table",
                    "chunk_index": c["chunk_index"],
                    "word_start": c["word_start"],
                    "word_end": c["word_end"],
                },
            )
            for table in extraction.tables
            for c in self.chunker.chunk_text(
                table.markdown,
                table.page_number,
                prefix="Extracted table",
            )
        ]

    def _image_payloads(
        self,
        base: dict[str, Any],
        extraction: ExtractionResult,
    ) -> list[ChunkPayload]:
        return [
            ChunkPayload(
                chunk_type="image_caption",
                page_number=image.page_number,
                content=image.caption,
                metadata={
                    **base,
                    "source": "pdf_image",
                    "chunk_index": i,
                    "image_storage_path": image.storage_path,
                },
            )
            for i, image in enumerate(extraction.images)
        ]

    def _embed(self, payloads: list[ChunkPayload]) -> list[list[float]]:
        t = time.monotonic()
        embeddings = self.embedder.embed_documents([p.content for p in payloads])
        logger.info(
            "timing: embeddings %.2fs (chunks=%d)",
            time.monotonic() - t,
            len(payloads),
        )
        if len(embeddings) != len(payloads):
            msg = f"embedding/chunk count mismatch {len(embeddings)}!={len(payloads)}"
            raise ValueError(msg)
        return embeddings

    def _save_chunks(
        self,
        document: Document,
        payloads: list[ChunkPayload],
        embeddings: list[list[float]],
    ) -> None:
        with _timed("save chunks"), transaction.atomic():
            DocumentChunk.objects.filter(document=document).delete()
            DocumentChunk.objects.bulk_create(
                [
                    DocumentChunk(
                        document=document,
                        company=document.company,
                        chunk_type=p.chunk_type,
                        page_number=p.page_number,
                        content=p.content,
                        embedding=e,
                        metadata=p.metadata,
                    )
                    for p, e in zip(payloads, embeddings, strict=True)
                ],
                batch_size=500,
            )

    def _summarize(self, document_id: int, payloads: list[ChunkPayload]) -> str:
        """Best-effort: a missing summary must never fail ingestion (spec §5.2)."""
        try:
            with _timed("summary"):
                return self.summarizer.summarize([p.content for p in payloads])
        except Exception:  # noqa: BLE001 — any summarizer error degrades to no summary
            logger.warning(
                "summary generation failed document=%s; continuing without one",
                document_id,
                exc_info=True,
            )
            return ""

    def _finish(
        self,
        document: Document,
        extraction: ExtractionResult,
        payloads: list[ChunkPayload],
        summary: str,
    ) -> None:
        Document.objects.filter(id=document.id).update(
            status=DocumentStatus.PROCESSED,
            summary=summary,
            page_count=extraction.page_count,
            chunks_count=len(payloads),
            tables_count=len(extraction.tables),
            images_count=len(extraction.images),
            error_message="",
            updated_at=timezone.now(),
        )

    def _fail(self, document: Document, exc: Exception) -> None:
        logger.exception("processing failed document=%s", document.id)
        Document.objects.filter(id=document.id).update(
            status=DocumentStatus.FAILED,
            error_message=str(exc),
            updated_at=timezone.now(),
        )
