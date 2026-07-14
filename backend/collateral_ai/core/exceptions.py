"""Domain errors raised by app services.

Services never touch request/Response (AGENTS.md); they raise these instead.
config.exception_handler renders any DomainError as {"detail": ...} with the
class's status code, keeping the wire format identical to a hand-built
Response({"detail": ...}, status=...).
"""

from __future__ import annotations


class DomainError(Exception):
    status_code = 400
    default_detail = "Invalid request."

    def __init__(self, detail: str | None = None) -> None:
        self.detail = detail or self.default_detail
        super().__init__(self.detail)


class StorageNotConfiguredError(DomainError):
    """GCS is not configured (no GS_BUCKET_NAME) — feature unavailable."""

    status_code = 503
    default_detail = "Storage is not configured in this environment."


class GenerationInProgressError(DomainError):
    """A fresh generation run is already active for this material."""

    status_code = 409
    default_detail = "Generation is already in progress."


class NoStoredFileError(DomainError):
    """The document row exists but no object was ever stored for it."""

    status_code = 404
    default_detail = "Document has no stored file."
