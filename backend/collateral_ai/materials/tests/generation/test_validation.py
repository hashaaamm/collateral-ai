from __future__ import annotations

from collateral_ai.materials.generation.validation import OutputValidator

CONSTRAINTS = {
    "headline_max_words": 5,
    "subheadline_max_words": 8,
    "body_section_count": 2,
    "body_section_max_words": 10,
    "cta_max_words": 4,
}
IMAGE_SLOTS = [
    {
        "slot_id": "hero_image",
        "label": "Hero",
        "spec": "1200×630",  # noqa: RUF001
        "source": "generated_placeholder",
    },
    {"slot_id": "sender_logo", "label": "Logo", "spec": "SVG", "source": "sender"},
]
ALLOWED = {"SENDER_SOURCE_1", "RECEIVER_SOURCE_1"}


def valid_output() -> dict:
    return {
        "article": {
            "headline": "Smart warehouses now",
            "subheadline": "AI planning for modern logistics teams",
            "body_sections": [
                {
                    "title": "The Challenge",
                    "text": "Manual planning wastes hours weekly.",
                },
                {
                    "title": "The Solution",
                    "text": "Predictive AI removes the guesswork.",
                },
            ],
            "cta": "Book a demo",
        },
        "image_slots": [
            {
                "slot_id": "hero_image",
                "description": "warehouse",
                "source": "generated_placeholder",
            },
            {"slot_id": "sender_logo", "description": "logo", "source": "sender"},
        ],
        "source_references": [
            {"source_id": "SENDER_SOURCE_1", "used_fact": "AI planning claim"},
        ],
    }


def validate(output: dict):
    return OutputValidator().validate(
        output=output,
        constraints=CONSTRAINTS,
        image_slots=IMAGE_SLOTS,
        allowed_source_ids=ALLOWED,
    )


def categories(result) -> set[str]:
    return {e["category"] for e in result.errors}


def test_valid_output_passes():
    result = validate(valid_output())
    assert result.is_valid, result.errors
    assert result.to_dict() == {"is_valid": True, "errors": []}


def test_missing_article_field_is_structure_error():
    output = valid_output()
    del output["article"]["cta"]
    result = validate(output)
    assert not result.is_valid
    assert categories(result) == {"structure"}


def test_word_limit_violations():
    output = valid_output()
    output["article"]["headline"] = "one two three four five six"  # 6 > 5
    result = validate(output)
    assert categories(result) == {"word_limit"}


def test_wrong_body_section_count_is_word_limit_category():
    output = valid_output()
    output["article"]["body_sections"].append({"title": "Extra", "text": "x"})
    result = validate(output)
    assert not result.is_valid
    assert "word_limit" in categories(result)


def test_missing_and_mismatched_image_slots():
    output = valid_output()
    output["image_slots"] = [
        # wrong source
        {"slot_id": "hero_image", "description": "x", "source": "sender"},
    ]
    result = validate(output)
    assert categories(result) == {"image_slot"}


def test_unknown_source_id_and_empty_references():
    output = valid_output()
    output["source_references"] = [{"source_id": "NOPE_9", "used_fact": "x"}]
    assert categories(validate(output)) == {"source"}
    output["source_references"] = []
    assert categories(validate(output)) == {"source"}


def test_non_string_body_section_text_is_structure_error_not_a_crash():
    output = valid_output()
    output["article"]["body_sections"][0]["text"] = True
    result = validate(output)
    assert not result.is_valid
    assert categories(result) == {"structure"}


def test_non_dict_image_slot_entry_is_image_slot_error():
    output = valid_output()
    output["image_slots"].append("not-a-slot")
    result = validate(output)
    assert not result.is_valid
    assert categories(result) == {"image_slot"}


def test_duplicate_output_slot_id_is_image_slot_error():
    output = valid_output()
    output["image_slots"].append(
        {
            "slot_id": "hero_image",
            "description": "dup",
            "source": "generated_placeholder",
        },
    )
    result = validate(output)
    assert not result.is_valid
    assert categories(result) == {"image_slot"}


def test_whitespace_only_headline_is_structure_error():
    output = valid_output()
    output["article"]["headline"] = "   "
    result = validate(output)
    assert not result.is_valid
    assert categories(result) == {"structure"}


def test_inline_citation_token_in_body_section_is_source_error():
    output = valid_output()
    output["article"]["body_sections"][1]["text"] = (
        "Handles 50 million samples per second (RECEIVER_SOURCE_1)."
    )
    result = validate(output)
    assert not result.is_valid
    assert categories(result) == {"source"}
    messages = [e["message"] for e in result.errors]
    assert any("body_sections[2].text" in m for m in messages)


def test_clean_article_with_no_inline_citations_passes():
    result = validate(valid_output())
    assert result.is_valid, result.errors
