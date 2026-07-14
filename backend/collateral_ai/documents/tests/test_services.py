from unittest import mock

import pytest

from collateral_ai.companies.tests.factories import CompanyFactory
from collateral_ai.core.exceptions import NoStoredFileError
from collateral_ai.core.exceptions import StorageNotConfiguredError
from collateral_ai.documents import services
from collateral_ai.documents.models import Document
from collateral_ai.documents.statuses import DocumentStatus
from collateral_ai.documents.tests.factories import DocumentFactory

pytestmark = pytest.mark.django_db


def test_create_document_raises_when_unconfigured():
    company = CompanyFactory()
    with (
        mock.patch(
            "collateral_ai.documents.services.gcs.is_configured",
            return_value=False,
        ),
        pytest.raises(StorageNotConfiguredError) as excinfo,
    ):
        services.create_document_with_upload_url(
            company_id=company.pk,
            file_name="a.pdf",
            content_type="application/pdf",
        )
    assert str(excinfo.value) == (
        "Document upload is not configured in this environment."
    )


def test_create_document_reserves_row_and_signs_url():
    company = CompanyFactory()
    with (
        mock.patch(
            "collateral_ai.documents.services.gcs.is_configured",
            return_value=True,
        ),
        mock.patch(
            "collateral_ai.documents.services.gcs.signed_upload_url",
            return_value="https://signed-put",
        ),
    ):
        doc, upload_url = services.create_document_with_upload_url(
            company_id=company.pk,
            file_name="a.pdf",
            content_type="application/pdf",
        )
    assert upload_url == "https://signed-put"
    assert doc.status == DocumentStatus.PENDING
    assert doc.company_id == company.pk
    assert doc.storage_path.startswith(f"media/companies/{company.pk}/documents/")


def test_start_processing_marks_failed_on_dispatch_error():
    doc = DocumentFactory(status=DocumentStatus.PENDING)
    with mock.patch(
        "collateral_ai.documents.services.trigger_processing",
        side_effect=RuntimeError("job boom"),
    ):
        doc = services.start_processing(doc)
    assert doc.status == DocumentStatus.FAILED
    assert doc.error_message == "Processing could not be started. Please try again."


def test_start_processing_flips_status_and_triggers():
    doc = DocumentFactory(status=DocumentStatus.PENDING, error_message="old")
    with mock.patch(
        "collateral_ai.documents.services.trigger_processing",
    ) as trigger:
        doc = services.start_processing(doc)
    trigger.assert_called_once()
    assert doc.status == DocumentStatus.PROCESSING
    assert doc.error_message == ""


def test_get_view_url_raises_without_stored_file():
    doc = DocumentFactory(storage_path="")
    with (
        mock.patch(
            "collateral_ai.documents.services.gcs.is_configured",
            return_value=True,
        ),
        pytest.raises(NoStoredFileError),
    ):
        services.get_view_url(doc)


def test_delete_document_cleans_gcs_then_deletes_row():
    doc = DocumentFactory(storage_path="media/companies/1/documents/1/doc.pdf")
    with (
        mock.patch(
            "collateral_ai.documents.services.gcs.is_configured",
            return_value=True,
        ),
        mock.patch(
            "collateral_ai.documents.services.gcs.delete_object",
        ) as delete_object,
    ):
        services.delete_document(doc)
    delete_object.assert_called_once_with("media/companies/1/documents/1/doc.pdf")
    assert not Document.objects.filter(pk=doc.pk).exists()
