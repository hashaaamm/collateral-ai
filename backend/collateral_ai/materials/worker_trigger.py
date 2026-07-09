"""Trigger material generation: inline command locally, Cloud Run Job in prod."""

from __future__ import annotations

from django.conf import settings
from django.core.management import call_command


def trigger_generation(material) -> str:
    """Dispatch worker 2 for `material`.

    Returns the Cloud Run operation name ('' inline).

    Unlike documents' trigger, callers must NOT suppress exceptions from this
    function — the view marks the material failed instead (spec §5.5).
    """
    job = getattr(settings, "MATERIAL_GENERATOR_JOB", "")
    if not job:
        # Local/dev/test: run the management command inline (synchronous).
        call_command("generate_material", material_id=material.pk)
        return ""

    from google.cloud import run_v2

    name = (
        f"projects/{settings.GOOGLE_CLOUD_PROJECT}"
        f"/locations/{settings.MATERIAL_GENERATOR_REGION}/jobs/{job}"
    )
    overrides = run_v2.RunJobRequest.Overrides(
        container_overrides=[
            run_v2.RunJobRequest.Overrides.ContainerOverride(
                args=[
                    "manage.py",
                    "generate_material",
                    "--material-id",
                    str(material.pk),
                ],
            ),
        ],
    )
    operation = run_v2.JobsClient().run_job(
        request=run_v2.RunJobRequest(name=name, overrides=overrides),
    )
    return getattr(getattr(operation, "operation", None), "name", "") or ""
