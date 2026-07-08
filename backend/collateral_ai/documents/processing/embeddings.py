"""Gemini embeddings via Vertex AI (keyless ADC)."""
from __future__ import annotations

from collections.abc import Iterable

from django.conf import settings


class EmbeddingService:
    def __init__(self) -> None:
        self.model = settings.EMBEDDING_MODEL
        self.dimensions = int(settings.EMBEDDING_DIMENSIONS)
        self.batch_size = int(settings.EMBEDDING_BATCH_SIZE)

    def _client(self):
        from google import genai

        return genai.Client(
            vertexai=True,
            project=settings.GOOGLE_CLOUD_PROJECT,
            location=settings.VERTEX_LOCATION,
        )

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts, task_type="RETRIEVAL_DOCUMENT")

    def embed_query(self, query: str) -> list[float]:
        out = self._embed([query], task_type="RETRIEVAL_QUERY")
        if not out:
            raise ValueError("Gemini returned no query embedding.")
        return out[0]

    def _embed(self, texts: list[str], task_type: str) -> list[list[float]]:
        clean = [t.strip() for t in texts if t and t.strip()]
        if not clean:
            return []
        from google.genai import types

        client = self._client()
        out: list[list[float]] = []
        for batch in self._batched(clean, self.batch_size):
            resp = client.models.embed_content(
                model=self.model,
                contents=batch,
                config=types.EmbedContentConfig(
                    task_type=task_type,
                    output_dimensionality=self.dimensions,
                ),
            )
            if not resp.embeddings:
                raise RuntimeError("Gemini returned no embeddings for batch.")
            for emb in resp.embeddings:
                values = list(emb.values)
                if len(values) != self.dimensions:
                    raise ValueError(
                        f"embedding dim mismatch expected={self.dimensions} actual={len(values)}",
                    )
                out.append(self._normalize(values))
        return out

    def _normalize(self, vec: list[float]) -> list[float]:
        mag = sum(v * v for v in vec) ** 0.5
        return vec if mag == 0 else [v / mag for v in vec]

    def _batched(self, values: list[str], size: int) -> Iterable[list[str]]:
        for i in range(0, len(values), size):
            yield values[i:i + size]
