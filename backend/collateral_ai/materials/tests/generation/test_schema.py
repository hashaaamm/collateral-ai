from __future__ import annotations

from collateral_ai.materials.generation.schema import build_response_schema

CONSTRAINTS = {
    "headline_max_words": 10,
    "subheadline_max_words": 22,
    "body_section_count": 2,
    "body_section_max_words": 80,
    "cta_max_words": 15,
}
SLOTS = [
    {
        "slot_id": "hero_image",
        "label": "Hero",
        "spec": "1200×630",  # noqa: RUF001
        "source": "generated_placeholder",
    },
    {"slot_id": "sender_logo", "label": "Logo", "spec": "SVG", "source": "sender"},
]


def test_schema_shape_and_slot_enum():
    schema = build_response_schema(constraints=CONSTRAINTS, image_slots=SLOTS)
    assert set(schema["properties"]) == {"article", "image_slots", "source_references"}
    assert schema["required"] == ["article", "image_slots", "source_references"]
    # template_id and theme are server-stamped — never model-generated (spec §4)
    assert "template_id" not in schema["properties"]
    assert "theme" not in schema["properties"]
    slots = schema["properties"]["image_slots"]
    assert slots["minItems"] == 2
    assert slots["maxItems"] == 2
    assert slots["items"]["properties"]["slot_id"]["enum"] == [
        "hero_image",
        "sender_logo",
    ]
    body = schema["properties"]["article"]["properties"]["body_sections"]
    assert body["minItems"] == 2
    assert body["maxItems"] == 2


def test_schema_empty_slots_omits_enum():
    schema = build_response_schema(constraints=CONSTRAINTS, image_slots=[])
    slots = schema["properties"]["image_slots"]
    assert slots["minItems"] == 0
    assert slots["maxItems"] == 0
    assert "enum" not in slots["items"]["properties"]["slot_id"]


def test_source_id_constrained_to_allowed_enum():
    schema = build_response_schema(
        constraints={"body_section_count": 2},
        image_slots=[],
        allowed_source_ids=["SENDER_SOURCE_1", "RECEIVER_SOURCE_1"],
    )
    source_id = schema["properties"]["source_references"]["items"]["properties"][
        "source_id"
    ]
    assert source_id["enum"] == ["SENDER_SOURCE_1", "RECEIVER_SOURCE_1"]


def test_source_id_unconstrained_when_no_ids():
    schema = build_response_schema(
        constraints={"body_section_count": 2},
        image_slots=[],
        allowed_source_ids=[],
    )
    source_id = schema["properties"]["source_references"]["items"]["properties"][
        "source_id"
    ]
    assert "enum" not in source_id
