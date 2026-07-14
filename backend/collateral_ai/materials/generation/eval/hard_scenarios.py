"""Extra hard split-fact scenarios for the golden eval (spec: PR #35 follow-up).

Each scenario mirrors the Merex/Baltic pattern defined in seed.py: sender and
receiver documents whose blocks put headline claims in the first ~220 words and
the qualifying fine print past the ~300-word chunk boundary, so bare 300-word
chunks retrieve the claim without its qualifier. Distractor blocks add
retrieval noise. `expected_facts` carry claim+qualifier pairs for the
fact_fidelity judge.
"""

from __future__ import annotations

_VERIDIAN_SENDER_BLOCKS = [
    # Block 1 (~430 words): triage + response-time claims early; ruleset
    # maturity and plan-tier qualifiers past the chunk boundary.
    "Veridian Shield is a managed detection and response platform built for "
    "healthcare providers, combining an AI triage engine with a "
    "around-the-clock security operations center staffed by analysts who "
    "work healthcare environments exclusively. The two numbers customers "
    "quote most: the AI triage engine resolves 70 percent of incoming "
    "security alerts automatically without human touch, and our security "
    "operations center holds a five-minute median analyst response for "
    "alerts. For a hospital security team drowning in alert volume, that "
    "combination converts an unmanageable queue into a short list of "
    "genuinely suspicious events with context attached. The platform "
    "ingests telemetry from endpoint agents, network sensors, identity "
    "providers, email gateways, and medical-device network segments, and "
    "correlates them into single incidents rather than duplicate alarms. "
    "Detection content is curated for clinical environments: lateral "
    "movement toward picture archiving systems, anomalous access to "
    "electronic health records, impossible-travel logins for clinical "
    "staff, and ransomware precursors tuned against real hospital traffic. "
    "Analysts see the full patient-safety context of an asset before "
    "acting, so a suspicious infusion-pump subnet event is escalated with "
    "clinical engineering on the bridge rather than quarantined blind. "
    "Deployment is agent-light: most customers reach full telemetry "
    "coverage inside three weeks, and the console ships with report packs "
    "for board briefings and cyber-insurance renewals. Reference customers "
    "include regional networks, academic medical centers, and specialty "
    "clinic groups across North America and Europe. Onboarding follows a "
    "fixed four-step runbook: telemetry inventory, connector rollout, "
    "detection tuning against two weeks of live traffic, and a joint "
    "go-live review with named owners on both sides. Every customer "
    "receives a dedicated service manager who runs the monthly review, "
    "tracks tuning actions to closure, and owns escalation paths into "
    "engineering. Documentation lives in a shared runbook portal your "
    "team can edit, so tribal knowledge survives staff turnover on "
    "either side. Integration health is scored weekly, and silent "
    "telemetry sources page our team before they become blind spots. "
    "The precise footing behind those two headline numbers, because we "
    "would rather you buy what we actually sell: the 70 percent automatic-resolution figure is "
    "measured on environments running our standard detection ruleset for "
    "at least ninety days — during the first quarter after go-live, while "
    "the models learn your baseline, automatic resolution typically runs "
    "near 40 percent and analysts absorb the difference. The five-minute "
    "median response applies to Critical-severity alerts for customers on "
    "the Premium response plan; the Standard plan carries a thirty-minute "
    "median during business hours, with overnight Critical alerts handled "
    "by the on-call rotation. Both figures are reported monthly in your "
    "service review, calculated from timestamped queue data.",
    # Block 2 (~430 words): compliance + uptime claims early; BAA tier and
    # SLA-scope qualifiers past the boundary.
    "Compliance posture is where Veridian Shield leads conversations with "
    "hospital counsel. The platform is HIPAA-ready and we sign business "
    "associate agreements; our uptime service-level agreement is 99.99 "
    "percent, and every control relevant to protected health information "
    "is documented in an auditor-facing matrix mapped to the HIPAA "
    "Security Rule, HITRUST, and SOC 2 Type II. Audit logging is "
    "immutable and exportable, with fifteen-month retention standard so a "
    "full OCR audit window is always available. Data handling is "
    "segregated per customer with dedicated encryption keys, and support "
    "access is broker-mediated, recorded, and time-boxed. Incident "
    "response retainers include breach-notification support: our team "
    "produces the forensic timeline and evidence package your counsel "
    "needs for reporting decisions, and we have supported customers "
    "through state and federal notifications without a missed deadline. "
    "The SOC operates from two geographically separate facilities with "
    "independent power and network paths, and analyst shifts overlap so "
    "context never hands off cold. Tabletop exercises are included twice "
    "yearly, run against scenarios drawn from real healthcare incidents: "
    "ransomware in imaging, compromised vendor VPN accounts, and insider "
    "access to celebrity records. Customers also receive quarterly "
    "purple-team reports showing which detection content fired against "
    "simulated attacker behavior in their own environment. Reporting "
    "cadence is fixed regardless of tier: a monthly service review with "
    "your named manager, a quarterly executive summary sized for "
    "committee packets, and an annual controls briefing your auditors "
    "may attend. Post-incident reviews are delivered within five "
    "business days of closure, with corrective actions tracked in the "
    "shared portal until your team signs them off. Escalation is "
    "contractual: severity definitions, bridge times, and management "
    "contacts are written into the agreement, and any missed commitment "
    "appears in the same monthly report your team sees, not a private "
    "dashboard. Customer references for each tier are available on "
    "request, matched by bed count and regulatory posture. Now the "
    "contract-level specifics your counsel will ask about, stated plainly "
    "so procurement holds no surprises: business associate agreements are "
    "executed on Enterprise agreements only — the Essentials tier is sold "
    "without a BAA and is therefore unsuitable for environments touching "
    "protected health information. The 99.99 percent availability "
    "commitment covers the detection and alerting pipeline; the reporting "
    "console carries a separate 99.9 percent commitment, and both exclude "
    "scheduled maintenance windows of up to four hours monthly, announced "
    "seventy-two hours in advance and placed outside your local business "
    "hours. Service credits accrue automatically from the same uptime "
    "telemetry we publish to your status page, so no claim filing is "
    "required for a missed month.",
]

_VERIDIAN_SENDER_DISTRACTORS = [
    "About this document. This overview is produced by the Veridian Shield "
    "field marketing team for prospective healthcare customers and their "
    "advisors. Regional sales offices operate in Boston, Toronto, "
    "Amsterdam, and Singapore, with clinical security specialists "
    "available for on-site briefings. Veridian Shield is a registered "
    "trademark; all product names referenced remain the property of their "
    "respective owners. Press and analyst inquiries should be directed to "
    "the communications office rather than regional sales. The customer "
    "stories cited in this document are published with written permission "
    "and are available in long form on the trust portal, alongside "
    "certification letters and sample reports.",
]

_VERIDIAN_RECEIVER_BLOCKS = [
    # Block 1 (~430 words): alert-fatigue pain early; EHR topology, budget
    # cycle, and board BAA mandate past the boundary.
    "Norhaven Health security posture review, prepared for the audit and "
    "compliance committee. Norhaven Health operates eleven hospitals and "
    "forty-one clinics across the region with roughly 2,300 staffed beds, "
    "and the information security function currently runs with four "
    "full-time staff. The core operational problem is alert fatigue: the "
    "security stack generates approximately 3,000 alerts per day across "
    "endpoint, network, and identity tooling, and the median time for a "
    "human to look at any alert is now ninety minutes — for overnight "
    "alerts it is effectively next-business-day. Last year's ransomware "
    "incident at a sister network, which forced ambulance diversion for "
    "four days, has the board treating detection speed as a patient-"
    "safety issue rather than an IT metric. The team's assessment is "
    "that internal hiring cannot close the gap: the market for "
    "healthcare-fluent security analysts is thin, our pay bands lag, and "
    "even a successful hiring round would add at most two analysts "
    "against a workload that needs a staffed night shift. Managed "
    "detection is therefore the recommended direction, with the caveat "
    "that any partner must demonstrate clinical-environment fluency, not "
    "generic enterprise coverage. Context any vendor proposal must "
    "account for before it reaches the committee: the electronic health "
    "record is an on-premise Meditech deployment scheduled for a cloud "
    "migration no earlier than two fiscal years out, imaging runs in a "
    "vendor cloud, and the two environments are bridged by an aging "
    "integration engine that is itself a risk register entry. The "
    "security budget is fixed until the fiscal year closes in September; "
    "anything above the earmarked managed-services line requires a "
    "supplemental request with chief financial officer sign-off. And the "
    "board resolution adopted after the sister-network incident is "
    "explicit: every vendor with any access path to protected health "
    "information executes a business associate agreement before "
    "connection — no pilot exceptions, no deferrals to contract renewal.",
    # Block 2 (~420 words): coverage-gap requirement early; union rules and
    # segmentation freeze past the boundary.
    "Requirements for a managed detection partner, as drafted for the "
    "request-for-proposal. The non-negotiable is continuous coverage: "
    "Norhaven needs 24/7 monitoring with analyst response, because the "
    "current four-person team covers weekdays only and the audit "
    "committee has flagged nights and weekends as the exposure window in "
    "two consecutive findings. The external auditors' Q2 deadline for a "
    "remediation plan makes this procurement time-bound: a signed "
    "contract and an agreed onboarding schedule must exist before the "
    "audit response is filed. Response expectations are concrete: "
    "critical alerts touching clinical systems need human eyes within "
    "minutes at any hour, with an escalation bridge that includes our "
    "on-call clinical engineering lead when medical devices are "
    "implicated. Reporting must serve three audiences: operational "
    "detail for the security team, control-mapped summaries for "
    "auditors, and a quarterly patient-safety-framed briefing for the "
    "board. Vendor analysts must be fluent in healthcare topology — "
    "PACS, HL7 interfaces, infusion-pump segments — because triage that "
    "quarantines clinical assets blind is itself a patient-safety event. "
    "Two operating constraints shape what any partner can actually "
    "deploy, and both have tripped vendors before: first, the collective "
    "bargaining agreement covering clinical and support staff restricts "
    "tooling that could function as individual staff performance "
    "monitoring, so any user-behavior analytics must be configured for "
    "security-relevant anomalies with individual-level dashboards "
    "disabled, and the union's technology committee reviews the "
    "configuration; second, the network segmentation project isolating "
    "clinical VLANs runs through the end of summer, and the change "
    "advisory board has frozen new agent deployments on clinical "
    "network segments until it completes — meaning initial coverage "
    "must come from network sensors and identity telemetry, with "
    "endpoint agents on clinical segments following in a phase two "
    "after the freeze lifts.",
]

_VERIDIAN_RECEIVER_DISTRACTORS = [
    "Document control. This security posture review is classified "
    "internal and distributed to the audit and compliance committee, the "
    "chief information officer, and the chief medical information "
    "officer. Version two point one, approved by the chief information "
    "security officer. Comments should be routed through the governance "
    "risk and compliance tool rather than email. Prior versions are "
    "superseded and must be deleted from shared drives. Appendices with "
    "the full alert-volume analysis and the auditor findings letters are "
    "held in the compliance document vault.",
]

_VERIDIAN_SENDER_SUMMARY = (
    "Sales overview of Veridian Shield, a managed detection and response "
    "platform for healthcare. Key facts with their qualifiers: 70 percent "
    "automatic alert triage applies after ninety days on the standard "
    "ruleset (first-quarter automatic resolution runs near 40 percent); "
    "the five-minute median response covers Critical alerts on the "
    "Premium plan, while Standard carries a thirty-minute business-hours "
    "median; business associate agreements are signed on Enterprise "
    "agreements only — Essentials has no BAA; the 99.99 percent uptime "
    "SLA covers the detection pipeline (console is 99.9) and excludes "
    "announced monthly maintenance windows; SOC 2 Type II and HITRUST "
    "mapped controls with fifteen-month audit log retention."
)

_VERIDIAN_RECEIVER_SUMMARY = (
    "Internal security posture review of Norhaven Health, an "
    "eleven-hospital regional network (2,300 beds, four-person security "
    "team). Pain: roughly 3,000 alerts/day with ninety-minute median "
    "human response and no night/weekend coverage; auditors require a "
    "remediation plan by Q2. Constraints: board mandate that every "
    "vendor touching protected health information signs a BAA before "
    "connection with no pilot exceptions; fixed budget until the fiscal "
    "year ends in September; union rules restrict individual staff "
    "monitoring; clinical-VLAN agent deployments are frozen until the "
    "network segmentation project completes at the end of summer; "
    "on-prem Meditech EHR bridged to cloud imaging."
)

_VERIDIAN_EXPECTED_FACTS = [
    "The 70 percent automatic alert triage figure applies only after "
    "roughly ninety days on the standard detection ruleset; during the "
    "first quarter after go-live automatic resolution runs near 40 "
    "percent, so Norhaven's audit-deadline-driven first months will see "
    "the lower figure.",
    "The five-minute median analyst response applies to Critical-severity "
    "alerts on the Premium response plan; the Standard plan carries a "
    "thirty-minute business-hours median, which does not by itself close "
    "Norhaven's night and weekend coverage gap.",
    "A business associate agreement is executed on Enterprise agreements "
    "only, and the 99.99 percent uptime SLA covers the detection pipeline "
    "(the console is 99.9 percent) and excludes announced monthly "
    "maintenance windows — material given Norhaven's board mandate that a "
    "BAA precede any connection.",
]

_VERIDIAN_PROMPT = (
    "Pitch Veridian Shield to Norhaven Health to close their 24/7 "
    "security coverage gap before their audit deadline. Be precise about "
    "response times, automatic triage maturity, and which plan tiers the "
    "compliance guarantees apply to."
)

_KINETIQ_SENDER_BLOCKS = [
    # Block 1 (~430 words): throughput + payback claims early; order-profile
    # and shift-model qualifiers past the boundary.
    "Kinetiq Systems builds goods-to-person robotic picking for "
    "e-commerce fulfilment operations that need warehouse throughput "
    "without warehouse expansion. The headline numbers from our "
    "installed base: a Kinetiq pick station sustains 650 units per hour, "
    "and customers typically reach payback in under eighteen months. "
    "The system stores inventory in a dense grid served by autonomous "
    "shuttles that deliver totes to ergonomic pick stations, so pickers "
    "stop walking and the building's cube does the work. Grid storage "
    "roughly triples location density against wide-aisle racking, which "
    "is frequently the difference between staying in an existing "
    "building through peak and signing a second lease. Order "
    "orchestration software sequences totes so multi-line orders "
    "converge at one station, and slotting is continuous: the shuttles "
    "re-warehouse quietly during idle minutes, keeping fast movers at "
    "the grid surface ahead of the daily wave. Station ergonomics are "
    "certified to reduce reach and lift strain, and new operators reach "
    "standard rate in under a shift because the station presents, "
    "lights, and confirms each pick. The control system degrades "
    "gracefully: a stalled shuttle strands one lane of totes rather "
    "than a zone, and mean recovery for common faults is under four "
    "minutes without vendor intervention. Throughput reporting is "
    "transparent by default: every station publishes its hourly rate to "
    "the operations dashboard, and the weekly export breaks performance "
    "down by order profile, tote type, and operator shift so your "
    "industrial engineers can see exactly where minutes go. Capacity "
    "planning is a joint exercise each quarter, using your forward "
    "order forecast rather than our averages, and the model hands back "
    "station counts, labour plans, and grid utilisation by week. During "
    "peak, a Kinetiq performance engineer joins your daily stand-up "
    "remotely for the first season. Rate guarantees, where offered, are "
    "written against your measured profile after the first four weeks "
    "of stable operation. Because honest sizing beats an impressive "
    "brochure, the assumptions behind those two numbers: "
    "the 650 units-per-hour station rate is measured with standardized "
    "600 by 400 millimeter totes and single-SKU order profiles typical "
    "of grocery and consumer staples; operations dominated by "
    "mixed-case apparel picking average 380 to 420 units per hour per "
    "station because garment handling and poly-bag singulation slow the "
    "pick cycle. The under-eighteen-month payback is modeled on "
    "two-shift operations where the system displaces agency labor at "
    "peak wage rates; single-shift sites typically model out at "
    "twenty-eight to thirty-four months because the capital works half "
    "the hours against the same purchase price.",
    # Block 2 (~425 words): deployment-speed + integration claims early;
    # site-prerequisite and WMS-version qualifiers past the boundary.
    "Deployment is where Kinetiq differentiates from conveyor-era "
    "automation. A standard grid goes live in six weeks from first "
    "steel to first pick, and the platform integrates with all major "
    "warehouse management systems through a documented interface used "
    "in more than one hundred sites. Installation is modular: the grid "
    "arrives as pre-assembled cells, commissioning runs cell by cell, "
    "and existing manual picking continues alongside until cutover, so "
    "there is no big-bang weekend. Our deployment team runs the "
    "process-change workstream with your supervisors — wave planning, "
    "exception handling, returns flow — because the software go-live is "
    "rarely the hard part. Training is train-the-trainer with "
    "bilingual materials, and hypercare runs two weeks past cutover "
    "with an on-site engineer. Service afterward is data-driven: every "
    "shuttle streams health telemetry, wear parts ship ahead of "
    "failure, and remote diagnostics resolve most tickets without a "
    "site visit. Spare-parts kits live on your mezzanine, sized to "
    "your duty cycle, and software updates install rolling with no "
    "picking downtime. Customers audit our uptime the same way we do: "
    "station-minutes available against station-minutes scheduled, "
    "published monthly. Commissioning quality is measured, not "
    "asserted: each cell passes a scripted acceptance test covering "
    "throughput, fault recovery, and emergency stop behaviour, "
    "witnessed by your engineers and signed before the next cell "
    "starts. The cutover plan is rehearsed on paper twice with your "
    "supervisors, including a rollback path to manual picking that "
    "stays available for the first month. After go-live, weekly "
    "service reviews run until performance stabilises, then monthly, "
    "with an agreed exit checklist rather than an open-ended "
    "hypercare. Spares consumption and shuttle health trends are "
    "reviewed in the same forum, so budget surprises do not accumulate "
    "quietly. The site and systems prerequisites behind the six-week "
    "figure, since surprises here are what stretch timelines: the schedule assumes the installation area offers "
    "three-phase power at the mezzanine level and a certified floor "
    "loading of 500 kilograms per square metre under the grid "
    "footprint — sites needing electrical upgrades or structural "
    "reinforcement should plan those works before steel arrives, as "
    "they gate everything. On integration, the prebuilt connectors "
    "target the current API generation — version two — of the major "
    "warehouse management platforms; older on-premise deployments "
    "still on version one interfaces require a middleware adapter that "
    "is scoped and quoted separately and adds four to six weeks to the "
    "integration workstream, including a regression test cycle against "
    "your order profiles.",
]

_KINETIQ_SENDER_DISTRACTORS = [
    "Kinetiq in the industry. Kinetiq Systems exhibits at the major "
    "intralogistics trade shows across three continents, and our "
    "engineering leadership speaks regularly on shuttle-fleet "
    "coordination and warehouse electrification. Recent trade-press "
    "coverage highlighted the company's growth in the mid-market "
    "fulfilment segment and its partner network of systems integrators. "
    "The reference-visit program pairs prospective customers with "
    "installed sites of comparable order profile; visits are hosted by "
    "the customer's own operations team without Kinetiq sales staff in "
    "the room. Financing options including capital purchase, lease, and "
    "throughput-based pricing are described in a separate commercial "
    "annex available under non-disclosure.",
]

_KINETIQ_RECEIVER_BLOCKS = [
    # Block 1 (~430 words): growth pain early; WMS version and building
    # constraints past the boundary.
    "Bramwell Trading fulfilment operations assessment, prepared for the "
    "automation steering group. Bramwell Trading is an online apparel "
    "and accessories retailer shipping roughly forty thousand orders "
    "per day from a single fulfilment centre, with apparel representing "
    "85 percent of units picked and the balance in footwear boxes and "
    "accessories. Order profiles are overwhelmingly mixed-case: the "
    "typical order spans three brands and four garment types, picked "
    "today from wide-aisle shelving by a walking workforce. Pick "
    "productivity has plateaued at rates the industrial engineers "
    "consider ceiling for a walk-and-pick design, and peak season "
    "triples daily volume, which last year required six hundred agency "
    "workers, a satellite tent operation for overflow packing, and "
    "still produced the worst on-time dispatch performance in the "
    "company's history. The board has approved exploring goods-to-"
    "person automation for the core apparel pick, with a decision "
    "wanted before the next peak planning cycle begins. Facts about "
    "the building and systems that bound any proposal: the fulfilment "
    "centre is a converted nineteenth-century mill acquired for its "
    "location and rail access — characterful, but the mezzanine floor "
    "plates where automation would sit are certified to 350 kilograms "
    "per square metre, and the structural survey priced reinforcement "
    "as a planning-permission matter given the building's heritage "
    "listing, not a quick works order. The warehouse management "
    "system is a 2019 on-premise build of a major platform, running "
    "the version-one application programming interface; the vendor's "
    "cloud migration offer is on the roadmap but unbudgeted, and the "
    "in-house integration team is two developers who also own the "
    "storefront middleware.",
    # Block 2 (~420 words): labor and finance context early; power and
    # freeze constraints past the boundary.
    "Labour model and financial guardrails for the automation case. "
    "Bramwell runs a single day shift year-round, augmented by agency "
    "labour from October through January; a second permanent shift has "
    "been costed twice and rejected because local labour supply is "
    "thin and churn on evening shifts at neighbouring sites runs "
    "double digits monthly. The chief financial officer's screening "
    "criterion for automation capital is written into the investment "
    "policy: payback inside twenty-four months on conservative volume "
    "assumptions, using current labour rates rather than peak agency "
    "premiums, and any business case that only clears the hurdle on a "
    "two-shift assumption must carry the recruitment risk explicitly "
    "on its risk register. Finance also requires that throughput "
    "claims be evidenced against our order profile — mixed-case "
    "apparel — rather than vendor-standard profiles, after a previous "
    "sortation project delivered 60 percent of its promised rate. "
    "Operational constraints on timing and site works: the electrical "
    "board serving the mezzanine is single-phase legacy supply; the "
    "three-phase upgrade has been quoted by the utility with a "
    "twelve-week lead time but sits unapproved pending the automation "
    "decision, so any vendor schedule must sequence behind it or fund "
    "temporary generation. And operations enforces a hard change "
    "freeze from mid-October to the end of January — no system "
    "cutovers, no structural works, no integration releases — so an "
    "automation programme either completes commissioning by early "
    "October or parks until February, which in practice decides "
    "whether go-live lands this year or next.",
]

_KINETIQ_RECEIVER_DISTRACTORS = [
    "Circulation note. This assessment is for the automation steering "
    "group and the finance business partner only; commercial terms "
    "from vendor conversations must not be forwarded outside the "
    "group while procurement is live. Version one point four. The "
    "appendices — labour cost model, structural survey extract, and "
    "the utility's three-phase quotation — are in the capital "
    "projects folder. Site visits for shortlisted vendors are "
    "coordinated through the operations excellence office, avoiding "
    "the peak-season freeze window.",
]

_KINETIQ_SENDER_SUMMARY = (
    "Sales brochure for Kinetiq Systems, goods-to-person robotic picking "
    "for e-commerce fulfilment. Key facts with their qualifiers: the 650 "
    "units-per-hour station rate assumes standardized totes and "
    "single-SKU profiles — mixed-case apparel operations average 380 to "
    "420; the under-eighteen-month payback is modeled on two-shift "
    "operations displacing peak agency labour, with single-shift sites "
    "at twenty-eight to thirty-four months; six-week deployment assumes "
    "three-phase mezzanine power and 500 kg/m2 floor loading; prebuilt "
    "WMS connectors target current version-two APIs, while version-one "
    "on-premise systems need a separately quoted middleware adapter "
    "adding four to six weeks."
)

_KINETIQ_RECEIVER_SUMMARY = (
    "Internal fulfilment assessment of Bramwell Trading, an online "
    "apparel retailer shipping forty thousand orders/day, 85 percent "
    "apparel, overwhelmingly mixed-case picking. Pain: walk-and-pick "
    "productivity ceiling and a tripled peak requiring six hundred "
    "agency workers. Constraints: CFO requires payback inside "
    "twenty-four months on single-shift economics evidenced against "
    "their order profile; mezzanine floor loading certified 350 kg/m2 "
    "in a heritage-listed mill; 2019 on-premise WMS on the version-one "
    "API; single-phase mezzanine power with a twelve-week three-phase "
    "upgrade unapproved; hard mid-October-to-January change freeze."
)

_KINETIQ_EXPECTED_FACTS = [
    "The 650 units-per-hour station rate is measured on standardized "
    "totes and single-SKU profiles; mixed-case apparel operations like "
    "Bramwell's (85 percent apparel) average roughly 380 to 420 units "
    "per hour per station.",
    "The under-eighteen-month payback is modeled on two-shift operations "
    "displacing peak agency labour; single-shift sites like Bramwell's "
    "typically model at twenty-eight to thirty-four months, against a "
    "CFO screening criterion of payback inside twenty-four months on "
    "single-shift economics.",
    "The six-week deployment assumes three-phase mezzanine power and 500 "
    "kg/m2 certified floor loading, and Bramwell's 2019 version-one WMS "
    "API requires a separately quoted middleware adapter adding four to "
    "six weeks — while their mezzanine is certified to 350 kg/m2 with "
    "single-phase power and a twelve-week utility upgrade lead time.",
]

_KINETIQ_PROMPT = (
    "Pitch Kinetiq Systems to Bramwell Trading for automating their "
    "apparel fulfilment before next peak. Be accurate about throughput "
    "on their mixed-case order profile, payback under their single-shift "
    "model, and deployment prerequisites given their building and WMS."
)

EXTRA_HARD_SCENARIOS = [
    {
        "sender_name": "Veridian Shield",
        "receiver_name": "Norhaven Health",
        "sender_file": "Veridian Shield healthcare MDR overview.pdf",
        "receiver_file": "Norhaven Health security posture review.pdf",
        "sender_blocks": [*_VERIDIAN_SENDER_BLOCKS, *_VERIDIAN_SENDER_DISTRACTORS],
        "receiver_blocks": [
            *_VERIDIAN_RECEIVER_BLOCKS,
            *_VERIDIAN_RECEIVER_DISTRACTORS,
        ],
        "sender_summary": _VERIDIAN_SENDER_SUMMARY,
        "receiver_summary": _VERIDIAN_RECEIVER_SUMMARY,
        "expected_facts": _VERIDIAN_EXPECTED_FACTS,
        "prompt": _VERIDIAN_PROMPT,
    },
    {
        "sender_name": "Kinetiq Systems",
        "receiver_name": "Bramwell Trading",
        "sender_file": "Kinetiq Systems fulfilment automation brochure.pdf",
        "receiver_file": "Bramwell Trading fulfilment assessment.pdf",
        "sender_blocks": [*_KINETIQ_SENDER_BLOCKS, *_KINETIQ_SENDER_DISTRACTORS],
        "receiver_blocks": [
            *_KINETIQ_RECEIVER_BLOCKS,
            *_KINETIQ_RECEIVER_DISTRACTORS,
        ],
        "sender_summary": _KINETIQ_SENDER_SUMMARY,
        "receiver_summary": _KINETIQ_RECEIVER_SUMMARY,
        "expected_facts": _KINETIQ_EXPECTED_FACTS,
        "prompt": _KINETIQ_PROMPT,
    },
]
