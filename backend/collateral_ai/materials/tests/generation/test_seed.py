import pytest

from collateral_ai.documents.models import DocumentChunk
from collateral_ai.materials.generation.eval import seed
from collateral_ai.materials.models import MarketingMaterial


@pytest.mark.django_db
def test_build_golden_materials_creates_varied_examples():
    ids = seed.build_golden_materials()
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
