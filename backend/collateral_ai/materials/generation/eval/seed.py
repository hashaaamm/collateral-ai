"""Self-generated golden examples for the material-gen eval dataset.

Builds varied templates (different section counts / image slots) plus an
adversarial sparse-context case. Uses the same factories the tests use.
"""

from __future__ import annotations

from collateral_ai.companies.tests.factories import CompanyFactory
from collateral_ai.documents.tests.factories import DocumentChunkFactory
from collateral_ai.materials.tests.factories import MarketingMaterialFactory
from collateral_ai.materials.tests.factories import TemplateFactory

_SENDER_FACTS = [
    "Acme ships a real-time fraud API with 40ms p99 latency.",
    "Acme's SOC2 Type II covers all data-plane services.",
    "Acme integrates with Stripe, Adyen, and Braintree out of the box.",
]
_RECEIVER_FACTS = [
    "Globex processes 2M card transactions per day across EMEA.",
    "Globex's current fraud tool has a 4% false-positive rate.",
    "Globex is expanding into APAC in the next fiscal year.",
]


def _template_two_sections():
    return TemplateFactory(name="Newsletter two sections")


def _template_three_sections_no_slots():
    return TemplateFactory(
        name="Longform three sections",
        constraints={
            "headline_max_words": 12, "subheadline_max_words": 24,
            "body_section_count": 3, "body_section_max_words": 90, "cta_max_words": 12,
        },
        image_slots=[],
    )


def _seed_chunks(company, facts):
    for i, fact in enumerate(facts, start=1):
        DocumentChunkFactory(company=company, content=fact, page_number=i)


def build_golden_materials() -> list[int]:
    ids: list[int] = []
    templates = [_template_two_sections(), _template_three_sections_no_slots()]

    for idx in range(6):
        template = templates[idx % len(templates)]
        sender = CompanyFactory(name=f"Acme {idx}")
        receiver = CompanyFactory(name=f"Globex {idx}")
        _seed_chunks(sender, _SENDER_FACTS)
        _seed_chunks(receiver, _RECEIVER_FACTS)
        material = MarketingMaterialFactory(
            title=f"Golden {idx}",
            sender_company=sender,
            receiver_company=receiver,
            template=template,
            prompt="Introduce our fraud API to the receiver's pain points.",
        )
        ids.append(material.pk)

    # Adversarial: sparse context (receiver has no chunks) to test grounding.
    sender = CompanyFactory(name="Acme sparse")
    receiver = CompanyFactory(name="Globex sparse")
    _seed_chunks(sender, _SENDER_FACTS[:1])
    material = MarketingMaterialFactory(
        title="Golden sparse adversarial",
        sender_company=sender,
        receiver_company=receiver,
        template=templates[0],
        prompt="Pitch with minimal context.",
    )
    ids.append(material.pk)
    return ids
