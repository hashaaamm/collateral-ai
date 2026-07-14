"""Trigger document processing: inline command locally, K8s Job in prod."""

from __future__ import annotations

from django.conf import settings
from django.core.management import call_command

from collateral_ai.worker_jobs import create_worker_job


def trigger_processing(document) -> None:
    job = getattr(settings, "DOCUMENT_PROCESSOR_JOB", "")
    if not job:
        # Local/dev/test: run the management command inline.
        call_command("process_document", document_id=document.pk)
        return

    # Prod: submit a Kubernetes Job that runs the same command with --document-id.
    create_worker_job(
        name_prefix=job,
        args=["manage.py", "process_document", "--document-id", str(document.pk)],
        backoff_limit=1,
        active_deadline_seconds=900,
        cpu="500m",
        memory="512Mi",
    )
