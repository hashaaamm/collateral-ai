from __future__ import annotations

from unittest import mock

from collateral_ai.documents.processing.storage import StorageService


def test_download_returns_blob_bytes():
    blob = mock.Mock()
    blob.download_as_bytes.return_value = b"pdf-bytes"
    bucket = mock.Mock()
    bucket.blob.return_value = blob
    with mock.patch(
        "collateral_ai.documents.processing.storage._bucket", return_value=bucket,
    ):
        assert StorageService().download("path/x.pdf") == b"pdf-bytes"
    bucket.blob.assert_called_once_with("path/x.pdf")


def test_upload_sends_content_and_returns_path():
    blob = mock.Mock()
    bucket = mock.Mock()
    bucket.blob.return_value = blob
    with mock.patch(
        "collateral_ai.documents.processing.storage._bucket", return_value=bucket,
    ):
        out = StorageService().upload("p/img.png", b"bytes", "image/png")
    blob.upload_from_string.assert_called_once_with(b"bytes", content_type="image/png")
    assert out == "p/img.png"
