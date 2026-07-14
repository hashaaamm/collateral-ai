from __future__ import annotations

import pytest

from collateral_ai.documents.models import DocumentChunk
from collateral_ai.documents.tests.factories import DocumentChunkFactory
from collateral_ai.documents.tests.factories import DocumentFactory
from collateral_ai.materials.generation.expansion import TABLE_PREFIX
from collateral_ai.materials.generation.expansion import NeighborExpander
from collateral_ai.materials.generation.expansion import stitch


def piece(content, *, chunk_type="text", index=None, start=None, end=None):
    metadata = {}
    if index is not None:
        metadata["chunk_index"] = index
    if start is not None:
        metadata["word_start"] = start
        metadata["word_end"] = end
    return DocumentChunk(content=content, chunk_type=chunk_type, metadata=metadata)


def test_stitch_single_piece_is_identity():
    assert stitch([piece("hello world")]) == "hello world"


def test_stitch_same_block_removes_overlap_exactly():
    a = piece("w0 w1 w2 w3 w4 w5", index=0, start=0, end=6)
    b = piece("w4 w5 w6 w7 w8 w9", index=1, start=4, end=10)
    assert stitch([a, b]) == "w0 w1 w2 w3 w4 w5 w6 w7 w8 w9"


def test_stitch_three_pieces_chain():
    a = piece("w0 w1 w2 w3", index=0, start=0, end=4)
    b = piece("w2 w3 w4 w5", index=1, start=2, end=6)
    c = piece("w4 w5 w6 w7", index=2, start=4, end=8)
    assert stitch([a, b, c]) == "w0 w1 w2 w3 w4 w5 w6 w7"


def test_stitch_without_offsets_joins_with_paragraph_break():
    assert stitch([piece("one two"), piece("three four")]) == "one two\n\nthree four"


def test_stitch_across_block_boundary_joins_with_paragraph_break():
    a = piece("end of block a", index=3, start=200, end=204)
    b = piece("start of block b", index=0, start=0, end=4)
    assert stitch([a, b]) == "end of block a\n\nstart of block b"


def test_stitch_same_table_keeps_single_prefix():
    a = piece(f"{TABLE_PREFIX}r1 r2 r3 r4", chunk_type="table", index=0, start=0, end=4)
    b = piece(f"{TABLE_PREFIX}r3 r4 r5 r6", chunk_type="table", index=1, start=2, end=6)
    assert stitch([a, b]) == f"{TABLE_PREFIX}r1 r2 r3 r4 r5 r6"


def test_stitch_different_tables_keep_their_prefixes():
    a = piece(f"{TABLE_PREFIX}r1 r2", chunk_type="table", index=0, start=0, end=2)
    b = piece(f"{TABLE_PREFIX}q1 q2", chunk_type="table", index=0, start=0, end=2)
    assert stitch([a, b]) == f"{TABLE_PREFIX}r1 r2\n\n{TABLE_PREFIX}q1 q2"


def _doc_with_chunks(n):
    doc = DocumentFactory()
    return doc, [DocumentChunkFactory(document=doc, content=f"c{i}") for i in range(n)]


@pytest.mark.django_db
def test_expand_window_zero_returns_empty():
    _, chunks = _doc_with_chunks(3)
    assert NeighborExpander(window=0).expand([chunks[1]]) == {}


@pytest.mark.django_db
def test_expand_attaches_adjacent_chunks():
    _, c = _doc_with_chunks(3)
    # Factory chunks carry no word offsets -> paragraph-break joins.
    assert NeighborExpander(window=1).expand([c[1]]) == {c[1].pk: "c0\n\nc1\n\nc2"}


@pytest.mark.django_db
def test_expand_skips_neighbors_that_are_seeds():
    _, c = _doc_with_chunks(4)
    result = NeighborExpander(window=1).expand([c[1], c[2]])
    assert result == {c[1].pk: "c0\n\nc1", c[2].pk: "c2\n\nc3"}


@pytest.mark.django_db
def test_expand_shared_neighbor_goes_to_higher_ranked_seed():
    _, c = _doc_with_chunks(5)
    result = NeighborExpander(window=1).expand([c[1], c[3]])
    assert result == {c[1].pk: "c0\n\nc1\n\nc2", c[3].pk: "c3\n\nc4"}


@pytest.mark.django_db
def test_expand_never_crosses_documents_or_chunk_types():
    doc_a, a = _doc_with_chunks(1)
    DocumentChunkFactory(document=doc_a, content="tbl", chunk_type="table")
    _, b = _doc_with_chunks(1)
    assert NeighborExpander(window=2).expand([a[0], b[0]]) == {}


@pytest.mark.django_db
def test_expand_ignores_image_captions():
    doc = DocumentFactory()
    caps = [
        DocumentChunkFactory(
            document=doc,
            chunk_type="image_caption",
            content=f"cap{i}",
        )
        for i in range(3)
    ]
    assert NeighborExpander(window=1).expand([caps[1]]) == {}


@pytest.mark.django_db
def test_expand_skips_seed_deleted_between_queries():
    _, c = _doc_with_chunks(3)
    seed = c[1]
    DocumentChunk.objects.filter(pk=seed.pk).delete()
    assert NeighborExpander(window=1).expand([seed]) == {}
