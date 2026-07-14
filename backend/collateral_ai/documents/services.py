"""Business operations for documents: upload reservation, processing, cleanup."""

from __future__ import annotations

import logging

from django.utils import timezone

from collateral_ai.core.exceptions import NoStoredFileError
from collateral_ai.core.exceptions import StorageNotConfiguredError
from collateral_ai.documents import gcs
from collateral_ai.documents.models import Document
from collateral_ai.documents.statuses import DocumentStatus
from collateral_ai.documents.worker_trigger import trigger_processing

logger = logging.getLogger(__name__)

# User-facing failure text; the real exception is logged server-side, never
# sent to clients.
_GENERIC_DISPATCH_ERROR = "Processing could not be started. Please try again."


def create_document_with_upload_url(
    *,
    company_id: int,
    file_name: str,
    content_type: str,
) -> tuple[Document, str]:
    """Reserve a PENDING row and return (document, signed PUT url).

    ATOMIC_REQUESTS wraps the calling request in a transaction, so if signing
    raises the row is rolled back — no orphan PENDING row is left behind.
    """
    if not gcs.is_configured():
        msg = "Document upload is not configured in this environment."
        raise StorageNotConfiguredError(msg)
    doc = Document.objects.create(
        company_id=company_id,
        file_name=file_name,
        content_type=content_type,
        status=DocumentStatus.PENDING,
    )
    object_path = gcs.build_document_object_path(company_id, doc.pk, file_name)
    doc.storage_path = object_path
    doc.save(update_fields=["storage_path", "updated_at"])
    return doc, gcs.signed_upload_url(object_path, content_type)


def start_processing(document: Document) -> Document:
    """Flip to PROCESSING, dispatch the worker, return the refreshed row.

    trigger_processing runs the pipeline INLINE (synchronous, in this thread)
    when DOCUMENT_PROCESSOR_JOB is unset — dev/local convenience. In prod it
    fires a Kubernetes Job and returns immediately. If dispatch itself fails
    (e.g. the control plane is unreachable), mark the row failed with a generic
    message — never leak the raw exception — so the client stops polling a doc
    that will never progress.
    """
    document.status = DocumentStatus.PROCESSING
    document.error_message = ""
    document.save(update_fields=["status", "error_message", "updated_at"])
    try:
        trigger_processing(document)
    except Exception:
        logger.exception("Document %s processing dispatch failed", document.pk)
        Document.objects.filter(pk=document.pk).update(
            status=DocumentStatus.FAILED,
            error_message=_GENERIC_DISPATCH_ERROR,
            updated_at=timezone.now(),
        )
    document.refresh_from_db()
    return document


def get_view_url(document: Document) -> str:
    """Signed GET URL so the browser can open the stored PDF (spec §5.3)."""
    if not gcs.is_configured():
        msg = "Document viewing is not configured in this environment."
        raise StorageNotConfiguredError(msg)
    if not document.storage_path:
        raise NoStoredFileError
    return gcs.signed_get_url(document.storage_path)


def delete_document(document: Document) -> None:
    """Delete the row and best-effort clean up the stored object."""
    if document.storage_path and gcs.is_configured():
        gcs.delete_object(document.storage_path)
    document.delete()
