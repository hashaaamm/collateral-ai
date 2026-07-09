from __future__ import annotations

from http import HTTPStatus

import pytest
from rest_framework.test import APIClient

from collateral_ai.companies.tests.factories import CompanyFactory
from collateral_ai.documents.statuses import DocumentStatus
from collateral_ai.documents.tests.factories import DocumentFactory
from collateral_ai.materials.statuses import GenerationStatus
from collateral_ai.materials.statuses import ReviewStatus
from collateral_ai.materials.tests.factories import MarketingMaterialFactory
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

    # Pin sender/receiver to the existing company so MarketingMaterialFactory's
    # SubFactory(CompanyFactory) defaults don't create new companies and inflate
    # companies_count.
    material = {"sender_company": company, "receiver_company": company}
    # generation_status=completed → counts toward materials_generated (3).
    MarketingMaterialFactory(
        **material,
        generation_status=GenerationStatus.COMPLETED,
        review_status=ReviewStatus.APPROVED,
    )
    MarketingMaterialFactory(
        **material,
        generation_status=GenerationStatus.COMPLETED,
        review_status=ReviewStatus.PENDING,
    )
    MarketingMaterialFactory(
        **material,
        generation_status=GenerationStatus.COMPLETED,
        review_status=ReviewStatus.PENDING,
    )
    # Still generating, review pending → counts toward materials_needs_review only.
    MarketingMaterialFactory(
        **material,
        generation_status=GenerationStatus.QUEUED,
        review_status=ReviewStatus.PENDING,
    )

    resp = auth_client.get("/api/dashboard/stats/")

    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == {
        "companies_count": 2,
        "documents_processed": 2,
        "documents_processing": 1,
        "materials_generated": 3,
        "materials_needs_review": 3,
    }


def test_stats_zero_state(auth_client):
    resp = auth_client.get("/api/dashboard/stats/")
    assert resp.json() == {
        "companies_count": 0,
        "documents_processed": 0,
        "documents_processing": 0,
        "materials_generated": 0,
        "materials_needs_review": 0,
    }
