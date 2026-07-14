"""Business operations for companies."""

from __future__ import annotations

from typing import TYPE_CHECKING

from collateral_ai.companies import gcs
from collateral_ai.core.exceptions import StorageNotConfiguredError

if TYPE_CHECKING:
    from collateral_ai.companies.models import Company


def create_logo_upload_url(*, filename: str, content_type: str) -> tuple[str, str]:
    """Return (upload_url, object_path) for a direct browser PUT of a logo."""
    if not gcs.is_configured():
        msg = "Logo upload is not configured in this environment."
        raise StorageNotConfiguredError(msg)
    object_path = gcs.build_logo_object_path(filename)
    return gcs.signed_upload_url(object_path, content_type), object_path


def delete_company(company: Company) -> None:
    """Delete the row and best-effort clean up the stored logo."""
    if company.logo and gcs.is_configured():
        gcs.delete_object(company.logo)
    company.delete()
