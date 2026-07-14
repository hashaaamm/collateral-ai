"""LangGraph pipeline for material generation: retrieve → generate → validate ⇄ repair.

Flow (edges wired in build_generation_graph):

    START → retrieve → generate → validate ──(valid, or out of attempts)──→ END
                                      │  ↑
                        (invalid, attempts left)
                                      ↓  │
                                     repair

Nodes are module-level functions taking (state, deps); build_generation_graph
binds deps and wires the edges. The service owns the DB state machine — this
module owns compute only and never touches the database rows.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from typing import Any
from typing import TypedDict

from django.conf import settings

from collateral_ai.materials.generation.prompts import REPAIR_SYSTEM_INSTRUCTION
from collateral_ai.materials.generation.prompts import SYSTEM_INSTRUCTION
from collateral_ai.materials.generation.prompts import build_generation_payload
from collateral_ai.materials.generation.prompts import build_repair_payload
from collateral_ai.materials.generation.prompts import build_retrieval_query
from collateral_ai.materials.generation.retrieval import fetch_document_summaries
from collateral_ai.materials.generation.schema import build_response_schema
from collateral_ai.materials.generation.validation import ValidationResult
from collateral_ai.materials.generation.validation import trim_to_word_limits
from collateral_ai.materials.statuses import SourceRole


@dataclass(frozen=True)
class GenerationDeps:
    """Everything the graph nodes need, injected by the service."""

    embedder: Any
    retriever: Any
    model: Any
    validator: Any
    max_repair_attempts: int


@dataclass(frozen=True)
class RetrievedContext:
    """Output of the retrieve node: grounding context + citation guardrails."""

    query_embedding: list[float]
    sender_chunks: list[Any]
    receiver_chunks: list[Any]
    sender_document_summaries: list[dict]
    receiver_document_summaries: list[dict]
    source_map: dict[str, Any]
    allowed_ids: set[str]
    response_schema: dict
    context_snapshot: dict


class GenerationState(TypedDict, total=False):
    material_id: int
    material: Any
    template: Any
    top_k: int
    retrieval: RetrievedContext
    output: dict
    validation: ValidationResult
    attempts: int


def _require_chunks(material, sender_chunks, receiver_chunks) -> None:
    for role, chunks, company in (
        ("sender", sender_chunks, material.sender_company),
        ("receiver", receiver_chunks, material.receiver_company),
    ):
        if not chunks:
            msg = (
                f"No processed document chunks for {role} company "
                f"{company.name!r} — upload and process documents first."
            )
            raise ValueError(msg)


def _document_summaries(sender_chunks, receiver_chunks) -> tuple[list, list]:
    if not settings.MATERIAL_INCLUDE_DOC_SUMMARIES:
        return [], []
    return (
        fetch_document_summaries(sender_chunks),
        fetch_document_summaries(receiver_chunks),
    )


def _stamp(output: dict, template, material) -> dict:
    output["template_id"] = template.slug
    output["theme"] = dict(template.theme)
    output["image_slots"] = [
        {"slot_id": slot["slot_id"], "source": slot["source"], "description": ""}
        for slot in template.image_slots
    ]
    if material.cta_link:
        output.setdefault("article", {})["cta_url"] = material.cta_link
    return output


def retrieve(state: GenerationState, deps: GenerationDeps) -> dict:
    material = state["material"]
    query_embedding = deps.embedder.embed_query(build_retrieval_query(material))
    sender_chunks = deps.retriever.retrieve(
        company_id=material.sender_company_id,
        query_embedding=query_embedding,
        source_role=SourceRole.SENDER,
        source_prefix="SENDER_SOURCE",
        top_k=state["top_k"],
    )
    receiver_chunks = deps.retriever.retrieve(
        company_id=material.receiver_company_id,
        query_embedding=query_embedding,
        source_role=SourceRole.RECEIVER,
        source_prefix="RECEIVER_SOURCE",
        top_k=state["top_k"],
    )
    _require_chunks(material, sender_chunks, receiver_chunks)
    sender_summaries, receiver_summaries = _document_summaries(
        sender_chunks,
        receiver_chunks,
    )
    source_map = {c.source_id: c for c in [*sender_chunks, *receiver_chunks]}
    allowed_ids = set(source_map)
    retrieval = RetrievedContext(
        query_embedding=query_embedding,
        sender_chunks=sender_chunks,
        receiver_chunks=receiver_chunks,
        sender_document_summaries=sender_summaries,
        receiver_document_summaries=receiver_summaries,
        source_map=source_map,
        allowed_ids=allowed_ids,
        response_schema=build_response_schema(
            constraints=state["template"].constraints,
            allowed_source_ids=sorted(allowed_ids),
        ),
        context_snapshot={
            "sender_context": [c.to_prompt_dict() for c in sender_chunks],
            "receiver_context": [c.to_prompt_dict() for c in receiver_chunks],
            "sender_document_summaries": sender_summaries,
            "receiver_document_summaries": receiver_summaries,
        },
    )
    return {"retrieval": retrieval}


def generate(state: GenerationState, deps: GenerationDeps) -> dict:
    retrieval = state["retrieval"]
    output = deps.model.generate_structured(
        system_instruction=SYSTEM_INSTRUCTION,
        user_input=build_generation_payload(
            material=state["material"],
            sender_chunks=retrieval.sender_chunks,
            receiver_chunks=retrieval.receiver_chunks,
            sender_document_summaries=retrieval.sender_document_summaries,
            receiver_document_summaries=retrieval.receiver_document_summaries,
        ),
        response_schema=retrieval.response_schema,
    )
    return {"output": _stamp(output, state["template"], state["material"])}


def validate(state: GenerationState, deps: GenerationDeps) -> dict:
    result = deps.validator.validate(
        output=state["output"],
        constraints=state["template"].constraints,
        image_slots=state["template"].image_slots,
        allowed_source_ids=state["retrieval"].allowed_ids,
    )
    return {"validation": result}


def repair(state: GenerationState, deps: GenerationDeps) -> dict:
    errors = state["validation"].errors
    trimmed = trim_to_word_limits(state["output"], errors)
    if trimmed is not None:
        return {"output": trimmed, "attempts": state["attempts"] + 1}
    retrieval = state["retrieval"]
    output = deps.model.generate_structured(
        system_instruction=REPAIR_SYSTEM_INSTRUCTION,
        user_input=build_repair_payload(
            output=state["output"],
            errors=errors,
            constraints=state["template"].constraints,
            image_slots=state["template"].image_slots,
            allowed_source_ids=sorted(retrieval.allowed_ids),
        ),
        response_schema=retrieval.response_schema,
    )
    return {
        "output": _stamp(output, state["template"], state["material"]),
        "attempts": state["attempts"] + 1,
    }


def route_after_validate(state: GenerationState, deps: GenerationDeps) -> str:
    if state["validation"].is_valid:
        return "done"
    if state["attempts"] >= deps.max_repair_attempts:
        return "done"
    return "repair"


def build_generation_graph(deps: GenerationDeps):
    # Lazy on purpose: web pods import this module (via service.py) but must
    # not pay the langgraph import at startup; only the worker builds the graph.
    from langgraph.graph import END
    from langgraph.graph import START
    from langgraph.graph import StateGraph

    builder = StateGraph(GenerationState)
    builder.add_node("retrieve", partial(retrieve, deps=deps))
    builder.add_node("generate", partial(generate, deps=deps))
    builder.add_node("validate", partial(validate, deps=deps))
    builder.add_node("repair", partial(repair, deps=deps))
    builder.add_edge(START, "retrieve")
    builder.add_edge("retrieve", "generate")
    builder.add_edge("generate", "validate")
    builder.add_conditional_edges(
        "validate",
        partial(route_after_validate, deps=deps),
        {"repair": "repair", "done": END},
    )
    builder.add_edge("repair", "validate")
    return builder.compile()
