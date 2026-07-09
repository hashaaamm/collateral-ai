import pytest

from collateral_ai.companies.tests.factories import CompanyFactory
from collateral_ai.documents.tests.factories import DocumentFactory

pytestmark = pytest.mark.django_db


def test_adding_document_bumps_company_last_activity():
    company = CompanyFactory()
    doc = DocumentFactory(company=company)
    company.refresh_from_db()
    assert company.last_activity_at == doc.created_at


def test_bump_uses_latest_document():
    company = CompanyFactory()
    DocumentFactory(company=company)
    latest = DocumentFactory(company=company)
    company.refresh_from_db()
    assert company.last_activity_at == latest.created_at
