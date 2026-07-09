from __future__ import annotations

from http import HTTPStatus

import pytest
from rest_framework.test import APIClient

from collateral_ai.companies.tests.factories import CompanyFactory
from collateral_ai.documents.statuses import DocumentStatus
from collateral_ai.documents.tests.factories import DocumentFactory
from collateral_ai.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def auth_client() -> APIClient:
    client = APIClient()
    client.force_authenticate(user=UserFactory())
    return client


def test_stats_requires_auth():
    resp = APIClient().get("/api/dashboard/stats/")
    assert resp.status_code == HTTPStatus.FORBIDDEN


def test_stats_counts_companies_and_documents_by_status(auth_client):
    company = CompanyFactory()
    CompanyFactory()
    # Pin documents to a single existing company: DocumentFactory.company is a
    # SubFactory(CompanyFactory), so leaving it unset would create a new
    # Company per document and inflate companies_count.
    DocumentFactory(company=company, status=DocumentStatus.PROCESSED)
    DocumentFactory(company=company, status=DocumentStatus.PROCESSED)
    DocumentFactory(company=company, status=DocumentStatus.PROCESSING)
    DocumentFactory(company=company, status=DocumentStatus.PENDING)
    DocumentFactory(company=company, status=DocumentStatus.FAILED)

    resp = auth_client.get("/api/dashboard/stats/")

    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == {
        "companies_count": 2,
        "documents_processed": 2,
        "documents_processing": 1,
    }


def test_stats_zero_state(auth_client):
    resp = auth_client.get("/api/dashboard/stats/")
    assert resp.json() == {
        "companies_count": 0,
        "documents_processed": 0,
        "documents_processing": 0,
    }
