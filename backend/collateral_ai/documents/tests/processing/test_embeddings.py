from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

from collateral_ai.documents.processing.embeddings import EmbeddingService


def _fake_client(vecs):
    client = mock.Mock()
    client.models.embed_content.return_value = SimpleNamespace(
        embeddings=[SimpleNamespace(values=v) for v in vecs],
    )
    return client


def test_embed_documents_normalizes_and_returns_vectors():
    raw = [[3.0] + [0.0] * 767, [0.0, 4.0] + [0.0] * 766]
    with mock.patch(
        "collateral_ai.documents.processing.embeddings.EmbeddingService._client",
        return_value=_fake_client(raw),
    ):
        out = EmbeddingService().embed_documents(["a", "b"])
    assert len(out) == 2
    assert all(len(v) == 768 for v in out)
    # L2-normalized: the single non-zero component becomes 1.0
    assert abs(out[0][0] - 1.0) < 1e-6
    assert abs(out[1][1] - 1.0) < 1e-6


def test_embed_documents_uses_retrieval_document_task_type():
    with mock.patch(
        "collateral_ai.documents.processing.embeddings.EmbeddingService._client",
        return_value=_fake_client([[1.0] + [0.0] * 767]),
    ) as client_factory:
        EmbeddingService().embed_documents(["x"])
    cfg = client_factory.return_value.models.embed_content.call_args.kwargs["config"]
    assert cfg.task_type == "RETRIEVAL_DOCUMENT"
    assert cfg.output_dimensionality == 768


def test_embed_documents_skips_blank_texts():
    with mock.patch(
        "collateral_ai.documents.processing.embeddings.EmbeddingService._client",
        return_value=_fake_client([[1.0] + [0.0] * 767]),
    ):
        out = EmbeddingService().embed_documents(["   ", "real"])
    assert len(out) == 1
