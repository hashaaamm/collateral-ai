from __future__ import annotations

from unittest import mock

from collateral_ai.documents.processing.extraction import PdfExtractionService
from collateral_ai.documents.tests.fixtures import make_pdf


class _Doc:
    id = 1
    company_id = 1
    file_name = "test.pdf"


def test_extract_text_and_page_count():
    storage = mock.Mock()
    result = PdfExtractionService(storage=storage).extract(make_pdf("Alpha Beta Gamma"), _Doc())
    assert result.page_count == 1
    joined = " ".join(b.text for b in result.text_blocks)
    assert "Alpha Beta Gamma" in joined
    # our minimal fixture has no embedded images/tables
    assert result.images == []


def test_extract_handles_empty_pdf():
    storage = mock.Mock()
    result = PdfExtractionService(storage=storage).extract(make_pdf(" "), _Doc())
    assert result.page_count == 1
    assert isinstance(result.tables, list)
