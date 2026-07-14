"""Per-document summary for generation grounding (google-genai, keyless ADC).

Summaries are orientation-only background for material generation (spec §5.2);
they are best-effort and must never block ingestion — the pipeline catches
failures and stores a blank summary.
"""

from __future__ import annotations

from django.conf import settings

SUMMARY_SYSTEM_INSTRUCTION = (
    "You summarize business documents for a B2B marketing content system. "
    "Write a factual plain-prose summary of at most {max_words} words. "
    "Capture: what the company and product are, key capabilities, positioning, "
    "concrete metrics and proof points, target industries, and the pain points "
    "addressed. No markdown, no bullet points, no hype."
)


class DocumentSummaryService:
    def __init__(self) -> None:
        self.model = settings.DOCUMENT_SUMMARY_MODEL
        self.input_max_words = int(settings.DOCUMENT_SUMMARY_INPUT_MAX_WORDS)
        self.max_words = int(settings.DOCUMENT_SUMMARY_MAX_WORDS)

    def _client(self):
        from google import genai

        return genai.Client(
            vertexai=True,
            project=settings.GOOGLE_CLOUD_PROJECT,
            location=settings.VERTEX_LOCATION,
        )

    def summarize(self, texts: list[str]) -> str:
        words = " ".join(text for text in texts if text).split()
        if not words:
            return ""
        from google.genai import types

        response = self._client().models.generate_content(
            model=self.model,
            contents=" ".join(words[: self.input_max_words]),
            config=types.GenerateContentConfig(
                system_instruction=SUMMARY_SYSTEM_INSTRUCTION.format(
                    max_words=self.max_words,
                ),
                temperature=0.1,
                max_output_tokens=1024,
                # Thinking disabled: short factual summary, spend tokens on output.
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        return (getattr(response, "text", None) or "").strip()
