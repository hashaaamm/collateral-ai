"""Gemini structured-output generation via Vertex AI (keyless ADC).

Same client pattern as documents.processing.embeddings.EmbeddingService.
"""

from __future__ import annotations

import json

from django.conf import settings


class GenerationClient:
    def __init__(self) -> None:
        self.model = settings.MATERIAL_LLM_MODEL
        self.temperature = float(settings.MATERIAL_GENERATION_TEMPERATURE)
        self.max_output_tokens = int(settings.MATERIAL_GENERATION_MAX_OUTPUT_TOKENS)

    def _client(self):
        from google import genai

        return genai.Client(
            vertexai=True,
            project=settings.GOOGLE_CLOUD_PROJECT,
            location=settings.VERTEX_LOCATION,
        )

    def generate_json(
        self,
        *,
        system_instruction: str,
        user_input: str,
        response_schema: dict,
    ) -> dict:
        from google.genai import types

        response = self._client().models.generate_content(
            model=self.model,
            contents=user_input,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=self.temperature,
                max_output_tokens=self.max_output_tokens,
                response_mime_type="application/json",
                response_schema=response_schema,
            ),
        )
        text = getattr(response, "text", None)
        if not text:
            msg = "Gemini returned an empty response."
            raise ValueError(msg)
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            msg = f"Gemini returned invalid JSON: {text[:500]}"
            raise ValueError(msg) from exc
