"""pgvector retrieval of company document chunks for generation grounding."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pgvector.django import CosineDistance

from collateral_ai.documents.models import DocumentChunk


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

    def to_prompt_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "file_name": self.file_name,
            "page_number": self.page_number,
            "chunk_type": self.chunk_type,
            "content": self.content,
        }


class RetrievalService:
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
        chunks = (
            DocumentChunk.objects.filter(company_id=company_id)
            .select_related("document")
            .annotate(distance=CosineDistance("embedding", query_embedding))
            .order_by("distance")[:top_k]
        )
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
            )
            for index, chunk in enumerate(chunks, start=1)
        ]
