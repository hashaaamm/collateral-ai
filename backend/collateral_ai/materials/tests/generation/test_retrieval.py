from __future__ import annotations

import pytest

from collateral_ai.companies.tests.factories import CompanyFactory
from collateral_ai.documents.tests.factories import DocumentChunkFactory
from collateral_ai.documents.tests.factories import DocumentFactory
from collateral_ai.materials.generation.retrieval import RetrievalService
from collateral_ai.materials.statuses import SourceRole

pytestmark = pytest.mark.django_db


def embedding(first: float) -> list[float]:
    vec = [0.0] * 768
    vec[0] = first
    return vec


def test_retrieve_orders_by_cosine_distance_and_labels_sources():
    company = CompanyFactory()
    doc = DocumentFactory(company=company, file_name="brochure.pdf")
    far = DocumentChunkFactory(document=doc, content="far", embedding=embedding(-1.0))
    near = DocumentChunkFactory(
        document=doc,
        content="near",
        page_number=3,
        embedding=embedding(1.0),
    )
    results = RetrievalService().retrieve(
        company_id=company.pk,
        query_embedding=embedding(1.0),
        source_role=SourceRole.SENDER,
        source_prefix="SENDER_SOURCE",
        top_k=2,
    )
    assert [r.chunk_id for r in results] == [near.pk, far.pk]
    first = results[0]
    assert first.source_id == "SENDER_SOURCE_1"
    assert first.file_name == "brochure.pdf"
    assert first.page_number == 3
    assert first.source_role == SourceRole.SENDER
    assert first.to_prompt_dict() == {
        "source_id": "SENDER_SOURCE_1",
        "file_name": "brochure.pdf",
        "page_number": 3,
        "chunk_type": "text",
        "content": "near",
    }


def test_retrieve_scopes_to_company_and_respects_top_k():
    company, other = CompanyFactory(), CompanyFactory()
    doc = DocumentFactory(company=company)
    for i in range(3):
        DocumentChunkFactory(document=doc, content=f"c{i}", embedding=embedding(0.5))
    DocumentChunkFactory(
        document=DocumentFactory(company=other),
        embedding=embedding(1.0),
    )
    results = RetrievalService().retrieve(
        company_id=company.pk,
        query_embedding=embedding(1.0),
        source_role=SourceRole.RECEIVER,
        source_prefix="RECEIVER_SOURCE",
        top_k=2,
    )
    assert len(results) == 2
    assert all(r.company_id == company.pk for r in results)


def test_retrieve_returns_empty_for_company_without_chunks():
    company = CompanyFactory()
    results = RetrievalService().retrieve(
        company_id=company.pk,
        query_embedding=embedding(1.0),
        source_role=SourceRole.SENDER,
        source_prefix="SENDER_SOURCE",
        top_k=8,
    )
    assert results == []


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
