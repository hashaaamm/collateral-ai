from __future__ import annotations

import json
from unittest.mock import MagicMock

from collateral_ai.materials.generation.prompts import REPAIR_SYSTEM_INSTRUCTION
from collateral_ai.materials.generation.prompts import SYSTEM_INSTRUCTION
from collateral_ai.materials.generation.prompts import build_generation_payload
from collateral_ai.materials.generation.prompts import build_repair_payload


def _material():
    material = MagicMock()
    material.prompt = "Introduce our product."
    material.tone = "professional"
    material.cta_style = "direct"
    material.language = "en"
    for attr, name in (
        ("sender_company", "Sender Co"),
        ("receiver_company", "Receiver Co"),
    ):
        company = MagicMock()
        company.pk = 1
        company.name = name
        company.industry = "software"
        company.description = "A company."
        setattr(material, attr, company)
    material.template.name = "Newsletter"
    material.template.constraints = {"headline_max_words": 10}
    return material


def test_payload_includes_document_summaries():
    payload = json.loads(
        build_generation_payload(
            material=_material(),
            sender_chunks=[],
            receiver_chunks=[],
            sender_document_summaries=[{"file_name": "a.pdf", "summary": "About A."}],
            receiver_document_summaries=[{"file_name": "b.pdf", "summary": "About B."}],
        ),
    )
    assert payload["sender_document_summaries"] == [
        {"file_name": "a.pdf", "summary": "About A."},
    ]
    assert payload["receiver_document_summaries"] == [
        {"file_name": "b.pdf", "summary": "About B."},
    ]


def test_payload_omits_empty_summaries():
    payload = json.loads(
        build_generation_payload(
            material=_material(),
            sender_chunks=[],
            receiver_chunks=[],
        ),
    )
    assert "sender_document_summaries" not in payload
    assert "receiver_document_summaries" not in payload


def test_system_instruction_marks_summaries_uncitable():
    assert "sender_document_summaries" in SYSTEM_INSTRUCTION
    assert "orientation-only" in SYSTEM_INSTRUCTION


def test_system_instruction_steers_below_word_budgets():
    assert "BELOW its max_words" in SYSTEM_INSTRUCTION


def test_repair_instruction_targets_eighty_percent_rewrite():
    assert "80% of its max words" in REPAIR_SYSTEM_INSTRUCTION


def test_repair_payload_carries_length_target():
    payload = json.loads(
        build_repair_payload(
            output={"article": {}},
            errors=[{"category": "word_limit", "message": "too long"}],
            constraints={"body_section_max_words": 90},
            image_slots=[],
            allowed_source_ids=["SENDER_SOURCE_1"],
        ),
    )
    assert "80% of its max words" in payload["instruction"]
