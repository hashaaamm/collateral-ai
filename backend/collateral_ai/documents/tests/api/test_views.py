from __future__ import annotations

from http import HTTPStatus
from unittest import mock

import pytest
from rest_framework.test import APIClient

from collateral_ai.companies.tests.factories import CompanyFactory
from collateral_ai.documents.models import Document
from collateral_ai.documents.statuses import DocumentStatus
from collateral_ai.documents.tests.factories import DocumentFactory
from collateral_ai.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def auth_client() -> APIClient:
    client = APIClient()
    client.force_authenticate(user=UserFactory())
    return client


def docs_url(company_pk: int) -> str:
    return f"/api/companies/{company_pk}/documents/"


def test_list_requires_auth():
    assert APIClient().get("/api/companies/1/documents/").status_code == HTTPStatus.FORBIDDEN


def test_list_is_scoped_to_company(auth_client):
    a, b = CompanyFactory(), CompanyFactory()
    DocumentFactory(company=a, file_name="a.pdf")
    DocumentFactory(company=b, file_name="b.pdf")
    resp = auth_client.get(docs_url(a.pk))
    assert resp.status_code == HTTPStatus.OK
    names = [d["file_name"] for d in resp.json()]
    assert names == ["a.pdf"]


def test_create_reserves_pending_doc_and_returns_upload_url(auth_client):
    company = CompanyFactory()
    with mock.patch(
        "collateral_ai.documents.api.views.gcs.is_configured", return_value=True,
    ), mock.patch(
        "collateral_ai.documents.api.views.gcs.signed_upload_url",
        return_value="https://signed-put",
    ):
        resp = auth_client.post(
            docs_url(company.pk),
            {"file_name": "report.pdf", "content_type": "application/pdf"},
            format="json",
        )
    assert resp.status_code == HTTPStatus.CREATED
    body = resp.json()
    assert body["upload_url"] == "https://signed-put"
    assert body["status"] == DocumentStatus.PENDING
    assert body["company"] == company.pk
    doc = Document.objects.get(pk=body["id"])
    assert doc.company_id == company.pk
    assert doc.storage_path.startswith(f"media/companies/{company.pk}/documents/{doc.pk}/")


def test_create_rejects_non_pdf(auth_client):
    company = CompanyFactory()
    with mock.patch(
        "collateral_ai.documents.api.views.gcs.is_configured", return_value=True,
    ):
        resp = auth_client.post(
            docs_url(company.pk),
            {"file_name": "a.docx", "content_type": "application/msword"},
            format="json",
        )
    assert resp.status_code == HTTPStatus.BAD_REQUEST
    assert not Document.objects.exists()


def test_create_503_when_unconfigured(auth_client):
    company = CompanyFactory()
    with mock.patch(
        "collateral_ai.documents.api.views.gcs.is_configured", return_value=False,
    ):
        resp = auth_client.post(
            docs_url(company.pk),
            {"file_name": "a.pdf", "content_type": "application/pdf"},
            format="json",
        )
    assert resp.status_code == HTTPStatus.SERVICE_UNAVAILABLE


def test_complete_marks_processing_and_returns_202(auth_client):
    doc = DocumentFactory(status=DocumentStatus.PENDING)
    resp = auth_client.post(f"{docs_url(doc.company_id)}{doc.pk}/complete/")
    assert resp.status_code == HTTPStatus.ACCEPTED
    assert resp.json()["status"] == DocumentStatus.PROCESSING
    doc.refresh_from_db()
    assert doc.status == DocumentStatus.PROCESSING


def test_complete_retries_failed_doc(auth_client):
    doc = DocumentFactory(status=DocumentStatus.FAILED, error_message="boom")
    resp = auth_client.post(f"{docs_url(doc.company_id)}{doc.pk}/complete/")
    assert resp.status_code == HTTPStatus.ACCEPTED
    doc.refresh_from_db()
    assert doc.status == DocumentStatus.PROCESSING
    assert doc.error_message == ""


def test_retrieve_other_companys_document_404(auth_client):
    company_a, company_b = CompanyFactory(), CompanyFactory()
    doc_b = DocumentFactory(company=company_b)
    resp = auth_client.get(f"{docs_url(company_a.pk)}{doc_b.pk}/")
    assert resp.status_code == HTTPStatus.NOT_FOUND


def test_complete_other_companys_document_404(auth_client):
    company_a, company_b = CompanyFactory(), CompanyFactory()
    doc_b = DocumentFactory(company=company_b, status=DocumentStatus.PENDING)
    resp = auth_client.post(f"{docs_url(company_a.pk)}{doc_b.pk}/complete/")
    assert resp.status_code == HTTPStatus.NOT_FOUND
    doc_b.refresh_from_db()
    assert doc_b.status == DocumentStatus.PENDING
