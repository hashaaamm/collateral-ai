"""Deterministic word-overlap chunking (no LLM)."""
from __future__ import annotations

from typing import Any

from django.conf import settings


class ChunkingService:
    def __init__(self) -> None:
        self.max_words = settings.DOCUMENT_CHUNK_MAX_WORDS
        self.overlap_words = settings.DOCUMENT_CHUNK_OVERLAP_WORDS
        self.version = settings.DOCUMENT_CHUNKING_VERSION

    def chunk_text(self, text: str, page_number: int, prefix: str = "") -> list[dict[str, Any]]:
        words = text.split()
        if not words:
            return []
        chunks: list[dict[str, Any]] = []
        start = 0
        chunk_index = 0
        num_words = len(words)
        step = max(1, self.max_words - self.overlap_words)
        while start < num_words:
            end = start + self.max_words
            # If this chunk would leave only a small (<= overlap_words) tail,
            # absorb the remainder now instead of emitting a tiny straggler chunk.
            if end >= num_words - self.overlap_words:
                end = num_words
            content = " ".join(words[start:end]).strip()
            if prefix:
                content = f"{prefix}\n\n{content}"
            chunks.append({
                "page_number": page_number,
                "chunk_index": chunk_index,
                "content": content,
                "word_start": start,
                "word_end": end,
            })
            chunk_index += 1
            if end >= num_words:
                break
            start += step
        return chunks
