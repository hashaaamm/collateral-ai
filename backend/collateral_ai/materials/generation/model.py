"""Provider-swappable LangChain chat model for structured generation.

Default provider is Vertex AI Gemini (keyless ADC), same auth as
documents.processing.embeddings. Provider is selected by MATERIAL_LLM_PROVIDER
so the model can be swapped (e.g. Claude on Vertex, OpenAI) without touching the
graph.
"""

from __future__ import annotations

from django.conf import settings

_TYPE_MAP = {
    "OBJECT": "object",
    "STRING": "string",
    "ARRAY": "array",
    "INTEGER": "integer",
    "NUMBER": "number",
    "BOOLEAN": "boolean",
}


def _to_json_schema(node):
    if isinstance(node, dict):
        out = {}
        for key, value in node.items():
            if key == "type" and isinstance(value, str):
                out[key] = _TYPE_MAP.get(value, value.lower())
            else:
                out[key] = _to_json_schema(value)
        return out
    if isinstance(node, list):
        return [_to_json_schema(item) for item in node]
    return node


class GenerationModel:
    def __init__(self) -> None:
        self.provider = settings.MATERIAL_LLM_PROVIDER
        self.model = settings.MATERIAL_LLM_MODEL
        self.temperature = float(settings.MATERIAL_GENERATION_TEMPERATURE)
        self.max_output_tokens = int(settings.MATERIAL_GENERATION_MAX_OUTPUT_TOKENS)

    def _build_chat_model(self):
        if self.provider == "vertex":
            from langchain_google_vertexai import ChatVertexAI

            return ChatVertexAI(
                model=self.model,
                project=settings.GOOGLE_CLOUD_PROJECT,
                location=settings.VERTEX_LOCATION,
                temperature=self.temperature,
                max_output_tokens=self.max_output_tokens,
                # Disable thinking so the full budget goes to JSON output.
                thinking_budget=0,
            )
        msg = f"Unsupported MATERIAL_LLM_PROVIDER: {self.provider}"
        raise ValueError(msg)

    def generate_structured(
        self,
        *,
        system_instruction: str,
        user_input: str,
        response_schema: dict,
    ) -> dict:
        from langchain_core.messages import HumanMessage
        from langchain_core.messages import SystemMessage

        chat = self._build_chat_model()
        json_schema = _to_json_schema(response_schema)
        json_schema.setdefault("title", "MarketingMaterial")
        json_schema.setdefault(
            "description",
            "Structured B2B marketing material output.",
        )
        structured = chat.with_structured_output(json_schema)
        result = structured.invoke(
            [
                SystemMessage(content=system_instruction),
                HumanMessage(content=user_input),
            ],
        )
        if not isinstance(result, dict):
            # with_structured_output may return a pydantic model; normalize.
            result = dict(result)
        return result
