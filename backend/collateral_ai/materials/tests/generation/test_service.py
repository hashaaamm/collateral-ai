from unittest.mock import MagicMock

import pytest

from collateral_ai.documents.tests.factories import DocumentChunkFactory
from collateral_ai.materials.generation.service import MaterialGenerationService
from collateral_ai.materials.models import GenerationSource
from collateral_ai.materials.statuses import GenerationStatus
from collateral_ai.materials.tests.factories import MarketingMaterialFactory


def _valid_output():
    return {
        "article": {
            "headline": "Short headline",
            "subheadline": "Sub",
            "body_sections": [
                {"title": "T", "text": "body text"},
                {"title": "T2", "text": "body text two"},
            ],
            "cta": "Act now",
        },
        "image_slots": [
            {
                "slot_id": "hero_image",
                "description": "d",
                "source": "generated_placeholder",
            },
            {"slot_id": "sender_logo", "description": "d", "source": "sender"},
        ],
        "source_references": [{"source_id": "SENDER_SOURCE_1", "used_fact": "f"}],
    }


@pytest.mark.django_db
def test_generate_completes_and_saves(monkeypatch):
    material = MarketingMaterialFactory(generation_status=GenerationStatus.QUEUED)
    DocumentChunkFactory(company=material.sender_company)
    DocumentChunkFactory(company=material.receiver_company)

    fake_model = MagicMock()
    fake_model.generate_structured.return_value = _valid_output()
    monkeypatch.setattr(
        "collateral_ai.materials.generation.service.GenerationModel",
        lambda: fake_model,
    )
    fake_embedder = MagicMock()
    fake_embedder.embed_query.return_value = [0.0] * 768
    monkeypatch.setattr(
        "collateral_ai.materials.generation.service.EmbeddingService",
        lambda: fake_embedder,
    )

    result = MaterialGenerationService().generate(material.pk)

    assert result is True
    material.refresh_from_db()
    assert material.generation_status == GenerationStatus.COMPLETED
    assert material.output_json["article"]["headline"] == "Short headline"
    assert GenerationSource.objects.filter(material=material).count() == 1
