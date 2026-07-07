from __future__ import annotations

import pytest

from collateral_ai.documents.models import Document
from collateral_ai.documents.statuses import DocumentStatus
from collateral_ai.documents.tests.factories import DocumentFactory

pytestmark = pytest.mark.django_db


def test_str_includes_file_name():
    doc = DocumentFactory(file_name="report.pdf")
    assert "report.pdf" in str(doc)


def test_defaults_status_pending_and_zero_counts():
    doc = DocumentFactory()
    assert doc.status == DocumentStatus.PENDING
    assert doc.chunks_count == 0
    assert doc.tables_count == 0
    assert doc.images_count == 0
    assert doc.page_count is None
    assert doc.error_message == ""


def test_ordering_is_newest_first():
    first = DocumentFactory()
    second = DocumentFactory()
    assert list(Document.objects.all()) == [second, first]


def test_company_related_name_documents():
    doc = DocumentFactory()
    assert list(doc.company.documents.all()) == [doc]
