"""GCS object paths for company documents.

Reuses the companies signed-URL machinery (dual prod/emulator signing) so there
is one signing code path in the project. Only the object-path convention is
document-specific.
"""

from __future__ import annotations

from pathlib import PurePosixPath

from collateral_ai.companies.gcs import _SANITIZE_RE
from collateral_ai.companies.gcs import delete_object  # noqa: F401  (re-exported)
from collateral_ai.companies.gcs import is_configured  # noqa: F401  (re-exported)
from collateral_ai.companies.gcs import signed_upload_url  # noqa: F401  (re-exported)

DOCUMENT_PREFIX = "media/companies"


def build_document_object_path(company_id: int, document_id: int, filename: str) -> str:
    path = PurePosixPath(filename)
    stem = _SANITIZE_RE.sub("_", path.stem.lower()).strip("_") or "document"
    suffix = path.suffix.lower() or ".pdf"
    name = stem + suffix
    return f"{DOCUMENT_PREFIX}/{company_id}/documents/{document_id}/{name}"
