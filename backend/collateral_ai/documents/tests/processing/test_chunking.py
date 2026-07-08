from __future__ import annotations

from collateral_ai.documents.processing.chunking import ChunkingService


def test_short_text_single_chunk():
    chunks = ChunkingService().chunk_text("one two three", page_number=2)
    assert len(chunks) == 1
    assert chunks[0]["content"] == "one two three"
    assert chunks[0]["page_number"] == 2
    assert chunks[0]["chunk_index"] == 0


def test_long_text_splits_with_overlap(settings):
    settings.DOCUMENT_CHUNK_MAX_WORDS = 10
    settings.DOCUMENT_CHUNK_OVERLAP_WORDS = 3
    words = " ".join(str(i) for i in range(25))
    chunks = ChunkingService().chunk_text(words, page_number=1)
    assert len(chunks) == 3
    # overlap: second chunk starts 3 words before the first chunk's end (index 7)
    assert chunks[0]["word_end"] == 10
    assert chunks[1]["word_start"] == 7


def test_prefix_is_prepended():
    chunks = ChunkingService().chunk_text("a b", page_number=1, prefix="TABLE")
    assert chunks[0]["content"].startswith("TABLE\n\n")


def test_empty_text_no_chunks():
    assert ChunkingService().chunk_text("   ", page_number=1) == []
