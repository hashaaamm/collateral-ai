"""LangGraph pipeline for material generation: retrieve → generate → validate ⇄ repair.

Nodes wrap the existing domain services (retrieval, validation, prompts). The
validate → repair → validate cycle replaces the imperative while-loop; the
conditional edge routes on is_valid and attempts.
"""

from __future__ import annotations

from typing import Any
from typing import TypedDict

from django.conf import settings

from collateral_ai.materials.generation.prompts import REPAIR_SYSTEM_INSTRUCTION
from collateral_ai.materials.generation.prompts import SYSTEM_INSTRUCTION
from collateral_ai.materials.generation.prompts import build_generation_payload
from collateral_ai.materials.generation.prompts import build_repair_payload
from collateral_ai.materials.generation.retrieval import fetch_document_summaries
from collateral_ai.materials.generation.schema import build_response_schema
from collateral_ai.materials.statuses import SourceRole


class GenerationState(TypedDict, total=False):
    material_id: int
    material: Any
    template: Any
    top_k: int
    query_embedding: list[float]
    sender_chunks: list[Any]
    receiver_chunks: list[Any]
    sender_document_summaries: list[dict]
    receiver_document_summaries: list[dict]
    source_map: dict[str, Any]
    allowed_ids: set[str]
    response_schema: dict
    output: dict
    validation_errors: list[dict]
    is_valid: bool
    attempts: int
    context_snapshot: dict


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


def build_generation_graph(
    *,
    embedder,
    retriever,
    model,
    validator,
    max_repair_attempts: int,
):
    from langgraph.graph import END
    from langgraph.graph import START
    from langgraph.graph import StateGraph

    def retrieve(state: GenerationState) -> dict:
        from collateral_ai.materials.generation.prompts import build_retrieval_query

        material = state["material"]
        top_k = state["top_k"]
        query_embedding = embedder.embed_query(build_retrieval_query(material))
        sender_chunks = retriever.retrieve(
            company_id=material.sender_company_id,
            query_embedding=query_embedding,
            source_role=SourceRole.SENDER,
            source_prefix="SENDER_SOURCE",
            top_k=top_k,
        )
        receiver_chunks = retriever.retrieve(
            company_id=material.receiver_company_id,
            query_embedding=query_embedding,
            source_role=SourceRole.RECEIVER,
            source_prefix="RECEIVER_SOURCE",
            top_k=top_k,
        )
        _require_chunks(material, sender_chunks, receiver_chunks)
        sender_summaries, receiver_summaries = _document_summaries(
            sender_chunks,
            receiver_chunks,
        )
        source_map = {c.source_id: c for c in [*sender_chunks, *receiver_chunks]}
        allowed_ids = set(source_map)
        response_schema = build_response_schema(
            constraints=state["template"].constraints,
            allowed_source_ids=sorted(allowed_ids),
        )
        context_snapshot = {
            "sender_context": [c.to_prompt_dict() for c in sender_chunks],
            "receiver_context": [c.to_prompt_dict() for c in receiver_chunks],
            "sender_document_summaries": sender_summaries,
            "receiver_document_summaries": receiver_summaries,
        }
        return {
            "query_embedding": query_embedding,
            "sender_chunks": sender_chunks,
            "receiver_chunks": receiver_chunks,
            "sender_document_summaries": sender_summaries,
            "receiver_document_summaries": receiver_summaries,
            "source_map": source_map,
            "allowed_ids": allowed_ids,
            "response_schema": response_schema,
            "context_snapshot": context_snapshot,
        }

    def generate(state: GenerationState) -> dict:
        output = model.generate_structured(
            system_instruction=SYSTEM_INSTRUCTION,
            user_input=build_generation_payload(
                material=state["material"],
                sender_chunks=state["sender_chunks"],
                receiver_chunks=state["receiver_chunks"],
                sender_document_summaries=state.get(
                    "sender_document_summaries",
                    [],
                ),
                receiver_document_summaries=state.get(
                    "receiver_document_summaries",
                    [],
                ),
            ),
            response_schema=state["response_schema"],
        )
        return {"output": _stamp(output, state["template"], state["material"])}

    def validate(state: GenerationState) -> dict:
        result = validator.validate(
            output=state["output"],
            constraints=state["template"].constraints,
            image_slots=state["template"].image_slots,
            allowed_source_ids=state["allowed_ids"],
        )
        return {"is_valid": result.is_valid, "validation_errors": result.errors}

    def repair(state: GenerationState) -> dict:
        from collateral_ai.materials.generation.validation import trim_to_word_limits

        trimmed = trim_to_word_limits(state["output"], state["validation_errors"])
        if trimmed is not None:
            return {"output": trimmed, "attempts": state["attempts"] + 1}
        output = model.generate_structured(
            system_instruction=REPAIR_SYSTEM_INSTRUCTION,
            user_input=build_repair_payload(
                output=state["output"],
                errors=state["validation_errors"],
                constraints=state["template"].constraints,
                image_slots=state["template"].image_slots,
                allowed_source_ids=sorted(state["allowed_ids"]),
            ),
            response_schema=state["response_schema"],
        )
        return {
            "output": _stamp(output, state["template"], state["material"]),
            "attempts": state["attempts"] + 1,
        }

    def route_after_validate(state: GenerationState) -> str:
        if state["is_valid"]:
            return END
        if state["attempts"] >= max_repair_attempts:
            return END
        return "repair"

    builder = StateGraph(GenerationState)
    builder.add_node("retrieve", retrieve)
    builder.add_node("generate", generate)
    builder.add_node("validate", validate)
    builder.add_node("repair", repair)
    builder.add_edge(START, "retrieve")
    builder.add_edge("retrieve", "generate")
    builder.add_edge("generate", "validate")
    builder.add_conditional_edges(
        "validate",
        route_after_validate,
        {"repair": "repair", END: END},
    )
    builder.add_edge("repair", "validate")
    return builder.compile()
