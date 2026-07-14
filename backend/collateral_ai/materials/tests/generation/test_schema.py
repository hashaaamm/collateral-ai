from __future__ import annotations

from collateral_ai.materials.generation.schema import build_response_schema

CONSTRAINTS = {
    "headline_max_words": 10,
    "subheadline_max_words": 22,
    "body_section_count": 2,
    "body_section_max_words": 80,
    "cta_max_words": 15,
}


def test_schema_shape_omits_image_slots():
    schema = build_response_schema(constraints=CONSTRAINTS)
    assert set(schema["properties"]) == {"article", "source_references"}
    assert schema["required"] == ["article", "source_references"]
    # template_id, theme, and image_slots are server-stamped — never
    # model-generated (spec §4; image_slots is template-owned).
    assert "template_id" not in schema["properties"]
    assert "theme" not in schema["properties"]
    assert "image_slots" not in schema["properties"]
    body = schema["properties"]["article"]["properties"]["body_sections"]
    assert body["minItems"] == 2
    assert body["maxItems"] == 2


def test_source_id_constrained_to_allowed_enum():
    schema = build_response_schema(
        constraints={"body_section_count": 2},
        allowed_source_ids=["SENDER_SOURCE_1", "RECEIVER_SOURCE_1"],
    )
    source_id = schema["properties"]["source_references"]["items"]["properties"][
        "source_id"
    ]
    assert source_id["enum"] == ["SENDER_SOURCE_1", "RECEIVER_SOURCE_1"]


def test_source_id_unconstrained_when_no_ids():
    schema = build_response_schema(
        constraints={"body_section_count": 2},
        allowed_source_ids=[],
    )
    source_id = schema["properties"]["source_references"]["items"]["properties"][
        "source_id"
    ]
    assert "enum" not in source_id
