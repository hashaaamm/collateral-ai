"""Self-generated golden examples for the material-gen eval dataset.

Builds varied templates (different section counts / image slots) across
three distinct, substantive sender/receiver company pairs, plus an
adversarial sparse-context case. Golden chunks carry REAL embeddings
(computed via EmbeddingService) so retrieval against them is meaningful
instead of matching against zero vectors. Each company's facts live in a
single document with a summary, so neighbor expansion and document
summaries are exercised by the eval.
"""

from __future__ import annotations

from collateral_ai.companies.tests.factories import CompanyFactory
from collateral_ai.documents.processing.chunking import ChunkingService
from collateral_ai.documents.processing.embeddings import EmbeddingService
from collateral_ai.documents.tests.factories import DocumentChunkFactory
from collateral_ai.documents.tests.factories import DocumentFactory
from collateral_ai.materials.tests.factories import MarketingMaterialFactory
from collateral_ai.materials.tests.factories import TemplateFactory

_PAIRS = [
    {
        "sender": "Sentinel Pay",
        "receiver": "Meridian Retail",
        "sender_summary": (
            "Sentinel Pay sells a real-time payment-fraud detection API for "
            "online merchants: 38ms p99 risk scoring, nightly retraining on 4 "
            "billion transactions, SOC 2 Type II and PCI-DSS Level 1 "
            "certification, and prebuilt connectors for Stripe, Adyen, and "
            "Braintree."
        ),
        "receiver_summary": (
            "Meridian Retail is an EMEA retailer processing 2.1M card "
            "transactions daily; its fraud tool's 4.2% false-positive rate "
            "costs $3M/yr in declined orders, and a Q3 APAC expansion needs "
            "multi-region latency under 50ms."
        ),
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
        "sender_summary": (
            "Nimbus Analytics is a cloud data warehouse whose columnar engine "
            "runs analytical queries 12x faster than Postgres at TB scale, "
            "with zero-copy cloning of 10TB warehouses in seconds and "
            "per-second compute billing with 60s autosuspend."
        ),
        "receiver_summary": (
            "Harborview Logistics runs same-day shipping operations slowed by "
            "a 6-hour nightly ETL and 40-second peak dashboard queries; it "
            "wants sub-second dashboards for 500 warehouse managers."
        ),
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
        "sender_summary": (
            "Pulse Observability is a tracing platform ingesting 5M spans/sec "
            "with 15-second end-to-end trace latency, anomaly detection that "
            "cut a customer's MTTR from 45 to 8 minutes, and 30-day "
            "high-cardinality retention at $0.10/GB."
        ),
        "receiver_summary": (
            "Cobalt Bank operates 1,200 microservices, misses SLA on 3% of "
            "incidents due to slow root-cause analysis, pages on-call 60 "
            "times weekly, and must retain audit logs for 7 years."
        ),
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


def _seed_chunks(embedder, company, facts, *, summary=""):
    document = DocumentFactory(
        company=company,
        file_name=f"{company.name} overview.pdf",
        summary=summary,
    )
    for i, fact in enumerate(facts, start=1):
        DocumentChunkFactory(
            document=document,
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
            _seed_chunks(
                embedder,
                sender,
                pair["sender_facts"],
                summary=pair["sender_summary"],
            )
            _seed_chunks(
                embedder,
                receiver,
                pair["receiver_facts"],
                summary=pair["receiver_summary"],
            )
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


# --- Hard cases: multi-chunk documents chunked by the REAL chunker so word
# offsets exist, headline claims land in a different chunk than their
# qualifiers, and distractor chunks force retrieval to actually select.
# Run the eval with MATERIAL_RETRIEVAL_TOP_K=3 so top_k < chunks/company.

_HARD_SENDER_BLOCKS = [
    # Block 1 (~455 words): performance claims early, tier/region/history
    # qualifiers past the 300-word chunk boundary.
    "Merex Analytics is a supply-chain analytics platform built for freight, "
    "retail, and manufacturing operators who need to make same-day decisions on "
    "live operational data instead of yesterday's batch exports. The platform "
    "connects to transactional systems, telematics feeds, and warehouse "
    "management software, and continuously materializes that data into "
    "decision-ready views for planners, dispatchers, and finance teams. "
    "Customers use Merex to answer questions that used to take an analyst half "
    "a day: which lanes are bleeding margin this week, which carriers are "
    "trending late, and where inventory is about to breach safety stock. The "
    "headline numbers our customers talk about most: Merex dashboards return "
    "sub-second query responses on datasets of up to twelve billion rows, and "
    "our demand forecasting module has reduced forecast error by 38 percent "
    "against customer baselines. Alerting is streaming-native, so a lane-level "
    "margin breach or a late-carrier pattern shows up in minutes, not in "
    "tomorrow's report. Planners get one shared view of the network, finance "
    "gets a governed semantic layer, and operations leadership gets a daily "
    "digest that actually reflects the overnight reality. Merex ships with "
    "more than eighty prebuilt connectors covering the common TMS, WMS, and "
    "ERP systems, plus native ingestion from Snowflake, BigQuery, and "
    "Databricks. Data teams can extend the semantic layer in SQL, and every "
    "metric definition is version-controlled so numbers reconcile across "
    "teams. Role-based access control, column-level masking, and full audit "
    "logs are standard on every tier. A few important specifics about the "
    "performance figures above, because we would rather set expectations "
    "correctly than surprise you in procurement. Sub-second interactive "
    "performance is a property of the Enterprise tier, which runs on "
    "dedicated compute pools; the Growth tier shares compute and typically "
    "lands between two and five seconds at the ninety-fifth percentile. "
    "Dedicated pools are currently provisioned in EU and US regions; "
    "customers routing APAC traffic are served through a partner region "
    "today, which adds roughly 180 milliseconds of latency, with first-party "
    "APAC pools on the roadmap for the second half of next year. Concurrency "
    "on a single dedicated pool is sized for up to fifty simultaneously "
    "active users; beyond that we add pools. The 38 percent forecast-error "
    "reduction was measured across consumer-goods and retail customers with "
    "at least twelve months of clean sales history; cold-start accuracy on "
    "sparse or newly launched product lines is materially lower until the "
    "models accumulate roughly one quarter of history.",
    # Block 2 (~420 words): onboarding claim early, prerequisites past the
    # boundary (security padding keeps the fine print out of chunk one).
    "Getting started with Merex is deliberately unlike a classic business-"
    "intelligence rollout. Most customers are live on their first governed "
    "dashboards within two weeks of contract signature, and our onboarding "
    "team has run more than two hundred implementations. The first week is "
    "connection and modeling: we point Merex at your systems, import the "
    "semantic definitions that match your vertical, and validate the numbers "
    "with your finance controller. The second week is enablement: we train "
    "planner and dispatcher teams in their own workspaces on their own data, "
    "not on demo content. Change management is built into the product: every "
    "dashboard has an owner, every metric has a definition page, and adoption "
    "analytics show you which teams are actually using what. On the security "
    "side, Merex holds a SOC 2 Type II attestation, encrypts data in transit "
    "and at rest, supports customer-managed encryption keys on Enterprise, "
    "and offers EU-only data residency including EU-based support handling. "
    "Single sign-on via SAML and OIDC is standard, and SCIM provisioning "
    "keeps access aligned with your directory. Penetration tests run twice a "
    "year through an independent security firm, and the executive summary of "
    "each test is shareable under a non-disclosure agreement. Residency "
    "commitments are contractual rather than best-effort: EU-resident "
    "customers receive a written guarantee that production data, backups, "
    "and support access remain within European Union boundaries, backed by "
    "quarterly attestation reports, and regulated customers receive an "
    "auditor-facing control matrix mapping platform controls to the common "
    "compliance frameworks. Now, the fine print that makes the two-week "
    "figure honest rather than optimistic. The two-week onboarding assumes "
    "two things: first, that your operational data already lands in a cloud "
    "warehouse such as Snowflake, BigQuery, or Databricks, or in one of the "
    "eighty-plus systems with a prebuilt connector; and second, that a data "
    "engineer from your side is available roughly half-time during those two "
    "weeks to resolve source-system questions. Customers starting from "
    "on-premise databases with no cloud warehouse, or without engineering "
    "availability, should plan for an eight-to-ten-week phased "
    "implementation, of which the first phase replicates the on-premise "
    "sources into a managed landing zone. Our ISO 27001 certification is in "
    "progress with the audit scheduled next quarter, so teams that "
    "contractually require ISO 27001 today should treat SOC 2 Type II as the "
    "operative control attestation until that completes.",
    # Block 3 (~415 words): outcome claim early, attribution and pricing
    # qualifiers past the boundary (support padding shifts the turn).
    "The commercial results customers report are the reason Merex wins "
    "renewals. The one we cite most: a Fortune 500 retailer reduced "
    "logistics cost per order by 22 percent after deploying Merex across its "
    "North American distribution network, and presented that result publicly "
    "at an industry conference. Mid-market freight forwarders typically "
    "report five-to-nine-percent margin improvement on managed lanes within "
    "the first two quarters, driven mostly by faster detection of carrier "
    "underperformance and automated accessorial audit. Finance teams report "
    "closing freight accruals days earlier because actuals and estimates "
    "live in one governed model. Customer success is staffed with former "
    "supply-chain planners rather than generalist account managers, and "
    "every Enterprise customer gets a named operations engineer. Support "
    "runs follow-the-sun from Amsterdam, Toronto, and Singapore. Contracts "
    "are annual with quarterly true-ups on usage, and we publish our uptime: "
    "the platform has run at 99.95 percent availability or better for eleven "
    "consecutive quarters. Quarterly business reviews include adoption "
    "scorecards by team and a jointly maintained value-realization log, so "
    "renewal conversations start from measured outcomes rather than "
    "anecdotes. Roadmap previews ship to customers a quarter ahead, and "
    "feature requests are tracked in a public portal where customers vote "
    "with their real usage profile attached. For completeness on the "
    "numbers above: the 22 percent logistics-cost result was measured over "
    "an eighteen-month engagement and combined the analytics platform with "
    "our route-optimization module, which is licensed separately; analytics "
    "alone accounted for roughly half of the modeled savings. The five-to-"
    "nine-percent forwarder results assume the customer acts on carrier-"
    "scorecard recommendations within the same quarter. On pricing: the "
    "Growth tier starts at four thousand dollars per month, which includes "
    "ten editor seats, unlimited viewers, and one hundred million rows of "
    "governed data; the Enterprise tier is custom-priced and adds dedicated "
    "compute, customer-managed keys, EU residency guarantees, and the named "
    "operations engineer. Route optimization is an add-on module priced on "
    "network volume. Proof-of-concept engagements run four weeks on your "
    "data with success criteria agreed in writing before we start.",
]

_HARD_SENDER_DISTRACTORS = [
    "Forward-looking statements notice. This document contains statements "
    "regarding anticipated product capabilities, certification timelines, and "
    "regional availability that are subject to change without notice. Nothing "
    "in this brochure constitutes a contractual commitment, warranty, or "
    "service-level agreement unless incorporated into a master services "
    "agreement executed by both parties. Product names, logos, and brands "
    "referenced herein are the property of their respective owners and are "
    "used for identification purposes only. Copyright Merex Analytics. All "
    "rights reserved. Reproduction without written permission is prohibited.",
    "About Merex Analytics. Founded by a team of former logistics planners "
    "and data-infrastructure engineers, Merex Analytics believes that every "
    "operational decision deserves current data. Our values are customer "
    "obsession, craftsmanship, and candor. We are a remote-first company "
    "with hubs in Amsterdam, Toronto, and Singapore, and we are proud to be "
    "recognized as a notable vendor in recent industry analyst coverage of "
    "supply-chain analytics. Merex is an equal-opportunity employer and "
    "sponsors visas in all hub locations. To learn more about careers, "
    "visit our website.",
]

_HARD_RECEIVER_BLOCKS = [
    "Baltic Freight Group operations review, prepared for the executive "
    "planning offsite. Baltic Freight Group is the fourth-largest freight "
    "forwarder in the Nordic and Baltic region, operating eighteen terminals "
    "with two thousand four hundred employees and moving roughly ninety "
    "thousand shipments per month across road, short-sea, and rail. This "
    "review consolidates the operational findings from the spring quarter. "
    "The two problems every terminal manager raised first: our nightly data "
    "pipeline takes six and a half hours to complete, which means morning "
    "planning starts on stale numbers whenever the run overflows its window, "
    "and our planning dashboards take forty to fifty seconds to load during "
    "the morning peak, which in practice means planners export to "
    "spreadsheets and the network plan fragments into local copies. "
    "Late-carrier detection is currently a weekly report; by the time a "
    "pattern is visible, we have usually already paid for the failure. "
    "Accessorial charges are audited manually on a sample basis and the "
    "finance team estimates leakage in the low single-digit percentage of "
    "freight spend. Fuel and toll reconciliation runs two weeks behind "
    "operations. These are the gaps a real-time analytics capability would "
    "need to close. Context on the team and stack that any vendor "
    "conversation has to start from: the central planning team is fourteen "
    "analysts split between Gdansk and Riga, with peak simultaneous "
    "dashboard usage measured at about thirty-five users on Monday mornings. "
    "All operational data lives today on two on-premise SQL Server clusters "
    "and a set of terminal-level Access databases; there is no cloud data "
    "warehouse yet, and the one prior attempt to stand one up stalled when "
    "the lone data engineer assigned to it left the company. Engineering "
    "availability for new tooling is effectively one shared data engineer at "
    "half capacity until the new platform team is hired in the autumn.",
    "The strategic driver for this year is the Asia-Pacific lane expansion. "
    "The board has approved opening a consolidation hub in Singapore with "
    "the first sailings booked for the fourth quarter, adding an expected "
    "eleven thousand shipments per month within the first year. The "
    "expansion makes our current reporting cadence untenable: booking desks "
    "in Singapore will be quoting against capacity we currently only "
    "reconcile overnight, so the working requirement from the network design "
    "team is estimated-time-of-arrival and capacity updates that are at most "
    "one minute old, visible simultaneously in Singapore, Gdansk, and Riga. "
    "Customer-facing commitments follow from that: the two anchor customers "
    "for the APAC lanes have service-level clauses tied to proactive delay "
    "notification, which our weekly late-carrier report cannot support. "
    "Whatever platform underpins this needs to be live and adopted by the "
    "planning teams before the Singapore hub opens. The constraints that "
    "bound the timeline and the architecture are as follows. Customer "
    "contracts and Latvian data-protection counsel both require that "
    "customer-identifying shipment data remains resident in the European "
    "Union; a vendor whose processing or support access happens outside the "
    "EU needs contractual safeguards our legal team has historically taken "
    "eight weeks to negotiate. IT operates a strict change freeze every "
    "December for the retail peak, so any migration work that is not "
    "finished by the last week of November slips to February. The Singapore "
    "hub will initially run on the corporate network via a regional "
    "breakout, so tooling latency from APAC matters operationally for the "
    "booking desk there, not just cosmetically. And the integration surface "
    "is wide: the transport management system is a heavily customized "
    "CargoWise deployment, and terminal telematics arrive as flat-file "
    "drops every fifteen minutes.",
    "Budget and procurement posture for analytics tooling. The finance "
    "committee has capped recurring analytics spend at sixty thousand euros "
    "per year for the first contract year, reviewable upward after the "
    "Singapore hub proves out; one-time implementation services are budgeted "
    "separately at up to twenty-five thousand euros. Procurement requires "
    "SOC 2 Type II or ISO 27001 attestation before contract signature, a "
    "data-processing agreement with EU standard contractual clauses, and "
    "references from at least two logistics customers of comparable size. "
    "The committee explicitly flagged the lessons from the previous "
    "business-intelligence rollout, which was abandoned after fourteen "
    "months: the vendor assumed a data-engineering capacity we did not have, "
    "the implementation plan had no phase gates, and adoption was never "
    "measured, so the sunk cost was discovered only at renewal. Any new "
    "proposal must therefore name the customer-side staffing it assumes, in "
    "hours per week, and must include adoption metrics in the quarterly "
    "business review. Timeline expectations given the December freeze: "
    "vendor selection concludes mid-summer, contracting and the "
    "data-processing agreement run in parallel through late summer, "
    "implementation must reach the phase-one milestone of planner dashboards "
    "on live terminal data before the November change-freeze cutoff, and the "
    "Singapore booking desk onboards in the new year. The operations "
    "directors asked that whichever platform is selected be piloted first on "
    "the Gdansk-Hamburg corridor, which has the cleanest historical data, "
    "before network-wide rollout. Success for the first two quarters is "
    "defined as: morning plan produced on data no older than fifteen "
    "minutes, dashboard load under five seconds at Monday peak for "
    "thirty-five concurrent planners, and proactive delay notifications "
    "reaching the two anchor customers ahead of their contractual windows.",
]

_HARD_RECEIVER_DISTRACTORS = [
    "Document control. This operations review is classified internal and is "
    "distributed to the executive committee, terminal directors, and the "
    "network design team. Version one point two, approved by the chief "
    "operating officer. Comments and corrections should be routed to the "
    "operations excellence mailbox before the planning offsite. Previous "
    "versions of this document are superseded and should be deleted from "
    "local drives. The appendices referenced throughout are available in "
    "the document management system under the operations review workspace.",
]

_HARD_SENDER_SUMMARY = (
    "Sales brochure for Merex Analytics, a supply-chain analytics platform "
    "for freight, retail, and manufacturing operators. Key facts with their "
    "qualifiers: sub-second dashboards apply to the Enterprise tier on "
    "dedicated EU/US compute pools sized for fifty concurrent users, with "
    "APAC served via a partner region (~180ms extra) until first-party APAC "
    "pools arrive next year; the 38 percent forecast-error reduction was "
    "measured on customers with twelve-plus months of history; two-week "
    "onboarding requires an existing cloud warehouse and a half-time "
    "customer data engineer, otherwise eight to ten weeks; SOC 2 Type II "
    "attested, ISO 27001 audit scheduled; a cited 22 percent logistics-cost "
    "reduction combined analytics with the separately licensed "
    "route-optimization module; Growth tier from four thousand dollars per "
    "month, Enterprise custom."
)

_HARD_RECEIVER_SUMMARY = (
    "Internal operations review of Baltic Freight Group, the fourth-largest "
    "Nordic/Baltic freight forwarder (eighteen terminals, ninety thousand "
    "shipments/month). Pain: a 6.5-hour nightly ETL and 40-50-second peak "
    "dashboards fragment planning; late-carrier detection is weekly. "
    "Driver: a board-approved Singapore consolidation hub opens in Q4 "
    "needing sub-minute ETA and capacity updates visible in Singapore, "
    "Gdansk, and Riga. Constraints: EU data residency for customer data, a "
    "December IT change freeze with a November cutoff, one half-time data "
    "engineer and no cloud warehouse, a sixty-thousand-euro annual analytics "
    "budget cap, and procurement lessons from a failed BI rollout that "
    "assumed unavailable engineering capacity."
)

_HARD_EXPECTED_FACTS = [
    "Sub-second dashboard performance requires the Enterprise tier on "
    "dedicated compute pools that exist only in EU and US regions today; "
    "APAC traffic goes through a partner region adding roughly 180 "
    "milliseconds until first-party APAC pools launch in the second half of "
    "next year.",
    "Two-week onboarding applies only when operational data already lands "
    "in a cloud warehouse or prebuilt-connector system and a customer data "
    "engineer is available half-time; starting from on-premise databases "
    "without engineering availability means an eight-to-ten-week phased "
    "implementation.",
    "The Fortune 500 retailer's 22 percent logistics-cost reduction was "
    "measured over eighteen months and combined analytics with the "
    "separately licensed route-optimization module; analytics alone "
    "accounted for roughly half of the modeled savings.",
]

_HARD_PROMPT = (
    "Pitch Merex Analytics to Baltic Freight Group for their APAC lane "
    "expansion. Be honest about implementation timeline, performance, and "
    "regional constraints given their situation."
)


def _seed_hard_document(embedder, company, *, file_name, blocks, summary):
    chunker = ChunkingService()
    document = DocumentFactory(
        company=company,
        file_name=file_name,
        summary=summary,
    )
    for page_number, block in enumerate(blocks, start=1):
        for piece in chunker.chunk_text(block, page_number):
            DocumentChunkFactory(
                document=document,
                company=company,
                content=piece["content"],
                page_number=page_number,
                metadata={
                    "chunk_index": piece["chunk_index"],
                    "word_start": piece["word_start"],
                    "word_end": piece["word_end"],
                },
                embedding=embedder.embed_query(piece["content"]),
            )
    return document


def build_hard_materials(*, embedder=None) -> list[dict]:
    """Hard cases where bare chunks genuinely lack context.

    Returns [{"material_id": int, "expected_facts": [str, ...]}, ...] so the
    dataset can carry the claim+qualifier facts for the fact_fidelity judge.
    """
    embedder = embedder or EmbeddingService()
    entries: list[dict] = []
    for template in (_template_two_sections(), _template_three_sections_no_slots()):
        sender = CompanyFactory(name="Merex Analytics")
        receiver = CompanyFactory(name="Baltic Freight Group")
        _seed_hard_document(
            embedder,
            sender,
            file_name="Merex Analytics platform brochure.pdf",
            blocks=[*_HARD_SENDER_BLOCKS, *_HARD_SENDER_DISTRACTORS],
            summary=_HARD_SENDER_SUMMARY,
        )
        _seed_hard_document(
            embedder,
            receiver,
            file_name="Baltic Freight operations review.pdf",
            blocks=[*_HARD_RECEIVER_BLOCKS, *_HARD_RECEIVER_DISTRACTORS],
            summary=_HARD_RECEIVER_SUMMARY,
        )
        material = MarketingMaterialFactory(
            title=f"Golden hard: Merex -> Baltic Freight ({template.name})",
            sender_company=sender,
            receiver_company=receiver,
            template=template,
            prompt=_HARD_PROMPT,
        )
        entries.append(
            {
                "material_id": material.pk,
                "expected_facts": list(_HARD_EXPECTED_FACTS),
            },
        )
    return entries
