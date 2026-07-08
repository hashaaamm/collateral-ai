"""Trigger document processing: inline command locally, Cloud Run Job in prod."""

from __future__ import annotations

from django.conf import settings
from django.core.management import call_command


def trigger_processing(document) -> None:
    job = getattr(settings, "DOCUMENT_PROCESSOR_JOB", "")
    if not job:
        # Local/dev/test: run the management command inline.
        call_command("process_document", document_id=document.pk)
        return

    # Prod: execute the Cloud Run Job with a --document-id override.
    from google.cloud import run_v2

    name = (
        f"projects/{settings.GOOGLE_CLOUD_PROJECT}"
        f"/locations/{settings.DOCUMENT_PROCESSOR_REGION}/jobs/{job}"
    )
    overrides = run_v2.RunJobRequest.Overrides(
        container_overrides=[
            run_v2.RunJobRequest.Overrides.ContainerOverride(
                args=[
                    "manage.py",
                    "process_document",
                    "--document-id",
                    str(document.pk),
                ],
            ),
        ],
    )
    run_v2.JobsClient().run_job(
        request=run_v2.RunJobRequest(name=name, overrides=overrides),
    )
