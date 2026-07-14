from __future__ import annotations

from unittest import mock

import pytest

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
    with (
        mock.patch(
            "collateral_ai.documents.processing.pipeline.StorageService.download",
            side_effect=RuntimeError("boom"),
        ),
        pytest.raises(RuntimeError),
    ):
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
        # `force` is a placeholder in Phase 2a (process() has no
        # skip-if-processed guard yet), so this reprocess would replace chunks
        # identically with or without it; asserting the count is stable proves
        # the delete-then-recreate replacement, not force-specific behavior.
        DocumentProcessingService().process(doc.id, force=True)
    assert DocumentChunk.objects.filter(document=doc).count() == first


def test_chunks_persist_word_offsets():
    doc = DocumentFactory(status=DocumentStatus.PROCESSING, storage_path="p/x.pdf")
    p1, p2 = _patches()
    with p1, p2:
        DocumentProcessingService().process(doc.id)
    chunk = DocumentChunk.objects.filter(document=doc, chunk_type="text").first()
    assert chunk is not None
    assert chunk.metadata["word_start"] == 0
    assert chunk.metadata["word_end"] > 0
