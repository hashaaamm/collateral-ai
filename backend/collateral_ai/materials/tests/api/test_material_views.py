from __future__ import annotations

import datetime
from http import HTTPStatus
from unittest import mock

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from collateral_ai.companies.tests.factories import CompanyFactory
from collateral_ai.documents.statuses import DocumentStatus
from collateral_ai.documents.tests.factories import DocumentFactory
from collateral_ai.materials.models import GenerationSource
from collateral_ai.materials.models import MarketingMaterial
from collateral_ai.materials.statuses import GenerationStatus
from collateral_ai.materials.statuses import ReviewStatus
from collateral_ai.materials.tests.factories import GenerationSourceFactory
from collateral_ai.materials.tests.factories import MarketingMaterialFactory
from collateral_ai.materials.tests.factories import TemplateFactory
from collateral_ai.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db

URL = "/api/materials/"
TRIGGER = "collateral_ai.materials.api.views.trigger_generation"


@pytest.fixture
def auth_client() -> APIClient:
    client = APIClient()
    client.force_authenticate(user=UserFactory())
    return client


def companies_with_docs() -> tuple:
    sender, receiver = CompanyFactory(), CompanyFactory()
    DocumentFactory(company=sender, status=DocumentStatus.PROCESSED)
    DocumentFactory(company=receiver, status=DocumentStatus.PROCESSED)
    return sender, receiver


def create_body(sender, receiver, template) -> dict:
    return {
        "title": "AI for Smarter Logistics",
        "sender_company": sender.pk,
        "receiver_company": receiver.pk,
        "template": template.pk,
        "prompt": "Pitch our AI to improve warehouse efficiency.",
    }


def test_list_requires_auth():
    assert APIClient().get(URL).status_code == HTTPStatus.FORBIDDEN


def test_create_queues_and_triggers(auth_client):
    sender, receiver = companies_with_docs()
    template = TemplateFactory()
    with mock.patch(TRIGGER, return_value="operations/abc") as trigger:
        resp = auth_client.post(
            URL,
            create_body(sender, receiver, template),
            format="json",
        )
    assert resp.status_code == HTTPStatus.CREATED
    trigger.assert_called_once()
    body = resp.json()
    assert body["generation_status"] == GenerationStatus.QUEUED
    assert body["review_status"] == ReviewStatus.PENDING
    assert body["sender_company"]["id"] == sender.pk
    assert body["template"]["slug"] == template.slug
    material = MarketingMaterial.objects.get(pk=body["id"])
    assert material.job_operation_name == "operations/abc"


def test_create_trigger_failure_marks_failed_but_returns_201(auth_client):
    sender, receiver = companies_with_docs()
    template = TemplateFactory()
    with mock.patch(TRIGGER, side_effect=RuntimeError("job boom")):
        resp = auth_client.post(
            URL,
            create_body(sender, receiver, template),
            format="json",
        )
    assert resp.status_code == HTTPStatus.CREATED
    body = resp.json()
    assert body["generation_status"] == GenerationStatus.FAILED
    assert "job boom" in body["error_message"]


def test_create_rejects_same_sender_and_receiver(auth_client):
    sender, _ = companies_with_docs()
    template = TemplateFactory()
    body = create_body(sender, sender, template)
    with mock.patch(TRIGGER) as trigger:
        resp = auth_client.post(URL, body, format="json")
    assert resp.status_code == HTTPStatus.BAD_REQUEST
    trigger.assert_not_called()


def test_create_rejects_company_without_processed_docs(auth_client):
    sender = CompanyFactory()  # no documents
    receiver = CompanyFactory()
    DocumentFactory(company=receiver, status=DocumentStatus.PROCESSED)
    template = TemplateFactory()
    with mock.patch(TRIGGER):
        resp = auth_client.post(
            URL,
            create_body(sender, receiver, template),
            format="json",
        )
    assert resp.status_code == HTTPStatus.BAD_REQUEST
    assert "sender_company" in resp.json()


def test_create_rejects_inactive_template(auth_client):
    sender, receiver = companies_with_docs()
    template = TemplateFactory(is_active=False)
    with mock.patch(TRIGGER):
        resp = auth_client.post(
            URL,
            create_body(sender, receiver, template),
            format="json",
        )
    assert resp.status_code == HTTPStatus.BAD_REQUEST


def test_list_company_filter_matches_sender_or_receiver(auth_client):
    company = CompanyFactory()
    as_sender = MarketingMaterialFactory(sender_company=company)
    as_receiver = MarketingMaterialFactory(receiver_company=company)
    MarketingMaterialFactory()  # unrelated
    resp = auth_client.get(URL, {"company": company.pk})
    ids = {m["id"] for m in resp.json()}
    assert ids == {as_sender.pk, as_receiver.pk}


def test_list_status_and_search_filters(auth_client):
    done = MarketingMaterialFactory(
        title="Warehouse AI",
        generation_status=GenerationStatus.COMPLETED,
    )
    MarketingMaterialFactory(title="Other", generation_status=GenerationStatus.FAILED)
    resp = auth_client.get(URL, {"generation_status": "completed"})
    assert [m["id"] for m in resp.json()] == [done.pk]
    resp = auth_client.get(URL, {"search": "warehouse"})
    assert [m["id"] for m in resp.json()] == [done.pk]


def test_detail_includes_template_sources_and_companies(auth_client):
    material = MarketingMaterialFactory()
    source = GenerationSourceFactory(material=material)
    resp = auth_client.get(f"{URL}{material.pk}/")
    assert resp.status_code == HTTPStatus.OK
    body = resp.json()
    assert body["template"]["constraints"]["body_section_count"] == 2
    assert body["sender_company"]["name"] == material.sender_company.name
    assert body["sources"][0]["document"]["file_name"] == source.document.file_name


def test_patch_review_status_requires_completed(auth_client):
    material = MarketingMaterialFactory(generation_status=GenerationStatus.QUEUED)
    resp = auth_client.patch(
        f"{URL}{material.pk}/",
        {"review_status": ReviewStatus.APPROVED},
        format="json",
    )
    assert resp.status_code == HTTPStatus.BAD_REQUEST


def test_patch_approves_completed_material(auth_client):
    material = MarketingMaterialFactory(generation_status=GenerationStatus.COMPLETED)
    resp = auth_client.patch(
        f"{URL}{material.pk}/",
        {"review_status": ReviewStatus.APPROVED},
        format="json",
    )
    assert resp.status_code == HTTPStatus.OK
    material.refresh_from_db()
    assert material.review_status == ReviewStatus.APPROVED


def test_patch_prompt_does_not_regenerate(auth_client):
    material = MarketingMaterialFactory(generation_status=GenerationStatus.COMPLETED)
    with mock.patch(TRIGGER) as trigger:
        resp = auth_client.patch(
            f"{URL}{material.pk}/",
            {"prompt": "new prompt"},
            format="json",
        )
    assert resp.status_code == HTTPStatus.OK
    trigger.assert_not_called()


def test_regenerate_conflicts_while_fresh_processing(auth_client):
    material = MarketingMaterialFactory(generation_status=GenerationStatus.PROCESSING)
    with mock.patch(TRIGGER) as trigger:
        resp = auth_client.post(f"{URL}{material.pk}/regenerate/")
    assert resp.status_code == HTTPStatus.CONFLICT
    trigger.assert_not_called()


def test_regenerate_allowed_when_processing_is_stale(auth_client):
    material = MarketingMaterialFactory(generation_status=GenerationStatus.PROCESSING)
    MarketingMaterial.objects.filter(pk=material.pk).update(
        updated_at=timezone.now() - datetime.timedelta(minutes=16),
    )
    with mock.patch(TRIGGER, return_value="") as trigger:
        resp = auth_client.post(f"{URL}{material.pk}/regenerate/")
    assert resp.status_code == HTTPStatus.ACCEPTED
    trigger.assert_called_once()


def test_regenerate_resets_output_review_and_sources(auth_client):
    material = MarketingMaterialFactory(
        generation_status=GenerationStatus.COMPLETED,
        review_status=ReviewStatus.APPROVED,
        output_json={"template_id": "x"},
        error_message="old",
        validation_result={"valid": True},
        retrieved_context={"chunks": ["a"]},
        job_operation_name="operations/old",
        completed_at=timezone.now(),
    )
    GenerationSourceFactory(material=material)
    with mock.patch(TRIGGER, return_value=""):
        resp = auth_client.post(f"{URL}{material.pk}/regenerate/")
    assert resp.status_code == HTTPStatus.ACCEPTED
    material.refresh_from_db()
    assert material.generation_status == GenerationStatus.QUEUED
    assert material.review_status == ReviewStatus.PENDING
    assert material.output_json is None
    assert material.error_message == ""
    assert material.validation_result is None
    assert material.retrieved_context is None
    assert material.job_operation_name == ""
    assert material.completed_at is None
    assert not GenerationSource.objects.filter(material=material).exists()


def test_delete_material(auth_client):
    material = MarketingMaterialFactory()
    GenerationSourceFactory(material=material)
    resp = auth_client.delete(f"{URL}{material.pk}/")
    assert resp.status_code == HTTPStatus.NO_CONTENT
    assert not MarketingMaterial.objects.filter(pk=material.pk).exists()
    assert not GenerationSource.objects.filter(material_id=material.pk).exists()
