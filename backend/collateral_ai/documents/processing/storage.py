"""GCS byte I/O for the document worker (ADC, via the companies bucket helper)."""

from __future__ import annotations

from collateral_ai.companies.gcs import _bucket


class StorageService:
    def download(self, object_path: str) -> bytes:
        return _bucket().blob(object_path).download_as_bytes()

    def upload(self, object_path: str, content: bytes, content_type: str) -> str:
        _bucket().blob(object_path).upload_from_string(
            content,
            content_type=content_type,
        )
        return object_path
