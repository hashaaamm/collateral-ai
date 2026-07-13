from unittest.mock import MagicMock

import pytest

from collateral_ai.documents.tests.factories import DocumentChunkFactory
from collateral_ai.materials.management.commands import run_eval
from collateral_ai.materials.statuses import GenerationStatus
from collateral_ai.materials.tests.factories import MarketingMaterialFactory


def _valid_output():
    return {
        "article": {
            "headline": "Short",
            "subheadline": "Sub",
            "body_sections": [
                {"title": "T", "text": "b"},
                {"title": "T2", "text": "b2"},
            ],
            "cta": "Act",
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
def test_evaluate_one_returns_scored_record(monkeypatch):
    material = MarketingMaterialFactory(generation_status=GenerationStatus.QUEUED)
    DocumentChunkFactory(company=material.sender_company)
    DocumentChunkFactory(company=material.receiver_company)

    fake_model = MagicMock()
    fake_model.generate_structured.return_value = _valid_output()
    monkeypatch.setattr(
        "collateral_ai.materials.generation.service.GenerationModel",
        lambda: fake_model,
    )
    monkeypatch.setattr(
        "collateral_ai.materials.generation.service.EmbeddingService",
        _fake_embedder,
    )

    record = run_eval.evaluate_one(material.pk, judge=lambda prompt: "0.9")

    assert record["schema_valid"] is True
    assert record["sources_grounded"] is True
    assert record["groundedness"] == 0.9


def _fake_embedder():
    e = MagicMock()
    e.embed_query.return_value = [0.0] * 768
    return e
