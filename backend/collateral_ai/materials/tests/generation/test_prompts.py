from __future__ import annotations

import json
from unittest.mock import MagicMock

from collateral_ai.materials.generation.prompts import SYSTEM_INSTRUCTION
from collateral_ai.materials.generation.prompts import build_generation_payload


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
