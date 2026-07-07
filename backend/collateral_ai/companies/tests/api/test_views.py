from __future__ import annotations

from http import HTTPStatus
from unittest import mock

import pytest
from rest_framework.test import APIClient

from collateral_ai.companies.models import Company
from collateral_ai.companies.tests.factories import CompanyFactory
from collateral_ai.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def auth_client() -> APIClient:
    client = APIClient()
    client.force_authenticate(user=UserFactory())
    return client


def test_list_requires_auth():
    assert APIClient().get("/api/companies/").status_code == HTTPStatus.FORBIDDEN


def test_list_returns_companies(auth_client):
    CompanyFactory(name="Acme AI")
    resp = auth_client.get("/api/companies/")
    assert resp.status_code == HTTPStatus.OK
    names = [c["name"] for c in resp.json()]
    assert "Acme AI" in names


def test_create_company(auth_client):
    resp = auth_client.post(
        "/api/companies/",
        {"name": "NewCo", "brand_colors": ["#5b5bd6"]},
        format="json",
    )
    assert resp.status_code == HTTPStatus.CREATED
    assert Company.objects.filter(name="NewCo").exists()
    assert resp.json()["brand_colors"] == ["#5b5bd6"]


def test_retrieve_company(auth_client):
    company = CompanyFactory(name="Acme AI")
    resp = auth_client.get(f"/api/companies/{company.pk}/")
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()["name"] == "Acme AI"


def test_logo_url_is_signed_when_configured(auth_client):
    company = CompanyFactory(logo="media/companies/logos/x/a.png")
    with mock.patch(
        "collateral_ai.companies.api.serializers.gcs.is_configured",
        return_value=True,
    ), mock.patch(
        "collateral_ai.companies.api.serializers.gcs.signed_get_url",
        return_value="https://signed-get",
    ):
        resp = auth_client.get(f"/api/companies/{company.pk}/")
    assert resp.json()["logo_url"] == "https://signed-get"


def test_logo_upload_url_503_when_unconfigured(auth_client):
    with mock.patch(
        "collateral_ai.companies.api.views.gcs.is_configured",
        return_value=False,
    ):
        resp = auth_client.post(
            "/api/companies/logo-upload-url/",
            {"filename": "a.png", "content_type": "image/png"},
            format="json",
        )
    assert resp.status_code == HTTPStatus.SERVICE_UNAVAILABLE


def test_logo_upload_url_rejects_bad_content_type(auth_client):
    with mock.patch(
        "collateral_ai.companies.api.views.gcs.is_configured",
        return_value=True,
    ):
        resp = auth_client.post(
            "/api/companies/logo-upload-url/",
            {"filename": "a.exe", "content_type": "application/x-msdownload"},
            format="json",
        )
    assert resp.status_code == HTTPStatus.BAD_REQUEST


def test_logo_upload_url_returns_signed_put(auth_client):
    with mock.patch(
        "collateral_ai.companies.api.views.gcs.is_configured",
        return_value=True,
    ), mock.patch(
        "collateral_ai.companies.api.views.gcs.build_logo_object_path",
        return_value="media/companies/logos/x/a.png",
    ), mock.patch(
        "collateral_ai.companies.api.views.gcs.signed_upload_url",
        return_value="https://signed-put",
    ):
        resp = auth_client.post(
            "/api/companies/logo-upload-url/",
            {"filename": "a.png", "content_type": "image/png"},
            format="json",
        )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == {
        "upload_url": "https://signed-put",
        "object_path": "media/companies/logos/x/a.png",
    }
