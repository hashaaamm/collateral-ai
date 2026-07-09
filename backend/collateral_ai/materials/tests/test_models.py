from __future__ import annotations

import pytest

from collateral_ai.materials.models import DEFAULT_TEMPLATE_SLUG
from collateral_ai.materials.models import Template
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
