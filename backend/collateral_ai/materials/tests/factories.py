from __future__ import annotations

from factory import Faker
from factory import LazyFunction
from factory import SubFactory
from factory.django import DjangoModelFactory

from collateral_ai.companies.tests.factories import CompanyFactory
from collateral_ai.documents.tests.factories import DocumentFactory
from collateral_ai.materials.models import GenerationSource
from collateral_ai.materials.models import MarketingMaterial
from collateral_ai.materials.models import Template
from collateral_ai.materials.statuses import SourceRole


def default_constraints() -> dict:
    return {
        "headline_max_words": 10,
        "subheadline_max_words": 22,
        "body_section_count": 2,
        "body_section_max_words": 80,
        "cta_max_words": 15,
    }


def default_image_slots() -> list[dict]:
    return [
        {
            "slot_id": "hero_image",
            "label": "Hero image",
            "spec": "1200×630",  # noqa: RUF001
            "source": "generated_placeholder",
        },
        {
            "slot_id": "sender_logo",
            "label": "Sender logo",
            "spec": "SVG/PNG",
            "source": "sender",
        },
    ]


class TemplateFactory(DjangoModelFactory[Template]):
    name = Faker("catch_phrase")
    constraints = LazyFunction(default_constraints)
    image_slots = LazyFunction(default_image_slots)
    theme = LazyFunction(
        lambda: {"primary_color": "#5b5bd6", "accent_color": "#0f172a"},
    )

    class Meta:
        model = Template


class MarketingMaterialFactory(DjangoModelFactory[MarketingMaterial]):
    title = Faker("sentence", nb_words=4)
    sender_company = SubFactory(CompanyFactory)
    receiver_company = SubFactory(CompanyFactory)
    template = SubFactory(TemplateFactory)
    prompt = Faker("paragraph")

    class Meta:
        model = MarketingMaterial


class GenerationSourceFactory(DjangoModelFactory[GenerationSource]):
    material = SubFactory(MarketingMaterialFactory)
    document = SubFactory(DocumentFactory)
    source_role = SourceRole.SENDER
    page_number = 1
    snippet = "quoted snippet"
    used_fact = "a fact that was used"
    relevance_score = 0.12

    class Meta:
        model = GenerationSource

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        # company defaults to the document's company when not given
        kwargs.setdefault("company", kwargs["document"].company)
        return super()._create(model_class, *args, **kwargs)
