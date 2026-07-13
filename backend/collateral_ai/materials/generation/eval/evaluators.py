"""Offline evaluators for material generation experiments.

Deterministic checks plus an LLM-as-judge groundedness score. Never run in the
live request path.
"""

from __future__ import annotations

import json

from django.conf import settings

from collateral_ai.materials.generation.validation import OutputValidator


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


_JUDGE_PROMPT = """You grade groundedness of marketing copy against source context.
Return ONLY a number between 0 and 1 (1 = every used_fact is supported by the
cited context; 0 = fabricated). Output JSON: {{"score": <number>}}.

source_references: {refs}
sender_context: {sender}
receiver_context: {receiver}
"""


def _default_judge(prompt: str) -> str:
    from langchain_core.messages import HumanMessage
    from langchain_google_vertexai import ChatVertexAI

    chat = ChatVertexAI(
        model=settings.MATERIAL_EVAL_JUDGE_MODEL,
        project=settings.GOOGLE_CLOUD_PROJECT,
        location=settings.VERTEX_LOCATION,
        temperature=0.0,
    )
    return chat.invoke([HumanMessage(content=prompt)]).content


def groundedness_judge(output: dict, context: dict, *, judge=None) -> float:
    judge = judge or _default_judge
    prompt = _JUDGE_PROMPT.format(
        refs=json.dumps(output.get("source_references", [])),
        sender=json.dumps(context.get("sender_context", [])),
        receiver=json.dumps(context.get("receiver_context", [])),
    )
    raw = judge(prompt).strip()
    try:
        return float(json.loads(raw)["score"])
    except (json.JSONDecodeError, KeyError, TypeError):
        return float(raw)
