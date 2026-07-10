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


def test_job_mode_creates_k8s_job(settings):
    settings.MATERIAL_GENERATOR_JOB = "collateral-ai-backend-matgen"
    material = MarketingMaterialFactory()
    with mock.patch(
        "collateral_ai.materials.worker_trigger.create_worker_job",
        return_value="matgen-abc",
    ) as create_worker_job:
        result = trigger_generation(material)
    create_worker_job.assert_called_once_with(
        name_prefix="collateral-ai-backend-matgen",
        args=["manage.py", "generate_material", "--material-id", str(material.pk)],
        backoff_limit=0,
        active_deadline_seconds=600,
        cpu="1",
        memory="1Gi",
    )
    assert result == "matgen-abc"
