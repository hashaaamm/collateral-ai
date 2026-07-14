"""Self-generated golden examples for the material-gen eval dataset.

Builds varied templates (different section counts / image slots) across
three distinct, substantive sender/receiver company pairs, plus an
adversarial sparse-context case. Golden chunks carry REAL embeddings
(computed via EmbeddingService) so retrieval against them is meaningful
instead of matching against zero vectors.
"""

from __future__ import annotations

from collateral_ai.companies.tests.factories import CompanyFactory
from collateral_ai.documents.processing.embeddings import EmbeddingService
from collateral_ai.documents.tests.factories import DocumentChunkFactory
from collateral_ai.materials.tests.factories import MarketingMaterialFactory
from collateral_ai.materials.tests.factories import TemplateFactory

_PAIRS = [
    {
        "sender": "Sentinel Pay",
        "receiver": "Meridian Retail",
        "sender_facts": [
            "Sentinel Pay's fraud API returns a risk score in 38ms at p99.",
            "Sentinel Pay is SOC 2 Type II and PCI-DSS Level 1 certified.",
            "Sentinel Pay ships prebuilt connectors for Stripe, Adyen, and Braintree.",
            "Sentinel Pay's model retrains nightly on 4 billion transactions.",
        ],
        "receiver_facts": [
            "Meridian Retail processes 2.1M card transactions per day across EMEA.",
            "Meridian's fraud tool has a 4.2% false-positive rate costing $3M/yr "
            "in declined orders.",
            "Meridian is expanding into APAC in Q3 and needs multi-region "
            "latency under 50ms.",
        ],
    },
    {
        "sender": "Nimbus Analytics",
        "receiver": "Harborview Logistics",
        "sender_facts": [
            "Nimbus's columnar engine runs analytical queries 12x faster than "
            "Postgres at TB scale.",
            "Nimbus supports zero-copy cloning so teams branch a 10TB warehouse "
            "in seconds.",
            "Nimbus bills per-second of compute with autosuspend after 60s idle.",
        ],
        "receiver_facts": [
            "Harborview runs a 6-hour nightly ETL that delays same-day shipping "
            "decisions.",
            "Harborview's analysts wait 40 seconds per dashboard query at peak.",
            "Harborview wants sub-second dashboards for 500 warehouse managers.",
        ],
    },
    {
        "sender": "Pulse Observability",
        "receiver": "Cobalt Bank",
        "sender_facts": [
            "Pulse ingests 5M spans per second with 15-second end-to-end trace "
            "latency.",
            "Pulse's anomaly detection cut one customer's MTTR from 45 to 8 minutes.",
            "Pulse retains high-cardinality traces for 30 days at $0.10 per GB.",
        ],
        "receiver_facts": [
            "Cobalt Bank runs 1,200 microservices and misses SLA on 3% of "
            "incidents from slow root-cause.",
            "Cobalt's on-call engineers page 60 times per week.",
            "Cobalt must retain audit logs for 7 years for compliance.",
        ],
    },
]


def _template_two_sections():
    return TemplateFactory(name="Newsletter two sections")


def _template_three_sections_no_slots():
    return TemplateFactory(
        name="Longform three sections",
        constraints={
            "headline_max_words": 12,
            "subheadline_max_words": 24,
            "body_section_count": 3,
            "body_section_max_words": 90,
            "cta_max_words": 12,
        },
        image_slots=[],
    )


def _seed_chunks(embedder, company, facts):
    for i, fact in enumerate(facts, start=1):
        DocumentChunkFactory(
            company=company,
            content=fact,
            page_number=i,
            embedding=embedder.embed_query(fact),
        )


def build_golden_materials(*, embedder=None) -> list[int]:
    embedder = embedder or EmbeddingService()
    ids: list[int] = []
    templates = [_template_two_sections(), _template_three_sections_no_slots()]

    for idx, pair in enumerate(_PAIRS):
        for template in templates:
            sender = CompanyFactory(name=pair["sender"])
            receiver = CompanyFactory(name=pair["receiver"])
            _seed_chunks(embedder, sender, pair["sender_facts"])
            _seed_chunks(embedder, receiver, pair["receiver_facts"])
            material = MarketingMaterialFactory(
                title=f"Golden {idx}: {pair['sender']} -> {pair['receiver']} "
                f"({template.name})",
                sender_company=sender,
                receiver_company=receiver,
                template=template,
                prompt=f"Pitch {pair['sender']} to {pair['receiver']}, "
                "addressing their specific situation.",
            )
            ids.append(material.pk)

    # Adversarial: sparse context (sender has 1 chunk, receiver has none).
    sender = CompanyFactory(name="Acme sparse")
    receiver = CompanyFactory(name="Globex sparse")
    _seed_chunks(embedder, sender, ["Acme ships a real-time fraud API."])
    material = MarketingMaterialFactory(
        title="Golden sparse adversarial",
        sender_company=sender,
        receiver_company=receiver,
        template=templates[0],
        prompt="Pitch with minimal context.",
    )
    ids.append(material.pk)
    return ids
