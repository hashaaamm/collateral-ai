"""Small-to-big neighbor expansion for retrieved chunks (spec §3).

Adjacent chunks from the same chunking block are stitched exactly — the
50-word overlap appears once — using the word offsets persisted in chunk
metadata. Everything else (block/page boundaries, legacy chunks without
offsets, distinct tables) is joined with a paragraph break.
"""

from __future__ import annotations

from collateral_ai.documents.models import DocumentChunk

TABLE_PREFIX = "Extracted table\n\n"
NON_EXPANDING_CHUNK_TYPES = frozenset({"image_caption"})
_OFFSET_KEYS = ("chunk_index", "word_start", "word_end")


def _has_offsets(meta: dict) -> bool:
    return all(isinstance(meta.get(key), int) for key in _OFFSET_KEYS)


def _same_block(prev_meta: dict, meta: dict) -> bool:
    """Contiguous chunks of one chunking block: index +1, overlapping word ranges."""
    if not (_has_offsets(prev_meta) and _has_offsets(meta)):
        return False
    return (
        meta["chunk_index"] == prev_meta["chunk_index"] + 1
        and prev_meta["word_start"] <= meta["word_start"] <= prev_meta["word_end"]
    )


def stitch(pieces: list[DocumentChunk]) -> str:
    """Join id-ordered chunks of one document + chunk_type into a passage."""
    is_table = pieces[0].chunk_type == "table"
    segments: list[list[str]] = []
    current: list[str] = []
    prev_meta: dict = {}
    for piece in pieces:
        body = piece.content.removeprefix(TABLE_PREFIX) if is_table else piece.content
        words = body.split()
        meta = piece.metadata or {}
        overlap = (
            prev_meta["word_end"] - meta["word_start"]
            if current and _same_block(prev_meta, meta)
            else None
        )
        if overlap is not None and overlap <= len(words):
            current.extend(words[overlap:])
        else:
            if current:
                segments.append(current)
            current = words
        prev_meta = meta
    segments.append(current)
    prefix = TABLE_PREFIX if is_table else ""
    return "\n\n".join(prefix + " ".join(segment) for segment in segments)
