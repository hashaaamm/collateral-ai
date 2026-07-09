from __future__ import annotations

import json
from unittest import mock

import pytest

from collateral_ai.materials.generation.llm import GenerationClient
from collateral_ai.materials.generation.prompts import build_generation_payload
from collateral_ai.materials.generation.prompts import build_retrieval_query
from collateral_ai.materials.generation.repair import OutputRepairService
from collateral_ai.materials.generation.retrieval import RetrievedChunk
from collateral_ai.materials.statuses import SourceRole
from collateral_ai.materials.tests.factories import MarketingMaterialFactory

pytestmark = pytest.mark.django_db


def chunk(source_id: str, role: str) -> RetrievedChunk:
    return RetrievedChunk(
        source_id=source_id,
        chunk_id=1,
        document_id=1,
        company_id=1,
        file_name="doc.pdf",
        page_number=2,
        chunk_type="text",
        content="Acme reduces planning time by 40%.",
        relevance_score=0.1,
        source_role=role,
    )


def test_retrieval_query_mentions_prompt_and_companies():
    material = MarketingMaterialFactory(prompt="Pitch warehouse AI")
    query = build_retrieval_query(material)
    assert "Pitch warehouse AI" in query
    assert material.sender_company.name in query
    assert material.receiver_company.name in query


def test_generation_payload_is_json_with_context_and_constraints():
    material = MarketingMaterialFactory()
    payload = json.loads(
        build_generation_payload(
            material=material,
            sender_chunks=[chunk("SENDER_SOURCE_1", SourceRole.SENDER)],
            receiver_chunks=[chunk("RECEIVER_SOURCE_1", SourceRole.RECEIVER)],
        ),
    )
    assert payload["material_prompt"] == material.prompt
    assert payload["template"]["constraints"] == material.template.constraints
    assert payload["sender_context"][0]["source_id"] == "SENDER_SOURCE_1"
    assert payload["receiver_context"][0]["source_id"] == "RECEIVER_SOURCE_1"
    # theme is server-stamped, so the model has no reason to see or echo it
    assert "theme" not in payload["template"]


def test_generation_client_parses_json_response(settings):
    settings.GOOGLE_CLOUD_PROJECT = "proj"
    fake_response = mock.Mock(text='{"ok": true}')
    with mock.patch("google.genai.Client") as client_cls:
        client_cls.return_value.models.generate_content.return_value = fake_response
        result = GenerationClient().generate_json(
            system_instruction="sys",
            user_input="{}",
            response_schema={"type": "OBJECT"},
        )
    assert result == {"ok": True}
    config = client_cls.return_value.models.generate_content.call_args.kwargs["config"]
    assert config.response_mime_type == "application/json"


def test_generation_client_raises_on_empty_and_invalid_json(settings):
    settings.GOOGLE_CLOUD_PROJECT = "proj"
    for text in ("", "not json"):
        fake_response = mock.Mock(text=text)
        with mock.patch("google.genai.Client") as client_cls:
            client_cls.return_value.models.generate_content.return_value = fake_response
            with pytest.raises(ValueError, match="Gemini"):
                GenerationClient().generate_json(
                    system_instruction="sys",
                    user_input="{}",
                    response_schema={"type": "OBJECT"},
                )


def test_repair_calls_client_with_errors_and_same_schema():
    client = mock.Mock()
    client.generate_json.return_value = {"fixed": True}
    schema = {"type": "OBJECT"}
    result = OutputRepairService(client).repair(
        output={"bad": True},
        errors=[{"category": "word_limit", "message": "too long"}],
        constraints={"headline_max_words": 10},
        image_slots=[],
        allowed_source_ids=["SENDER_SOURCE_1"],
        response_schema=schema,
    )
    assert result == {"fixed": True}
    kwargs = client.generate_json.call_args.kwargs
    assert kwargs["response_schema"] is schema
    assert "too long" in kwargs["user_input"]
