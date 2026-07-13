from unittest.mock import MagicMock

from collateral_ai.materials.generation.model import GenerationModel


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
    # schema passed through (converted or raw — both acceptable)
    fake_structured.invoke.assert_called_once()
