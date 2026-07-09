from __future__ import annotations

from unittest import mock

import pytest

from collateral_ai.materials.tests.factories import MarketingMaterialFactory
from collateral_ai.materials.worker_trigger import trigger_generation

pytestmark = pytest.mark.django_db


def test_inline_mode_runs_command(settings):
    settings.MATERIAL_GENERATOR_JOB = ""
    material = MarketingMaterialFactory()
    with mock.patch(
        "collateral_ai.materials.worker_trigger.call_command",
    ) as call_command:
        result = trigger_generation(material)
    call_command.assert_called_once_with("generate_material", material_id=material.pk)
    assert result == ""


def test_job_mode_runs_cloud_run_job(settings):
    settings.MATERIAL_GENERATOR_JOB = "matgen-job"
    settings.MATERIAL_GENERATOR_REGION = "us-central1"
    settings.GOOGLE_CLOUD_PROJECT = "proj-123"
    material = MarketingMaterialFactory()
    with mock.patch("google.cloud.run_v2.JobsClient") as jobs_client:
        operation = jobs_client.return_value.run_job.return_value
        operation.operation.name = "operations/abc"
        result = trigger_generation(material)
    request = jobs_client.return_value.run_job.call_args.kwargs["request"]
    assert request.name == "projects/proj-123/locations/us-central1/jobs/matgen-job"
    args = list(request.overrides.container_overrides[0].args)
    assert args == ["manage.py", "generate_material", "--material-id", str(material.pk)]
    assert result == "operations/abc"
