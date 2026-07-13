"""Prompt construction for material generation (spec §6.3 step 3)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collateral_ai.materials.generation.retrieval import RetrievedChunk
    from collateral_ai.materials.models import MarketingMaterial

SYSTEM_INSTRUCTION = """
You are a senior B2B marketing strategist and a strict structured JSON \
generation system.

Rules:
- Generate tailored B2B marketing material from the sender to the receiver.
- Use ONLY the provided sender_context and receiver_context. No external \
knowledge, no unsupported claims.
- Think through the receiver's pain points and pick one sharp campaign angle \
before writing.
- Respect every constraint in template.constraints (word limits are hard \
limits, counted by whitespace-separated words).
- source_references: cite only source_id values that appear in sender_context \
or receiver_context, and explain the fact used.
- Keep the tone professional, credible, and specific.
""".strip()

REPAIR_SYSTEM_INSTRUCTION = """
You repair invalid JSON for a marketing layout system.

Rules:
- Return valid JSON only, matching the schema.
- Fix ONLY what the validation errors list; keep everything else unchanged.
- Do not add unsupported claims.
- Respect all word limits (whitespace-separated words).
- Use only allowed source IDs.
""".strip()


def build_retrieval_query(material: MarketingMaterial) -> str:
    return (
        f"Marketing request: {material.prompt}\n"
        f"Sender company: {material.sender_company.name}\n"
        f"Receiver company: {material.receiver_company.name}\n"
        f"Tone: {material.tone}\n"
        "Find relevant products, positioning, benefits, industry, pain points, "
        "and proof points."
    )


def build_generation_payload(
    *,
    material: MarketingMaterial,
    sender_chunks: list[RetrievedChunk],
    receiver_chunks: list[RetrievedChunk],
) -> str:
    template = material.template
    payload = {
        "task": "Generate a short tailored B2B marketing article.",
        "material_prompt": material.prompt,
        "tone": material.tone,
        "cta_style": material.cta_style,
        "language": material.language,
        "sender_company": _company_dict(material.sender_company),
        "receiver_company": _company_dict(material.receiver_company),
        "template": {
            "name": template.name,
            "constraints": template.constraints,
        },
        "sender_context": [c.to_prompt_dict() for c in sender_chunks],
        "receiver_context": [c.to_prompt_dict() for c in receiver_chunks],
    }
    return json.dumps(payload, indent=2)


def build_repair_payload(
    *,
    output: dict,
    errors: list[dict],
    constraints: dict,
    image_slots: list[dict],
    allowed_source_ids: list[str],
) -> str:
    return json.dumps(
        {
            "invalid_output_json": output,
            "validation_errors": errors,
            "template_constraints": constraints,
            "template_image_slots": image_slots,
            "allowed_source_ids": allowed_source_ids,
            "instruction": (
                "Fix the JSON so it passes validation. Respect word limits, "
                "required fields, image slots, and source references."
            ),
        },
        indent=2,
    )


def _company_dict(company) -> dict:
    return {
        "id": company.pk,
        "name": company.name,
        "industry": company.industry,
        "description": company.description,
    }
