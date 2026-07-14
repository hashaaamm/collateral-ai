import json
from unittest.mock import MagicMock

import pytest

from collateral_ai.materials.generation.model import GenerationModel


def _fake_client(captured, *, text='{"article": {"headline": "Hi"}}'):
    fake_response = MagicMock()
    fake_response.text = text

    def fake_generate_content(*, model, contents, config):
        captured["model"] = model
        captured["contents"] = contents
        captured["config"] = config
        return fake_response

    fake_client = MagicMock()
    fake_client.models.generate_content = fake_generate_content
    return fake_client


def test_generate_structured_returns_parsed_dict_and_passes_call_args(monkeypatch):
    captured = {}
    model = GenerationModel()
    monkeypatch.setattr(model, "_client", lambda: _fake_client(captured))

    schema = {"type": "OBJECT", "properties": {}}
    result = model.generate_structured(
        system_instruction="sys",
        user_input="user",
        response_schema=schema,
    )

    assert result == {"article": {"headline": "Hi"}}
    assert captured["model"] == model.model
    assert captured["contents"] == "user"
    assert captured["config"].response_schema == schema
    assert captured["config"].system_instruction == "sys"


def test_generate_structured_raises_on_empty_text(monkeypatch):
    captured = {}
    model = GenerationModel()
    monkeypatch.setattr(model, "_client", lambda: _fake_client(captured, text=""))

    with pytest.raises(ValueError, match="empty"):
        model.generate_structured(
            system_instruction="sys",
            user_input="user",
            response_schema={"type": "OBJECT"},
        )


def test_generate_structured_raises_on_invalid_json(monkeypatch):
    captured = {}
    model = GenerationModel()
    monkeypatch.setattr(
        model,
        "_client",
        lambda: _fake_client(captured, text="not json"),
    )

    with pytest.raises(ValueError, match="invalid JSON"):
        model.generate_structured(
            system_instruction="sys",
            user_input="user",
            response_schema={"type": "OBJECT"},
        )


def test_generate_structured_raises_on_unsupported_provider(monkeypatch):
    model = GenerationModel()
    monkeypatch.setattr(model, "provider", "openai")

    with pytest.raises(ValueError, match="Unsupported MATERIAL_LLM_PROVIDER"):
        model.generate_structured(
            system_instruction="sys",
            user_input="user",
            response_schema={"type": "OBJECT"},
        )


def test_generate_structured_parses_json_dumped_payload(monkeypatch):
    captured = {}
    model = GenerationModel()
    payload = {"article": {"headline": "Hi", "body": ["a", "b"]}}
    monkeypatch.setattr(
        model,
        "_client",
        lambda: _fake_client(captured, text=json.dumps(payload)),
    )

    result = model.generate_structured(
        system_instruction="sys",
        user_input="user",
        response_schema={"type": "OBJECT"},
    )

    assert result == payload
