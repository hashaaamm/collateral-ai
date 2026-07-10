from __future__ import annotations

from unittest import mock

import pytest

from collateral_ai.documents import worker_trigger
from collateral_ai.documents.tests.factories import DocumentFactory

pytestmark = pytest.mark.django_db


def test_local_runs_command_inline(settings):
    settings.DOCUMENT_PROCESSOR_JOB = ""
    doc = DocumentFactory()
    with mock.patch(
        "collateral_ai.documents.worker_trigger.call_command",
    ) as call_command:
        worker_trigger.trigger_processing(doc)
    call_command.assert_called_once_with("process_document", document_id=doc.pk)


def test_prod_creates_k8s_job(settings):
    settings.DOCUMENT_PROCESSOR_JOB = "collateral-ai-backend-docproc"
    doc = DocumentFactory()
    with (
        mock.patch(
            "collateral_ai.documents.worker_trigger.create_worker_job",
        ) as create_worker_job,
        mock.patch(
            "collateral_ai.documents.worker_trigger.call_command",
        ) as call_command,
    ):
        worker_trigger.trigger_processing(doc)
    call_command.assert_not_called()
    create_worker_job.assert_called_once_with(
        name_prefix="collateral-ai-backend-docproc",
        args=["manage.py", "process_document", "--document-id", str(doc.pk)],
        backoff_limit=1,
        active_deadline_seconds=900,
        cpu="2",
        memory="2Gi",
    )
