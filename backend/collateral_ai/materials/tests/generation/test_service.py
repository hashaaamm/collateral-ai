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
    assert material.output_json["image_slots"] == [
        {
            "slot_id": "hero_image",
            "source": "generated_placeholder",
            "description": "",
        },
        {"slot_id": "sender_logo", "source": "sender", "description": ""},
    ]
    assert GenerationSource.objects.filter(material=material).count() == 1


def _mock_service(*, valid: bool = True) -> tuple[MaterialGenerationService, MagicMock]:
    """Build a service with injected mocks against the new __init__ signature."""
    fake_model = MagicMock()
    if valid:
        fake_model.generate_structured.return_value = _valid_output()
    fake_embedder = MagicMock()
    fake_embedder.embed_query.return_value = [0.0] * 768
    service = MaterialGenerationService(embedder=fake_embedder, model=fake_model)
    return service, fake_model


@pytest.mark.django_db
@pytest.mark.parametrize(
    "status",
    [GenerationStatus.COMPLETED, GenerationStatus.PROCESSING],
)
def test_skips_without_force_and_leaves_status(status):
    material = MarketingMaterialFactory(generation_status=status)
    service, fake_model = _mock_service()

    assert service.generate(material.pk) is False

    material.refresh_from_db()
    assert material.generation_status == status  # unchanged
    fake_model.generate_structured.assert_not_called()


@pytest.mark.django_db
def test_force_reruns_completed_material():
    material = MarketingMaterialFactory(generation_status=GenerationStatus.COMPLETED)
    DocumentChunkFactory(company=material.sender_company)
    DocumentChunkFactory(company=material.receiver_company)
    service, _ = _mock_service()

    assert service.generate(material.pk, force=True) is True

    material.refresh_from_db()
    assert material.generation_status == GenerationStatus.COMPLETED


@pytest.mark.django_db
def test_empty_chunks_marks_failed_and_reraises():
    # Sender company has no chunks: the retrieve node raises ValueError, which
    # propagates through generate()'s try/except → FAILED + re-raise.
    material = MarketingMaterialFactory(generation_status=GenerationStatus.QUEUED)
    service, _ = _mock_service()

    with pytest.raises(ValueError, match="No processed document chunks"):
        service.generate(material.pk)

    material.refresh_from_db()
    assert material.generation_status == GenerationStatus.FAILED
    assert "sender" in material.error_message
