"""Provider-swappable LangChain chat model for structured generation.

Default provider is Vertex AI Gemini (keyless ADC), same auth as
documents.processing.embeddings. Provider is selected by MATERIAL_LLM_PROVIDER
so the model can be swapped (e.g. Claude on Vertex, OpenAI) without touching the
graph.

Structured output is bound natively via Vertex's response_schema /
response_mime_type generation-config knobs rather than LangChain's
with_structured_output (function-calling mode), which was proven via live A/B
to produce catastrophically ungrounded output on this model/schema.
"""

from __future__ import annotations

from django.conf import settings

_VERTEX_KEY_RENAMES = {"minItems": "min_items", "maxItems": "max_items"}


def _to_vertex_schema(node):
    """Rename camelCase item bounds to the snake_case the Vertex proto expects."""
    if isinstance(node, dict):
        return {
            _VERTEX_KEY_RENAMES.get(k, k): _to_vertex_schema(v) for k, v in node.items()
        }
    if isinstance(node, list):
        return [_to_vertex_schema(item) for item in node]
    return node


class GenerationModel:
    def __init__(self) -> None:
        self.provider = settings.MATERIAL_LLM_PROVIDER
        self.model = settings.MATERIAL_LLM_MODEL
        self.temperature = float(settings.MATERIAL_GENERATION_TEMPERATURE)
        self.max_output_tokens = int(settings.MATERIAL_GENERATION_MAX_OUTPUT_TOKENS)

    def _build_chat_model(self, *, response_schema: dict | None = None):
        if self.provider == "vertex":
            from langchain_google_vertexai import ChatVertexAI

            kwargs = {}
            if response_schema is not None:
                kwargs["response_mime_type"] = "application/json"
                kwargs["response_schema"] = _to_vertex_schema(response_schema)

            return ChatVertexAI(
                model=self.model,
                project=settings.GOOGLE_CLOUD_PROJECT,
                location=settings.VERTEX_LOCATION,
                temperature=self.temperature,
                max_output_tokens=self.max_output_tokens,
                # Disable thinking so the full budget goes to JSON output.
                thinking_budget=0,
                **kwargs,
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
        import json

        from langchain_core.messages import HumanMessage
        from langchain_core.messages import SystemMessage

        chat = self._build_chat_model(response_schema=response_schema)
        response = chat.invoke(
            [
                SystemMessage(content=system_instruction),
                HumanMessage(content=user_input),
            ],
        )
        text = (
            response.content
            if isinstance(response.content, str)
            else str(response.content)
        )
        if not text:
            msg = "Gemini returned an empty response."
            raise ValueError(msg)
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            msg = f"Gemini returned invalid JSON: {text[:500]}"
            raise ValueError(msg) from exc
