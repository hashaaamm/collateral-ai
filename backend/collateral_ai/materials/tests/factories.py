from __future__ import annotations

from factory import Faker
from factory import LazyFunction
from factory.django import DjangoModelFactory

from collateral_ai.materials.models import Template


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
            "spec": "1200×630",
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
