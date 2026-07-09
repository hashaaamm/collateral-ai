from __future__ import annotations

import pytest

from collateral_ai.companies.models import Company
from collateral_ai.companies.tests.factories import CompanyFactory

pytestmark = pytest.mark.django_db


def test_company_str_is_name():
    company = CompanyFactory(name="Acme AI")
    assert str(company) == "Acme AI"


def test_brand_colors_defaults_to_empty_list():
    company = Company.objects.create(name="NoColors")
    assert company.brand_colors == []


def test_ordering_is_newest_first():
    first = CompanyFactory(name="First")
    second = CompanyFactory(name="Second")
    assert list(Company.objects.all()) == [second, first]


def test_logo_defaults_blank():
    company = CompanyFactory()
    assert company.logo == ""


def test_company_has_last_activity_after_create():
    company = CompanyFactory()
    assert company.last_activity_at is not None


def test_saving_company_bumps_last_activity():
    company = CompanyFactory()
    before = company.last_activity_at
    company.name = "Renamed"
    company.save()
    company.refresh_from_db()
    assert company.last_activity_at >= before
