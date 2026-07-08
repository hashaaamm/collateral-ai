from __future__ import annotations

from collateral_ai.documents import gcs


def test_object_path_is_scoped_and_sanitized():
    path = gcs.build_document_object_path(7, 42, "Q3 Report!.PDF")
    assert path.startswith("media/companies/7/documents/42/")
    assert path.endswith(".pdf")
    # unsafe characters collapsed, lowercased
    assert " " not in path
    assert "!" not in path


def test_object_path_falls_back_when_stem_empty():
    path = gcs.build_document_object_path(1, 1, "***.pdf")
    assert path == "media/companies/1/documents/1/document.pdf"
