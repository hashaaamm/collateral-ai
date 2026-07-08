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
