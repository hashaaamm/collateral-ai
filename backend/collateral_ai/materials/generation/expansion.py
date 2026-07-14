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


class NeighborExpander:
    """Assigns each rank-ordered seed its unclaimed ±window neighbors, stitched."""

    def __init__(self, *, window: int) -> None:
        self.window = window

    def expand(self, seeds: list[DocumentChunk]) -> dict[int, str]:
        """Map seed chunk id -> expanded passage; seeds must be rank-ordered.

        Seeds with no fresh neighbors are omitted (their content stands alone).
        """
        if self.window <= 0 or not seeds:
            return {}
        ordered = self._ordered_ids(seeds)
        claimed = {seed.pk for seed in seeds}
        assignment: dict[int, list[int]] = {}
        for seed in seeds:
            key = (seed.document_id, seed.chunk_type)
            if key not in ordered:
                continue
            ids = ordered[key]
            if seed.pk not in ids:
                continue
            pos = ids.index(seed.pk)
            lo = max(0, pos - self.window)
            wanted = ids[lo:pos] + ids[pos + 1 : pos + 1 + self.window]
            fresh = [pk for pk in wanted if pk not in claimed]
            if fresh:
                claimed.update(fresh)
                assignment[seed.pk] = fresh
        if not assignment:
            return {}
        neighbor_ids = [pk for pks in assignment.values() for pk in pks]
        neighbors = DocumentChunk.objects.in_bulk(neighbor_ids)
        result: dict[int, str] = {}
        for seed in seeds:
            if seed.pk not in assignment:
                continue
            survivors = [
                chunk
                for pk in assignment[seed.pk]
                if (chunk := neighbors.get(pk)) is not None
            ]
            if not survivors:
                continue
            result[seed.pk] = stitch(
                sorted([seed, *survivors], key=lambda chunk: chunk.pk),
            )
        return result

    def _ordered_ids(
        self,
        seeds: list[DocumentChunk],
    ) -> dict[tuple[int, str], list[int]]:
        keys = {
            (seed.document_id, seed.chunk_type)
            for seed in seeds
            if seed.chunk_type not in NON_EXPANDING_CHUNK_TYPES
        }
        if not keys:
            return {}
        rows = (
            DocumentChunk.objects.filter(
                document_id__in={doc_id for doc_id, _ in keys},
            )
            .order_by("pk")
            .values_list("document_id", "chunk_type", "pk")
        )
        ordered: dict[tuple[int, str], list[int]] = {}
        for doc_id, chunk_type, pk in rows:
            if (doc_id, chunk_type) in keys:
                ordered.setdefault((doc_id, chunk_type), []).append(pk)
        return ordered
