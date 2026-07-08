"""Document processing orchestration: download → extract → chunk → embed → persist."""
from __future__ import annotations

import logging
import time
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
        t0 = time.monotonic()
        document = Document.objects.select_related("company").get(id=document_id)
        Document.objects.filter(id=document.id).update(
            status=DocumentStatus.PROCESSING, error_message="", updated_at=timezone.now(),
        )
        logger.info("timing: db connect+fetch %.2fs (document=%s)", time.monotonic() - t0, document_id)
        try:
            t = time.monotonic()
            pdf_bytes = self.storage.download(document.storage_path)
            logger.info("timing: gcs download %.2fs (%d bytes)", time.monotonic() - t, len(pdf_bytes))
            t = time.monotonic()
            extraction = self.extractor.extract(pdf_bytes=pdf_bytes, document=document)
            logger.info("timing: extraction %.2fs (pages=%d)", time.monotonic() - t, extraction.page_count)
            payloads = self._build_payloads(document, extraction)
            if not payloads:
                raise ValueError("No extractable content found in PDF.")
            t = time.monotonic()
            embeddings = self.embedder.embed_documents([p["content"] for p in payloads])
            logger.info("timing: embeddings %.2fs (chunks=%d)", time.monotonic() - t, len(payloads))
            if len(embeddings) != len(payloads):
                raise ValueError(
                    f"embedding/chunk count mismatch {len(embeddings)}!={len(payloads)}",
                )
            t = time.monotonic()
            self._save_chunks(document, payloads, embeddings)
            logger.info("timing: save chunks %.2fs", time.monotonic() - t)
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
