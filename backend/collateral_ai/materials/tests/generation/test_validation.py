from __future__ import annotations

from collateral_ai.materials.generation.validation import OutputValidator
from collateral_ai.materials.generation.validation import trim_to_word_limits

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


def _overlimit_output():
    return {
        "article": {
            "headline": "Short headline",
            "subheadline": "Sub",
            "body_sections": [
                {
                    "title": "T",
                    "text": "First sentence stays. " + "word " * 90 + "ends here.",
                },
            ],
            "cta": "Act now",
        },
        "image_slots": [],
        "source_references": [{"source_id": "SENDER_SOURCE_1", "used_fact": "f"}],
    }


def _constraints():
    return {
        "headline_max_words": 10,
        "subheadline_max_words": 22,
        "body_section_count": 1,
        "body_section_max_words": 80,
        "cta_max_words": 15,
    }


def test_word_limit_errors_carry_machine_path_and_max():
    result = OutputValidator().validate(
        output=_overlimit_output(),
        constraints=_constraints(),
        image_slots=[],
        allowed_source_ids={"SENDER_SOURCE_1"},
    )
    [error] = [e for e in result.errors if e["category"] == "word_limit"]
    assert error["path"] == ["article", "body_sections", 0, "text"]
    assert error["max_words"] == 80


def test_trim_drops_trailing_sentences_to_fit():
    output = _overlimit_output()
    result = OutputValidator().validate(
        output=output,
        constraints=_constraints(),
        image_slots=[],
        allowed_source_ids={"SENDER_SOURCE_1"},
    )
    trimmed = trim_to_word_limits(output, result.errors)
    assert trimmed is not None
    assert trimmed["article"]["body_sections"][0]["text"] == "First sentence stays."
    # original untouched
    assert output["article"]["body_sections"][0]["text"].startswith(
        "First sentence stays. word",
    )
    revalidated = OutputValidator().validate(
        output=trimmed,
        constraints=_constraints(),
        image_slots=[],
        allowed_source_ids={"SENDER_SOURCE_1"},
    )
    assert revalidated.is_valid


def test_trim_gives_up_on_non_word_limit_errors():
    errors = [
        {
            "category": "word_limit",
            "path": ["article", "cta"],
            "max_words": 15,
            "message": "m",
        },
        {"category": "source", "message": "bad source"},
    ]
    assert trim_to_word_limits(_overlimit_output(), errors) is None


def test_trim_gives_up_when_single_sentence_exceeds_limit():
    output = _overlimit_output()
    output["article"]["body_sections"][0]["text"] = "word " * 90
    errors = [
        {
            "category": "word_limit",
            "path": ["article", "body_sections", 0, "text"],
            "max_words": 80,
            "message": "m",
        },
    ]
    assert trim_to_word_limits(output, errors) is None


def test_trim_gives_up_on_pathless_word_limit_error():
    errors = [{"category": "word_limit", "message": "Expected 3 body sections, got 2."}]
    assert trim_to_word_limits(_overlimit_output(), errors) is None
