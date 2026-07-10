"""Trigger material generation: inline command locally, K8s Job in prod."""

from __future__ import annotations

from django.conf import settings
from django.core.management import call_command

from collateral_ai.worker_jobs import create_worker_job


def trigger_generation(material) -> str:
    """Dispatch worker 2 for `material`.

    Returns the created K8s Job name ('' inline).

    Unlike documents' trigger, callers must NOT suppress exceptions from this
    function — the view marks the material failed instead (spec §5.5).
    """
    job = getattr(settings, "MATERIAL_GENERATOR_JOB", "")
    if not job:
        # Local/dev/test: run the management command inline (synchronous).
        call_command("generate_material", material_id=material.pk)
        return ""

    # backoff_limit=0 is deliberate (unlike docproc): the command exits non-zero on
    # deterministic failures like validation exhaustion, and an auto re-run would burn
    # more LLM calls and flip a row the UI already shows as failed. (spec §6.6)
    return create_worker_job(
        name_prefix=job,
        args=["manage.py", "generate_material", "--material-id", str(material.pk)],
        backoff_limit=0,
        active_deadline_seconds=600,
        cpu="1",
        memory="1Gi",
    )
