from unittest import mock

import pytest

from collateral_ai.companies import services
from collateral_ai.companies.tests.factories import CompanyFactory
from collateral_ai.core.exceptions import StorageNotConfiguredError

pytestmark = pytest.mark.django_db


def test_create_logo_upload_url_raises_when_unconfigured():
    with (
        mock.patch(
            "collateral_ai.companies.services.gcs.is_configured",
            return_value=False,
        ),
        pytest.raises(StorageNotConfiguredError) as excinfo,
    ):
        services.create_logo_upload_url(filename="a.png", content_type="image/png")
    assert str(excinfo.value) == ("Logo upload is not configured in this environment.")


def test_create_logo_upload_url_returns_url_and_path():
    with (
        mock.patch(
            "collateral_ai.companies.services.gcs.is_configured",
            return_value=True,
        ),
        mock.patch(
            "collateral_ai.companies.services.gcs.build_logo_object_path",
            return_value="media/companies/logos/x/a.png",
        ),
        mock.patch(
            "collateral_ai.companies.services.gcs.signed_upload_url",
            return_value="https://signed-put",
        ) as sign,
    ):
        url, path = services.create_logo_upload_url(
            filename="a.png",
            content_type="image/png",
        )
    assert url == "https://signed-put"
    assert path == "media/companies/logos/x/a.png"
    sign.assert_called_once_with("media/companies/logos/x/a.png", "image/png")


def test_delete_company_cleans_logo_then_deletes_row():
    company = CompanyFactory(logo="media/companies/logos/x/a.png")
    with (
        mock.patch(
            "collateral_ai.companies.services.gcs.is_configured",
            return_value=True,
        ),
        mock.patch(
            "collateral_ai.companies.services.gcs.delete_object",
        ) as delete_object,
    ):
        services.delete_company(company)
    delete_object.assert_called_once_with("media/companies/logos/x/a.png")
    assert not type(company).objects.filter(pk=company.pk).exists()


def test_delete_company_without_logo_skips_gcs():
    company = CompanyFactory(logo="")
    with mock.patch(
        "collateral_ai.companies.services.gcs.delete_object",
    ) as delete_object:
        services.delete_company(company)
    delete_object.assert_not_called()
    assert not type(company).objects.filter(pk=company.pk).exists()
