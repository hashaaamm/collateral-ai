from __future__ import annotations

from collateral_ai.documents.models import DocumentChunk
from collateral_ai.materials.generation.expansion import TABLE_PREFIX
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
