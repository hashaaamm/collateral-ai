from http import HTTPStatus

from rest_framework.exceptions import NotFound

from collateral_ai.core.exceptions import DomainError
from collateral_ai.core.exceptions import GenerationInProgress
from collateral_ai.core.exceptions import NoStoredFile
from collateral_ai.core.exceptions import StorageNotConfigured
from config.exception_handler import api_exception_handler


def test_domain_error_renders_detail_and_status():
    exc = StorageNotConfigured("Logo upload is not configured in this environment.")
    resp = api_exception_handler(exc, context={})
    assert resp.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert resp.data == {
        "detail": "Logo upload is not configured in this environment.",
    }


def test_domain_error_default_details():
    assert GenerationInProgress().detail == "Generation is already in progress."
    assert NoStoredFile().detail == "Document has no stored file."
    conflict = api_exception_handler(GenerationInProgress(), context={})
    assert conflict.status_code == HTTPStatus.CONFLICT
    missing = api_exception_handler(NoStoredFile(), context={})
    assert missing.status_code == HTTPStatus.NOT_FOUND


def test_drf_exceptions_still_use_default_handler():
    resp = api_exception_handler(NotFound(), context={})
    assert resp.status_code == HTTPStatus.NOT_FOUND
    assert resp.data == {"detail": "Not found."}


def test_non_api_exceptions_return_none():
    # None means Django's normal 500 handling takes over — unchanged behavior.
    assert api_exception_handler(RuntimeError("boom"), context={}) is None


def test_str_is_the_detail():
    assert str(DomainError("nope")) == "nope"
