import pytest

from collateral_ai.documents.models import DocumentChunk
from collateral_ai.materials.generation.eval import seed
from collateral_ai.materials.models import MarketingMaterial


class _FakeEmbedder:
    """Deterministic, non-zero, text-varying fake — no live Vertex calls."""

    def embed_query(self, text: str) -> list[float]:
        base = (hash(text) % 1000) / 1000.0 or 0.001
        return [base + (i % 7) * 1e-4 for i in range(768)]


@pytest.mark.django_db
def test_build_golden_materials_creates_varied_examples():
    ids = seed.build_golden_materials(embedder=_FakeEmbedder())
    assert len(ids) >= 6
    materials = MarketingMaterial.objects.filter(pk__in=ids)
    assert materials.count() == len(ids)
    # every material's companies have at least one chunk (except the adversarial one)
    for material in materials:
        sender_chunks = DocumentChunk.objects.filter(company=material.sender_company)
        assert sender_chunks.exists() or "sparse" in material.title.lower()
    # at least two distinct templates for coverage
    template_ids = {m.template_id for m in materials}
    assert len(template_ids) >= 2


@pytest.mark.django_db
def test_build_golden_materials_uses_real_nonzero_embeddings():
    seed.build_golden_materials(embedder=_FakeEmbedder())
    chunk = DocumentChunk.objects.first()
    assert chunk is not None
    assert any(value != 0.0 for value in chunk.embedding)


@pytest.mark.django_db
def test_build_hard_materials_splits_claims_from_qualifiers():
    entries = seed.build_hard_materials(embedder=_FakeEmbedder())
    assert entries
    assert all(entry["expected_facts"] for entry in entries)
    material = MarketingMaterial.objects.get(pk=entries[0]["material_id"])
    chunks = list(
        DocumentChunk.objects.filter(company=material.sender_company).order_by("pk"),
    )
    # More chunks than the eval's top_k=3, so retrieval must actually select.
    assert len(chunks) >= 6
    assert all("word_start" in (c.metadata or {}) for c in chunks)
    claim = next(c for c in chunks if "sub-second query responses" in c.content)
    qualifier = next(c for c in chunks if "180 milliseconds" in c.content)
    assert claim.pk != qualifier.pk
    assert claim.document_id == qualifier.document_id
    assert claim.document.summary != ""


@pytest.mark.django_db
def test_build_golden_materials_groups_chunks_and_sets_summaries():
    seed.build_golden_materials(embedder=_FakeEmbedder())
    material = MarketingMaterial.objects.exclude(title__icontains="sparse").first()
    chunks = DocumentChunk.objects.filter(company=material.sender_company)
    assert chunks.count() >= 3
    assert len({c.document_id for c in chunks}) == 1
    assert chunks.first().document.summary != ""
