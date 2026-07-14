import json
from unittest.mock import MagicMock

import pytest

from collateral_ai.materials.generation.model import GenerationModel
from collateral_ai.materials.generation.model import _to_vertex_schema


def test_to_vertex_schema_renames_item_bounds_recursively():
    schema = {
        "type": "ARRAY",
        "minItems": 1,
        "maxItems": 2,
        "items": {"maxItems": 0},
    }

    result = _to_vertex_schema(schema)

    assert result["type"] == "ARRAY"
    assert result["min_items"] == 1
    assert result["max_items"] == 2
    assert "minItems" not in result
    assert "maxItems" not in result
    assert result["items"]["max_items"] == 0
    assert "maxItems" not in result["items"]


def test_generate_structured_binds_schema_and_returns_dict(monkeypatch):
    fake_response = MagicMock()
    fake_response.content = json.dumps({"article": {"headline": "Hi"}})
    fake_chat = MagicMock()
    fake_chat.invoke.return_value = fake_response

    captured = {}

    def fake_build_chat_model(*, response_schema=None):
        captured["response_schema"] = response_schema
        return fake_chat

    model = GenerationModel()
    monkeypatch.setattr(model, "_build_chat_model", fake_build_chat_model)

    schema = {"type": "OBJECT", "properties": {}}
    result = model.generate_structured(
        system_instruction="sys",
        user_input="user",
        response_schema=schema,
    )

    assert result == {"article": {"headline": "Hi"}}
    fake_chat.invoke.assert_called_once()
    assert captured["response_schema"] == schema


def test_generate_structured_raises_on_empty_content(monkeypatch):
    fake_response = MagicMock()
    fake_response.content = ""
    fake_chat = MagicMock()
    fake_chat.invoke.return_value = fake_response

    model = GenerationModel()
    monkeypatch.setattr(
        model,
        "_build_chat_model",
        lambda *, response_schema=None: fake_chat,
    )

    with pytest.raises(ValueError, match="empty"):
        model.generate_structured(
            system_instruction="sys",
            user_input="user",
            response_schema={"type": "OBJECT"},
        )


def test_generate_structured_raises_on_invalid_json(monkeypatch):
    fake_response = MagicMock()
    fake_response.content = "not json"
    fake_chat = MagicMock()
    fake_chat.invoke.return_value = fake_response

    model = GenerationModel()
    monkeypatch.setattr(
        model,
        "_build_chat_model",
        lambda *, response_schema=None: fake_chat,
    )

    with pytest.raises(ValueError, match="invalid JSON"):
        model.generate_structured(
            system_instruction="sys",
            user_input="user",
            response_schema={"type": "OBJECT"},
        )
