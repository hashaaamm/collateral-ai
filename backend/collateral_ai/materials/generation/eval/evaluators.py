"""Offline evaluators for material generation experiments.

Deterministic checks plus an LLM-as-judge groundedness score. Never run in the
live request path.
"""

from __future__ import annotations

import json
import re
import time

from django.conf import settings

from collateral_ai.materials.generation.validation import INLINE_CITATION_RE
from collateral_ai.materials.generation.validation import OutputValidator

_SCORE_RE = re.compile(r"-?\d+(?:\.\d+)?")


def _parse_score(raw: str) -> float:
    """Robustly extract a 0..1 score from noisy/flaky judge output.

    Handles fenced JSON, bare JSON, plain numbers embedded in prose, and
    falls back to 0.0 (never raises) when nothing parseable is found.
    """
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict) and "score" in parsed:
            return _clamp(float(parsed["score"]))
        if isinstance(parsed, (int, float)):
            return _clamp(float(parsed))
    except (json.JSONDecodeError, TypeError, ValueError):
        pass

    match = _SCORE_RE.search(text)
    if match:
        try:
            return _clamp(float(match.group()))
        except ValueError:
            return 0.0
    return 0.0


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def schema_valid(output: dict, template) -> bool:
    result = OutputValidator().validate(
        output=output,
        constraints=template.constraints,
        image_slots=template.image_slots,
        allowed_source_ids={
            ref.get("source_id") for ref in output.get("source_references", [])
        },
    )
    return result.is_valid


def sources_grounded(output: dict, allowed_ids: set[str]) -> bool:
    refs = output.get("source_references", [])
    if not refs:
        return False
    return all(ref.get("source_id") in allowed_ids for ref in refs)


def counts_match(output: dict, template) -> bool:
    expected = template.constraints["body_section_count"]
    sections = output.get("article", {}).get("body_sections", [])
    slots_ok = len(output.get("image_slots", [])) == len(template.image_slots)
    return len(sections) == expected and slots_ok


def no_inline_citations(output: dict) -> bool:
    article = output.get("article", {})
    fields = [article.get("headline"), article.get("subheadline"), article.get("cta")]
    for section in article.get("body_sections", []):
        if isinstance(section, dict):
            fields.append(section.get("title"))
            fields.append(section.get("text"))
    return not any(
        isinstance(value, str) and INLINE_CITATION_RE.search(value) for value in fields
    )


_JUDGE_PROMPT = """You grade groundedness of marketing copy against source context.
Return ONLY a number between 0 and 1 (1 = every used_fact is supported by the
cited context; 0 = fabricated). Output JSON: {{"score": <number>}}.

source_references: {refs}
sender_context: {sender}
receiver_context: {receiver}
"""


_MAX_JUDGE_ATTEMPTS = 3


def _is_transient_error(exc: Exception) -> bool:
    haystack = f"{type(exc).__name__} {exc}".lower()
    return "429" in haystack or "resourceexhausted" in haystack


def _judge_client():
    from google import genai

    return genai.Client(
        vertexai=True,
        project=settings.GOOGLE_CLOUD_PROJECT,
        location=settings.VERTEX_LOCATION,
    )


def _default_judge(prompt: str) -> str:
    from google.genai import types

    for attempt in range(1, _MAX_JUDGE_ATTEMPTS + 1):
        try:
            response = _judge_client().models.generate_content(
                model=settings.MATERIAL_EVAL_JUDGE_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.0),
            )
        except Exception as exc:  # noqa: BLE001 - judge must never raise
            if attempt >= _MAX_JUDGE_ATTEMPTS or not _is_transient_error(exc):
                return ""
            time.sleep(2 * attempt)
        else:
            return response.text or ""
    return ""


def groundedness_judge(output: dict, context: dict, *, judge=None) -> float:
    judge = judge or _default_judge
    prompt = _JUDGE_PROMPT.format(
        refs=json.dumps(output.get("source_references", [])),
        sender=json.dumps(context.get("sender_context", [])),
        receiver=json.dumps(context.get("receiver_context", [])),
    )
    return _parse_score(judge(prompt))


_SPECIFICITY_PROMPT = """You grade how SPECIFIC and concrete B2B marketing copy is.
Return ONLY JSON: {{"score": <number 0..1>}}.
1.0 = names concrete products/numbers/facts specific to these two companies;
0.0 = generic filler that could describe any company (buzzwords like "revolutionize",
"cutting-edge", "unlock", "the future of", "game-changing" with no concrete referent).

article: {article}
"""


def specificity_judge(output: dict, *, judge=None) -> float:
    judge = judge or _default_judge
    prompt = _SPECIFICITY_PROMPT.format(article=json.dumps(output.get("article", {})))
    return _parse_score(judge(prompt))
