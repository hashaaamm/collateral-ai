from __future__ import annotations

from io import StringIO
from unittest import mock

import pytest
from django.core.management import call_command

from collateral_ai.documents.statuses import DocumentStatus
from collateral_ai.documents.tests.factories import DocumentChunkFactory
from collateral_ai.documents.tests.factories import DocumentFactory
from collateral_ai.materials.generation.service import MaterialGenerationService
from collateral_ai.materials.models import GenerationSource
from collateral_ai.materials.statuses import GenerationStatus
from collateral_ai.materials.statuses import ReviewStatus
from collateral_ai.materials.tests.factories import MarketingMaterialFactory

pytestmark = pytest.mark.django_db


def material_with_chunks():
    material = MarketingMaterialFactory()
    for company in (material.sender_company, material.receiver_company):
        doc = DocumentFactory(company=company, status=DocumentStatus.PROCESSED)
        DocumentChunkFactory(document=doc, content=f"facts about {company.name}")
    return material


def valid_output() -> dict:
    return {
        "article": {
            "headline": "Smarter Warehouses, Powered by AI",
            "subheadline": "Predictive planning for modern logistics operations",
            "body_sections": [
                {"title": "The Challenge", "text": "Manual planning wastes hours."},
                {"title": "The Solution", "text": "Predictive AI removes guesswork."},
            ],
            "cta": "Book a 20-minute assessment",
        },
        "image_slots": [
            {
                "slot_id": "hero_image",
                "description": "warehouse",
                "source": "generated_placeholder",
            },
            {"slot_id": "sender_logo", "description": "logo", "source": "sender"},
        ],
        "source_references": [
            {"source_id": "SENDER_SOURCE_1", "used_fact": "sender fact"},
            {"source_id": "RECEIVER_SOURCE_1", "used_fact": "receiver fact"},
        ],
    }


def make_service(outputs: list[dict]) -> MaterialGenerationService:
    embedder = mock.Mock()
    embedder.embed_query.return_value = [0.0] * 768
    client = mock.Mock()
    client.generate_json.side_effect = list(outputs)
    repairer = mock.Mock()
    return MaterialGenerationService(
        embedder=embedder,
        client=client,
        repairer=repairer,
    )


def test_happy_path_completes_and_saves_sources():
    material = material_with_chunks()
    service = make_service([valid_output()])
    assert service.generate(material.pk) is True
    material.refresh_from_db()
    assert material.generation_status == GenerationStatus.COMPLETED
    assert material.review_status == ReviewStatus.PENDING  # untouched
    assert material.output_json["template_id"] == material.template.slug
    assert material.output_json["theme"] == material.template.theme
    assert material.validation_result == {"is_valid": True, "errors": []}
    assert material.completed_at is not None
    assert material.retrieved_context["sender_context"]
    sources = list(GenerationSource.objects.filter(material=material))
    assert {s.source_role for s in sources} == {"sender", "receiver"}
    assert sources[0].snippet


def test_repair_loop_recovers_invalid_output():
    material = material_with_chunks()
    bad = valid_output()
    bad["article"]["headline"] = " ".join(["word"] * 30)  # violates limit of 10
    service = make_service([bad])
    service.repairer.repair.return_value = valid_output()
    assert service.generate(material.pk) is True
    material.refresh_from_db()
    assert material.generation_status == GenerationStatus.COMPLETED
    service.repairer.repair.assert_called_once()


def test_validation_exhausted_fails_but_persists_output():
    material = material_with_chunks()
    bad = valid_output()
    bad["article"]["headline"] = " ".join(["word"] * 30)
    service = make_service([bad])
    service.repairer.repair.return_value = bad  # never gets better
    with pytest.raises(ValueError, match="failed validation"):
        service.generate(material.pk)
    material.refresh_from_db()
    assert material.generation_status == GenerationStatus.FAILED
    assert material.output_json is not None
    assert material.validation_result["is_valid"] is False
    assert not GenerationSource.objects.filter(material=material).exists()
    assert service.repairer.repair.call_count == 2  # MATERIAL_MAX_REPAIR_ATTEMPTS


def test_no_context_fails_with_actionable_error():
    material = MarketingMaterialFactory()  # companies without chunks
    service = make_service([valid_output()])
    with pytest.raises(ValueError, match="No processed document chunks"):
        service.generate(material.pk)
    material.refresh_from_db()
    assert material.generation_status == GenerationStatus.FAILED
    assert "sender" in material.error_message


def test_skips_completed_and_processing_without_force():
    for status_value in (GenerationStatus.COMPLETED, GenerationStatus.PROCESSING):
        material = MarketingMaterialFactory(generation_status=status_value)
        service = make_service([valid_output()])
        assert service.generate(material.pk) is False
        material.refresh_from_db()
        assert material.generation_status == status_value  # unchanged


def test_force_reruns_completed_material():
    material = material_with_chunks()
    material.generation_status = GenerationStatus.COMPLETED
    material.save(update_fields=["generation_status"])
    service = make_service([valid_output()])
    assert service.generate(material.pk, force=True) is True


def test_command_skip_exits_zero():
    material = MarketingMaterialFactory(generation_status=GenerationStatus.PROCESSING)
    out = StringIO()
    with mock.patch(
        "collateral_ai.materials.management.commands.generate_material"
        ".MaterialGenerationService",
    ) as service_cls:
        service_cls.return_value.generate.return_value = False
        call_command("generate_material", material_id=material.pk, stdout=out)
    assert "skipped" in out.getvalue()


def test_stamp_injects_cta_url_when_link_present():
    from collateral_ai.materials.generation.service import MaterialGenerationService
    from collateral_ai.materials.tests.factories import (
        MarketingMaterialFactory,
        TemplateFactory,
    )

    template = TemplateFactory()
    material = MarketingMaterialFactory(template=template, cta_link="https://example.com/demo")
    service = MaterialGenerationService.__new__(MaterialGenerationService)
    output = {"article": {"cta": "Book a demo"}}

    stamped = service._stamp(output, template, material)

    assert stamped["article"]["cta_url"] == "https://example.com/demo"


def test_stamp_omits_cta_url_when_link_blank():
    from collateral_ai.materials.generation.service import MaterialGenerationService
    from collateral_ai.materials.tests.factories import (
        MarketingMaterialFactory,
        TemplateFactory,
    )

    template = TemplateFactory()
    material = MarketingMaterialFactory(template=template, cta_link="")
    service = MaterialGenerationService.__new__(MaterialGenerationService)
    output = {"article": {"cta": "Book a demo"}}

    stamped = service._stamp(output, template, material)

    assert "cta_url" not in stamped["article"]
