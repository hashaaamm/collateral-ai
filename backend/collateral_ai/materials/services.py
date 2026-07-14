"""Business operations for marketing materials: create, dispatch, regenerate."""

from __future__ import annotations

import datetime
import logging

from django.db import transaction
from django.utils import timezone

from collateral_ai.core.exceptions import GenerationInProgressError
from collateral_ai.materials.models import MarketingMaterial
from collateral_ai.materials.statuses import GenerationStatus
from collateral_ai.materials.statuses import ReviewStatus
from collateral_ai.materials.worker_trigger import trigger_generation

logger = logging.getLogger(__name__)

# User-facing failure text. The real exception (which may leak infra details
# like internal hostnames) is logged server-side, never surfaced to the client.
_GENERIC_DISPATCH_ERROR = "Generation could not be started. Please try again."

# A queued/processing row older than this is considered stranded (crashed job)
# and may be regenerated (spec §5.2). Comfortably above the 600s job timeout.
STALE_AFTER = datetime.timedelta(minutes=15)


def create_material(**validated_data) -> MarketingMaterial:
    """Create the row, dispatch generation, return the refreshed row."""
    material = MarketingMaterial.objects.create(**validated_data)
    dispatch_generation(material)
    material.refresh_from_db()
    return material


def dispatch_generation(material: MarketingMaterial) -> None:
    """Trigger the worker inside its own savepoint (spec §5.5).

    The request runs under ATOMIC_REQUESTS; the inner atomic() means a
    failing trigger (or a poisoned inline run) can't take the created row
    down with it — we mark the material failed and the caller still returns
    success.
    """
    try:
        with transaction.atomic():
            operation_name = trigger_generation(material)
    except Exception:  # any trigger failure → failed row, generic client message
        logger.exception("Material %s generation dispatch failed", material.pk)
        MarketingMaterial.objects.filter(pk=material.pk).update(
            generation_status=GenerationStatus.FAILED,
            error_message=_GENERIC_DISPATCH_ERROR,
            updated_at=timezone.now(),
        )
    else:
        if operation_name:
            MarketingMaterial.objects.filter(pk=material.pk).update(
                job_operation_name=operation_name,
                updated_at=timezone.now(),
            )


def regenerate_material(
    material: MarketingMaterial,
    *,
    prompt: str | None = None,
) -> MarketingMaterial:
    """Reset a material and re-queue generation; returns the refreshed row.

    Raises GenerationInProgressError while a fresh (non-stale) run is active. The
    locked re-fetch guards the read-modify-write against a concurrent worker
    completion.
    """
    with transaction.atomic():
        material = MarketingMaterial.objects.select_for_update().get(
            pk=material.pk,
        )
        is_active = material.generation_status in {
            GenerationStatus.QUEUED,
            GenerationStatus.PROCESSING,
        }
        is_stale = material.updated_at < timezone.now() - STALE_AFTER
        if is_active and not is_stale:
            raise GenerationInProgressError
        # Apply an edited prompt in the same locked txn so the row that gets
        # re-queued is the one the new prompt will generate from.
        if prompt is not None:
            material.prompt = prompt
        material.generation_status = GenerationStatus.QUEUED
        material.review_status = ReviewStatus.PENDING
        material.output_json = None
        material.validation_result = None
        material.retrieved_context = None
        material.error_message = ""
        material.job_operation_name = ""
        material.completed_at = None
        material.save()
        material.sources.all().delete()
    dispatch_generation(material)
    material.refresh_from_db()
    return material
