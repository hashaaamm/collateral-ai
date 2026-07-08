"""PDF extraction: text + images (PyMuPDF), tables (pdfplumber)."""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ExtractedTextBlock:
    page_number: int
    text: str


@dataclass
class ExtractedTable:
    page_number: int
    markdown: str


@dataclass
class ExtractedImage:
    page_number: int
    storage_path: str
    caption: str


@dataclass
class ExtractionResult:
    page_count: int
    text_blocks: list[ExtractedTextBlock]
    tables: list[ExtractedTable]
    images: list[ExtractedImage]


class PdfExtractionService:
    def __init__(self, storage) -> None:
        self.storage = storage

    def extract(self, pdf_bytes: bytes, document) -> ExtractionResult:
        return ExtractionResult(
            page_count=self._page_count(pdf_bytes),
            text_blocks=self._text_blocks(pdf_bytes),
            tables=self._tables(pdf_bytes),
            images=self._images(pdf_bytes, document),
        )

    def _page_count(self, pdf_bytes: bytes) -> int:
        import fitz

        with fitz.open(stream=pdf_bytes, filetype="pdf") as pdf:
            return pdf.page_count

    def _text_blocks(self, pdf_bytes: bytes) -> list[ExtractedTextBlock]:
        import fitz

        blocks: list[ExtractedTextBlock] = []
        with fitz.open(stream=pdf_bytes, filetype="pdf") as pdf:
            for i, page in enumerate(pdf, start=1):
                text = page.get_text("text").strip()
                if text:
                    blocks.append(ExtractedTextBlock(page_number=i, text=text))
        return blocks

    def _tables(self, pdf_bytes: bytes) -> list[ExtractedTable]:
        import pdfplumber

        tables: list[ExtractedTable] = []
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for i, page in enumerate(pdf.pages, start=1):
                for t_index, table in enumerate(page.extract_tables() or [], start=1):
                    md = self._table_to_markdown(table)
                    if md.strip():
                        tables.append(
                            ExtractedTable(
                                page_number=i,
                                markdown=f"Table {t_index} on page {i}\n\n{md}",
                            ),
                        )
        return tables

    def _table_to_markdown(self, table: list[list[Any]]) -> str:
        rows = [
            [("" if c is None else str(c).replace("\n", " ").strip()) for c in row]
            for row in table
            if row
        ]
        if not rows:
            return ""
        cols = max(len(r) for r in rows)
        rows = [r + [""] * (cols - len(r)) for r in rows]
        lines = [
            "| " + " | ".join(rows[0]) + " |",
            "| " + " | ".join(["---"] * cols) + " |",
        ]
        lines += ["| " + " | ".join(r) + " |" for r in rows[1:]]
        return "\n".join(lines)

    def _images(self, pdf_bytes: bytes, document) -> list[ExtractedImage]:
        import fitz

        images: list[ExtractedImage] = []
        with fitz.open(stream=pdf_bytes, filetype="pdf") as pdf:
            for page_index, page in enumerate(pdf, start=1):
                for img_index, info in enumerate(page.get_images(full=True), start=1):
                    xref = info[0]
                    try:
                        extracted = pdf.extract_image(xref)
                    except Exception:
                        logger.exception(
                            "image extract failed xref=%s doc=%s",
                            xref,
                            document.id,
                        )
                        continue
                    data = extracted.get("image")
                    ext = extracted.get("ext", "png")
                    if not data:
                        continue
                    path = (
                        f"media/companies/{document.company_id}/documents/{document.id}"
                        f"/images/page_{page_index}_image_{img_index}.{ext}"
                    )
                    self.storage.upload(path, data, self._content_type(ext))
                    images.append(
                        ExtractedImage(
                            page_number=page_index,
                            storage_path=path,
                            caption=(
                                f"Image from page {page_index} of {document.file_name}."
                            ),
                        ),
                    )
        return images

    def _content_type(self, ext: str) -> str:
        e = ext.lower().strip(".")
        return {"jpg": "image/jpeg", "jpeg": "image/jpeg"}.get(e, f"image/{e}")
