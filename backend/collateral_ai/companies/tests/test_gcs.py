from __future__ import annotations

from unittest import mock

from collateral_ai.companies import gcs


def test_is_configured_false_without_bucket(settings):
    settings.GS_BUCKET_NAME = ""
    assert gcs.is_configured() is False


def test_is_configured_true_with_bucket(settings):
    settings.GS_BUCKET_NAME = "my-bucket"
    assert gcs.is_configured() is True


def test_build_logo_object_path_sanitizes_and_uuids():
    path = gcs.build_logo_object_path("My Logo (v2).PNG")
    assert path.startswith("media/companies/logos/")
    # <prefix>/<uuid>/<sanitized-filename>
    prefix, uuid_seg, filename = path.rsplit("/", 2)
    assert prefix == "media/companies/logos"
    assert len(uuid_seg) >= 32  # a uuid hex/str
    assert filename == "my_logo_v2.png"
    assert " " not in filename and "(" not in filename


def test_signed_upload_url_delegates_to_blob(settings):
    settings.GS_BUCKET_NAME = "my-bucket"
    with mock.patch.object(gcs, "_bucket") as bucket, \
         mock.patch.object(gcs, "_signing_credentials"):
        blob = bucket.return_value.blob.return_value
        blob.generate_signed_url.return_value = "https://signed-put"
        url = gcs.signed_upload_url("media/companies/logos/x/a.png", "image/png")
        assert url == "https://signed-put"
        _, kwargs = blob.generate_signed_url.call_args
        assert kwargs["method"] == "PUT"
        assert kwargs["content_type"] == "image/png"
        assert kwargs["version"] == "v4"


def test_signed_get_url_delegates_to_blob(settings):
    settings.GS_BUCKET_NAME = "my-bucket"
    with mock.patch.object(gcs, "_bucket") as bucket, \
         mock.patch.object(gcs, "_signing_credentials"):
        blob = bucket.return_value.blob.return_value
        blob.generate_signed_url.return_value = "https://signed-get"
        url = gcs.signed_get_url("media/companies/logos/x/a.png")
        assert url == "https://signed-get"
        _, kwargs = blob.generate_signed_url.call_args
        assert kwargs["method"] == "GET"
        assert kwargs["version"] == "v4"
