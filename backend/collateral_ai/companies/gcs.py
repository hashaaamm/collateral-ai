"""GCS V4 signed URLs for company logos.

Dual signing so the SAME code path runs in prod and local:
- Cloud Run (prod): google.auth.default() yields compute credentials (no private key);
  sign via the IAM SignBlob API (requires roles/iam.serviceAccountTokenCreator on the
  runtime SA itself) by passing service_account_email + access_token.
- Local (GCS emulator): GOOGLE_APPLICATION_CREDENTIALS points at a throwaway
  service-account key, so google.auth.default() returns service_account.Credentials that
  sign directly with the key. The emulator ignores the signature.

The signed-URL host is settings.GCS_SIGNED_URL_ENDPOINT (passed as api_access_endpoint):
unset in prod (defaults to real GCS), set to the browser-reachable emulator host locally.
When GS_BUCKET_NAME is unset (CI/unit tests), the module is "not configured" and callers
degrade gracefully.
"""
from __future__ import annotations

import datetime
import re
import uuid
from pathlib import PurePosixPath

import google.auth
from django.conf import settings
from google.auth.transport import requests as ga_requests
from google.cloud import storage
from google.oauth2 import service_account

LOGO_PREFIX = "media/companies/logos"
UPLOAD_EXPIRY = datetime.timedelta(minutes=15)
GET_EXPIRY = datetime.timedelta(hours=1)

_SANITIZE_RE = re.compile(r"[^a-z0-9._-]+")


def is_configured() -> bool:
    return bool(getattr(settings, "GS_BUCKET_NAME", ""))


def build_logo_object_path(filename: str) -> str:
    path = PurePosixPath(filename)
    stem = path.stem.lower()
    suffix = path.suffix.lower()
    stem = _SANITIZE_RE.sub("_", stem).strip("_") or "logo"
    name = stem + suffix
    return f"{LOGO_PREFIX}/{uuid.uuid4().hex}/{name}"


def _signing_credentials():
    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    return credentials


def _bucket():
    return storage.Client().bucket(settings.GS_BUCKET_NAME)


def _signed_url(object_path, *, method, expiration, content_type=None):
    creds = _signing_credentials()
    blob = _bucket().blob(object_path)
    kwargs = {"version": "v4", "expiration": expiration, "method": method}
    if content_type:
        kwargs["content_type"] = content_type
    endpoint = getattr(settings, "GCS_SIGNED_URL_ENDPOINT", "")
    if endpoint:
        kwargs["api_access_endpoint"] = endpoint
    if isinstance(creds, service_account.Credentials):
        # Local (emulator): sign directly with the throwaway service-account key.
        return blob.generate_signed_url(credentials=creds, **kwargs)
    # Cloud Run: keyless signing via the IAM SignBlob API.
    creds.refresh(ga_requests.Request())
    return blob.generate_signed_url(
        service_account_email=creds.service_account_email,
        access_token=creds.token,
        **kwargs,
    )


def signed_upload_url(object_path: str, content_type: str) -> str:
    return _signed_url(
        object_path, method="PUT", expiration=UPLOAD_EXPIRY, content_type=content_type,
    )


def signed_get_url(object_path: str) -> str:
    return _signed_url(object_path, method="GET", expiration=GET_EXPIRY)


def delete_object(object_path: str) -> None:
    """Best-effort delete of a stored object; never raises."""
    try:
        _bucket().blob(object_path).delete()
    except Exception:  # noqa: BLE001 - deletion is best-effort
        pass
