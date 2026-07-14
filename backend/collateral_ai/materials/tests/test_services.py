import datetime
from unittest import mock

import pytest
from django.utils import timezone

from collateral_ai.core.exceptions import GenerationInProgressError
from collateral_ai.materials import services
from collateral_ai.materials.models import MarketingMaterial
from collateral_ai.materials.statuses import GenerationStatus
from collateral_ai.materials.statuses import ReviewStatus
from collateral_ai.materials.tests.factories import MarketingMaterialFactory

pytestmark = pytest.mark.django_db

TRIGGER = "collateral_ai.materials.services.trigger_generation"


def test_dispatch_failure_marks_failed_with_generic_message():
    material = MarketingMaterialFactory(generation_status=GenerationStatus.QUEUED)
    with mock.patch(TRIGGER, side_effect=RuntimeError("job boom")):
        services.dispatch_generation(material)
    material.refresh_from_db()
    assert material.generation_status == GenerationStatus.FAILED
    assert material.error_message == (
        "Generation could not be started. Please try again."
    )


def test_dispatch_success_stores_operation_name():
    material = MarketingMaterialFactory(generation_status=GenerationStatus.QUEUED)
    with mock.patch(TRIGGER, return_value="operations/abc"):
        services.dispatch_generation(material)
    material.refresh_from_db()
    assert material.job_operation_name == "operations/abc"
    assert material.generation_status == GenerationStatus.QUEUED


def test_regenerate_conflicts_while_fresh_run_is_active():
    material = MarketingMaterialFactory(
        generation_status=GenerationStatus.PROCESSING,
    )
    with pytest.raises(GenerationInProgressError):
        services.regenerate_material(material)


def test_regenerate_takes_over_stale_run():
    material = MarketingMaterialFactory(
        generation_status=GenerationStatus.PROCESSING,
    )
    stale = timezone.now() - services.STALE_AFTER - datetime.timedelta(minutes=1)
    MarketingMaterial.objects.filter(pk=material.pk).update(updated_at=stale)
    with mock.patch(TRIGGER, return_value="") as trigger:
        result = services.regenerate_material(material)
    trigger.assert_called_once()
    assert result.generation_status == GenerationStatus.QUEUED


def test_regenerate_resets_fields_and_applies_prompt():
    material = MarketingMaterialFactory(
        generation_status=GenerationStatus.COMPLETED,
        review_status=ReviewStatus.APPROVED,
        output_json={"headline": "old"},
        error_message="old error",
        job_operation_name="operations/old",
    )
    with mock.patch(TRIGGER, return_value=""):
        result = services.regenerate_material(material, prompt="new prompt")
    assert result.prompt == "new prompt"
    assert result.generation_status == GenerationStatus.QUEUED
    assert result.review_status == ReviewStatus.PENDING
    assert result.output_json is None
    assert result.error_message == ""
    assert result.job_operation_name == ""
    assert result.completed_at is None


def test_create_material_creates_row_and_dispatches():
    template = MarketingMaterialFactory().template
    seed = MarketingMaterialFactory()  # supplies sender/receiver companies
    with mock.patch(TRIGGER, return_value="operations/abc"):
        material = services.create_material(
            title="T",
            sender_company=seed.sender_company,
            receiver_company=seed.receiver_company,
            template=template,
            prompt="p",
        )
    assert material.pk is not None
    assert material.job_operation_name == "operations/abc"
