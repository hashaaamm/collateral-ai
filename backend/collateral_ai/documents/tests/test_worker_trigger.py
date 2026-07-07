from __future__ import annotations

from unittest import mock

import pytest

from collateral_ai.documents.tests.factories import DocumentFactory
from collateral_ai.documents import worker_trigger

pytestmark = pytest.mark.django_db


def test_local_runs_command_inline(settings):
    settings.DOCUMENT_PROCESSOR_JOB = ""
    doc = DocumentFactory()
    with mock.patch("collateral_ai.documents.worker_trigger.call_command") as call_command:
        worker_trigger.trigger_processing(doc)
    call_command.assert_called_once_with("process_document", document_id=doc.pk)


def test_prod_executes_cloud_run_job(settings):
    settings.DOCUMENT_PROCESSOR_JOB = "collateral-ai-backend-docproc"
    settings.DOCUMENT_PROCESSOR_REGION = "us-central1"
    settings.GOOGLE_CLOUD_PROJECT = "proj-123"
    doc = DocumentFactory()
    with mock.patch("google.cloud.run_v2.JobsClient") as JobsClient, mock.patch(
        "collateral_ai.documents.worker_trigger.call_command",
    ) as call_command:
        worker_trigger.trigger_processing(doc)
    call_command.assert_not_called()
    client = JobsClient.return_value
    assert client.run_job.call_count == 1
    request = client.run_job.call_args.kwargs.get("request") or client.run_job.call_args.args[0]
    assert request.name == (
        "projects/proj-123/locations/us-central1/jobs/collateral-ai-backend-docproc"
    )
    args = request.overrides.container_overrides[0].args
    assert args == ["manage.py", "process_document", "--document-id", str(doc.pk)]
