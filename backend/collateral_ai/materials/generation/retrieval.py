"""pgvector retrieval of company document chunks for generation grounding."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.conf import settings
from pgvector.django import CosineDistance

from collateral_ai.documents.models import DocumentChunk
from collateral_ai.materials.generation.expansion import NeighborExpander


@dataclass(frozen=True)
class RetrievedChunk:
    source_id: str
    chunk_id: int
    document_id: int
    company_id: int
    file_name: str
    page_number: int
    chunk_type: str
    content: str
    relevance_score: float
    source_role: str
    expanded_content: str = ""

    def to_prompt_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "file_name": self.file_name,
            "page_number": self.page_number,
            "chunk_type": self.chunk_type,
            "content": self.expanded_content or self.content,
        }


class RetrievalService:
    def __init__(self) -> None:
        self.neighbor_window = int(settings.MATERIAL_NEIGHBOR_WINDOW)

    def retrieve(
        self,
        *,
        company_id: int,
        query_embedding: list[float],
        source_role: str,
        source_prefix: str,
        top_k: int,
    ) -> list[RetrievedChunk]:
        # `embedding` is non-nullable — every persisted chunk has one (spec §6.3).
        chunks = list(
            DocumentChunk.objects.filter(company_id=company_id)
            .select_related("document")
            .annotate(distance=CosineDistance("embedding", query_embedding))
            .order_by("distance")[:top_k],
        )
        expanded = NeighborExpander(window=self.neighbor_window).expand(chunks)
        return [
            RetrievedChunk(
                source_id=f"{source_prefix}_{index}",
                chunk_id=chunk.pk,
                document_id=chunk.document_id,
                company_id=chunk.company_id,
                file_name=chunk.document.file_name,
                page_number=chunk.page_number,
                chunk_type=chunk.chunk_type,
                content=chunk.content,
                relevance_score=float(chunk.distance),
                source_role=source_role,
                expanded_content=expanded.get(chunk.pk, chunk.content),
            )
            for index, chunk in enumerate(chunks, start=1)
        ]
