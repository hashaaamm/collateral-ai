"""Structured generation via the native google-genai SDK (keyless ADC).

Provider-swappable: the `vertex` branch calls google-genai directly because a
controlled A/B showed langchain-google-vertexai's request path catastrophically
degrades grounding on real payloads (hallucinated companies, 0 grounded terms)
in both function-calling and native-schema binding, while the raw client
grounds reliably. Other providers can be added as LangChain chat models behind
the same generate_structured interface.
"""

from __future__ import annotations

import json

from django.conf import settings


class GenerationModel:
    def __init__(self) -> None:
        self.provider = settings.MATERIAL_LLM_PROVIDER
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

    def generate_structured(
        self,
        *,
        system_instruction: str,
        user_input: str,
        response_schema: dict,
    ) -> dict:
        if self.provider != "vertex":
            msg = f"Unsupported MATERIAL_LLM_PROVIDER: {self.provider}"
            raise ValueError(msg)
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
                # Thinking disabled so the full token budget goes to the JSON output.
                thinking_config=types.ThinkingConfig(thinking_budget=0),
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
