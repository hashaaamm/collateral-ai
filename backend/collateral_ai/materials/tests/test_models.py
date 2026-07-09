from __future__ import annotations

import pytest
from django.db.models import ProtectedError

from collateral_ai.documents.tests.factories import DocumentChunkFactory
from collateral_ai.materials.models import DEFAULT_TEMPLATE_SLUG
from collateral_ai.materials.models import GenerationSource
from collateral_ai.materials.models import Template
from collateral_ai.materials.statuses import GenerationStatus
from collateral_ai.materials.statuses import ReviewStatus
from collateral_ai.materials.tests.factories import GenerationSourceFactory
from collateral_ai.materials.tests.factories import MarketingMaterialFactory
from collateral_ai.materials.tests.factories import TemplateFactory

pytestmark = pytest.mark.django_db


def test_default_template_is_seeded():
    seeded = Template.objects.get(slug=DEFAULT_TEMPLATE_SLUG)
    assert seeded.name == "Newsletter Article"
    assert seeded.constraints["body_section_count"] == 2
    assert [s["slot_id"] for s in seeded.image_slots] == ["hero_image", "sender_logo"]
    assert seeded.theme == {"primary_color": "#5b5bd6", "accent_color": "#0f172a"}
    assert seeded.is_active


def test_slug_is_generated_snake_case_and_unique():
    a = TemplateFactory(name="Product Spotlight V1")
    b = TemplateFactory(name="Product Spotlight V1")
    assert a.slug == "product_spotlight_v1"
    assert b.slug == "product_spotlight_v1_2"


def test_ordering_is_oldest_first_with_seed_first():
    TemplateFactory(name="Later Template")
    slugs = list(Template.objects.values_list("slug", flat=True))
    assert slugs[0] == DEFAULT_TEMPLATE_SLUG


def test_material_defaults():
    material = MarketingMaterialFactory()
    assert material.generation_status == GenerationStatus.QUEUED
    assert material.review_status == ReviewStatus.PENDING
    assert material.tone == "professional"
    assert material.cta_style == "soft"
    assert material.language == "english"
    assert material.output_json is None
    assert material.completed_at is None


def test_template_delete_is_protected_by_materials():
    material = MarketingMaterialFactory()
    with pytest.raises(ProtectedError):
        material.template.delete()


def test_source_chunk_nulls_on_chunk_delete():
    chunk = DocumentChunkFactory()
    source = GenerationSourceFactory(
        document=chunk.document,
        chunk=chunk,
        page_number=chunk.page_number,
    )
    chunk.delete()
    source.refresh_from_db()
    assert source.chunk is None
    assert source.page_number == 1  # denormalized value survives


def test_material_delete_cascades_sources():
    source = GenerationSourceFactory()
    source.material.delete()

    assert not GenerationSource.objects.filter(pk=source.pk).exists()


def test_cta_link_defaults_blank():
    material = MarketingMaterialFactory()
    assert material.cta_link == ""
