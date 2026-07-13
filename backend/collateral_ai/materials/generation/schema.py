"""Structured-output schema for Vertex Gemini, parameterized by the template.

The dict uses Vertex's OpenAPI-subset schema (uppercase types, camelCase
minItems/maxItems — google-genai's types.Schema accepts these aliases).
minItems/maxItems are best-effort hints; OutputValidator is the enforcement
backstop when the model ignores them.

template_id and theme are deliberately absent: both are stamped server-side
from the template after every model response (spec §4).
"""

from __future__ import annotations

from typing import Any

SLOT_SOURCE_VALUES = ["sender", "receiver", "generated_placeholder"]


def build_response_schema(
    *,
    constraints: dict,
    allowed_source_ids: list[str] | None = None,
) -> dict[str, Any]:
    section_count = int(constraints["body_section_count"])
    source_id_property: dict[str, Any] = {"type": "STRING"}
    if allowed_source_ids:
        # Structurally prevent hallucinated citations (defense-in-depth with
        # OutputValidator's source check).
        source_id_property["enum"] = list(allowed_source_ids)
    return {
        "type": "OBJECT",
        "properties": {
            "article": {
                "type": "OBJECT",
                "properties": {
                    "headline": {"type": "STRING"},
                    "subheadline": {"type": "STRING"},
                    "body_sections": {
                        "type": "ARRAY",
                        "minItems": section_count,
                        "maxItems": section_count,
                        "items": {
                            "type": "OBJECT",
                            "properties": {
                                "title": {"type": "STRING"},
                                "text": {"type": "STRING"},
                            },
                            "required": ["title", "text"],
                        },
                    },
                    "cta": {"type": "STRING"},
                },
                "required": ["headline", "subheadline", "body_sections", "cta"],
            },
            "source_references": {
                "type": "ARRAY",
                "minItems": 1,
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "source_id": source_id_property,
                        "used_fact": {"type": "STRING"},
                    },
                    "required": ["source_id", "used_fact"],
                },
            },
        },
        "required": ["article", "source_references"],
    }
