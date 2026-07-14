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
    assert APIClient().get("/api/companies/").status_code == HTTPStatus.UNAUTHORIZED


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
    with (
        mock.patch(
            "collateral_ai.companies.api.serializers.gcs.is_configured",
            return_value=True,
        ),
        mock.patch(
            "collateral_ai.companies.api.serializers.gcs.signed_get_url",
            return_value="https://signed-get",
        ),
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
    with (
        mock.patch(
            "collateral_ai.companies.api.views.gcs.is_configured",
            return_value=True,
        ),
        mock.patch(
            "collateral_ai.companies.api.views.gcs.build_logo_object_path",
            return_value="media/companies/logos/x/a.png",
        ),
        mock.patch(
            "collateral_ai.companies.api.views.gcs.signed_upload_url",
            return_value="https://signed-put",
        ),
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


def test_search_filters_by_name(auth_client):
    CompanyFactory(name="Acme AI")
    CompanyFactory(name="Globex")
    resp = auth_client.get("/api/companies/?search=acm")
    assert resp.status_code == HTTPStatus.OK
    names = [c["name"] for c in resp.json()]
    assert names == ["Acme AI"]


def test_search_empty_returns_all(auth_client):
    CompanyFactory(name="Acme AI")
    CompanyFactory(name="Globex")
    resp = auth_client.get("/api/companies/")
    assert len(resp.json()) == 2


def test_search_no_match_returns_empty(auth_client):
    CompanyFactory(name="Acme AI")
    resp = auth_client.get("/api/companies/?search=zzz")
    assert resp.json() == []


def test_patch_updates_name(auth_client):
    company = CompanyFactory(name="Old")
    resp = auth_client.patch(
        f"/api/companies/{company.pk}/",
        {"name": "New"},
        format="json",
    )
    assert resp.status_code == HTTPStatus.OK
    company.refresh_from_db()
    assert company.name == "New"


def test_patch_without_logo_keeps_existing(auth_client):
    company = CompanyFactory(name="Keep", logo="media/companies/logos/x/a.png")
    auth_client.patch(f"/api/companies/{company.pk}/", {"name": "Keep2"}, format="json")
    company.refresh_from_db()
    assert company.logo == "media/companies/logos/x/a.png"


def test_delete_removes_company_and_cleans_logo(auth_client):
    company = CompanyFactory(logo="media/companies/logos/x/a.png")
    with (
        mock.patch(
            "collateral_ai.companies.api.views.gcs.is_configured",
            return_value=True,
        ),
        mock.patch(
            "collateral_ai.companies.api.views.gcs.delete_object",
        ) as delete_object,
    ):
        resp = auth_client.delete(f"/api/companies/{company.pk}/")
    assert resp.status_code == HTTPStatus.NO_CONTENT
    assert not Company.objects.filter(pk=company.pk).exists()
    delete_object.assert_called_once_with("media/companies/logos/x/a.png")


def test_delete_without_logo_skips_cleanup(auth_client):
    company = CompanyFactory(logo="")
    with mock.patch(
        "collateral_ai.companies.api.views.gcs.delete_object",
    ) as delete_object:
        resp = auth_client.delete(f"/api/companies/{company.pk}/")
    assert resp.status_code == HTTPStatus.NO_CONTENT
    assert not Company.objects.filter(pk=company.pk).exists()
    delete_object.assert_not_called()


def test_company_list_includes_last_updated(auth_client):
    CompanyFactory()
    response = auth_client.get("/api/companies/")
    assert response.status_code == HTTPStatus.OK
    row = response.json()[0]
    assert "last_updated" in row
    assert row["last_updated"] is not None


def test_patch_and_delete_require_auth():
    company = CompanyFactory()
    patch_resp = APIClient().patch(f"/api/companies/{company.pk}/", {}, format="json")
    assert patch_resp.status_code == HTTPStatus.UNAUTHORIZED
    delete_resp = APIClient().delete(f"/api/companies/{company.pk}/")
    assert delete_resp.status_code == HTTPStatus.UNAUTHORIZED
