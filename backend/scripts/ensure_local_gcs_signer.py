"""Generate a throwaway service-account key for LOCAL GCS signing.

fake-gcs-server ignores the signature, so this key authorizes nothing — it only lets
google-cloud-storage compute a V4 signature offline. Regenerated on each container start;
never committed.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

DEST = Path(os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "/app/.gcs-signer.json"))


def main() -> None:
    if DEST.exists():
        return
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    ).decode()
    DEST.write_text(
        json.dumps(
            {
                "type": "service_account",
                "project_id": "local",
                "private_key_id": "local",
                "private_key": pem,
                "client_email": "fake-signer@local.iam.gserviceaccount.com",
                "client_id": "0",
                "token_uri": "https://oauth2.googleapis.com/token",
            },
            indent=2,
        ),
    )


if __name__ == "__main__":
    main()
