from unittest.mock import MagicMock

from collateral_ai.materials.generation.model import GenerationModel
from collateral_ai.materials.generation.model import _to_json_schema


def test_to_json_schema_lowercases_types_recursively():
    vertex_schema = {
        "type": "OBJECT",
        "properties": {
            "headline": {"type": "STRING", "enum": ["a", "b"]},
            "tags": {
                "type": "ARRAY",
                "minItems": 1,
                "maxItems": 5,
                "items": {"type": "STRING"},
            },
            "nested": {
                "type": "OBJECT",
                "properties": {"count": {"type": "INTEGER"}},
                "required": ["count"],
            },
        },
        "required": ["headline", "tags"],
    }

    result = _to_json_schema(vertex_schema)

    assert result["type"] == "object"
    assert result["properties"]["headline"]["type"] == "string"
    assert result["properties"]["headline"]["enum"] == ["a", "b"]
    assert result["properties"]["tags"]["type"] == "array"
    assert result["properties"]["tags"]["minItems"] == 1
    assert result["properties"]["tags"]["maxItems"] == 5
    assert result["properties"]["tags"]["items"]["type"] == "string"
    assert result["properties"]["nested"]["type"] == "object"
    assert result["properties"]["nested"]["properties"]["count"]["type"] == "integer"
    assert result["properties"]["nested"]["required"] == ["count"]
    assert result["required"] == ["headline", "tags"]


def test_generate_structured_binds_schema_and_returns_dict(monkeypatch):
    fake_structured = MagicMock()
    fake_structured.invoke.return_value = {"article": {"headline": "Hi"}}
    fake_chat = MagicMock()
    fake_chat.with_structured_output.return_value = fake_structured

    model = GenerationModel()
    monkeypatch.setattr(model, "_build_chat_model", lambda: fake_chat)

    schema = {"type": "OBJECT", "properties": {}}
    result = model.generate_structured(
        system_instruction="sys",
        user_input="user",
        response_schema=schema,
    )

    assert result == {"article": {"headline": "Hi"}}
    fake_chat.with_structured_output.assert_called_once()
    fake_structured.invoke.assert_called_once()

    passed_schema = fake_chat.with_structured_output.call_args[0][0]
    assert passed_schema["type"] == "object"
    assert "title" in passed_schema
    assert "description" in passed_schema
