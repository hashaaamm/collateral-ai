from __future__ import annotations

from http import HTTPStatus

import pytest
from rest_framework.test import APIClient

from collateral_ai.materials.models import DEFAULT_TEMPLATE_SLUG
from collateral_ai.materials.models import Template
from collateral_ai.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db

URL = "/api/templates/"


@pytest.fixture
def auth_client() -> APIClient:
    client = APIClient()
    client.force_authenticate(user=UserFactory())
    return client


def valid_body() -> dict:
    return {
        "name": "Product Spotlight",
        "description": "One-pager",
        "constraints": {
            "headline_max_words": 8,
            "subheadline_max_words": 20,
            "body_section_count": 3,
            "body_section_max_words": 90,
            "cta_max_words": 12,
        },
        "image_slots": [
            {
                "slot_id": "hero_image",
                "label": "Hero image",
                "spec": "1200×630",
                "source": "generated_placeholder",
            },
        ],
        "theme": {"primary_color": "#112233", "accent_color": "#abcdef"},
    }


def test_list_requires_auth():
    assert APIClient().get(URL).status_code == HTTPStatus.FORBIDDEN


def test_list_returns_seed_first(auth_client):
    resp = auth_client.get(URL)
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()[0]["slug"] == DEFAULT_TEMPLATE_SLUG


def test_create_generates_slug(auth_client):
    resp = auth_client.post(URL, valid_body(), format="json")
    assert resp.status_code == HTTPStatus.CREATED
    assert resp.json()["slug"] == "product_spotlight"
    assert Template.objects.filter(slug="product_spotlight").exists()


def test_create_uniquifies_slug(auth_client):
    auth_client.post(URL, valid_body(), format="json")
    resp = auth_client.post(URL, valid_body(), format="json")
    assert resp.status_code == HTTPStatus.CREATED
    assert resp.json()["slug"] == "product_spotlight_2"


@pytest.mark.parametrize(
    ("patch", "expected_error_field"),
    [
        ({"constraints": {"headline_max_words": 8}}, "constraints"),  # missing keys
        (
            {
                "constraints": {
                    "headline_max_words": 8,
                    "subheadline_max_words": 20,
                    "body_section_count": 40,  # > 10
                    "body_section_max_words": 90,
                    "cta_max_words": 12,
                },
            },
            "constraints",
        ),
        (
            {
                "image_slots": [
                    {"slot_id": "Bad Id!", "label": "x", "spec": "", "source": "sender"},
                ],
            },
            "image_slots",
        ),
        (
            {
                "image_slots": [
                    {"slot_id": "a", "label": "x", "spec": "", "source": "sender"},
                    {"slot_id": "a", "label": "y", "spec": "", "source": "sender"},
                ],
            },
            "image_slots",
        ),
        ({"theme": {"primary_color": "blue", "accent_color": "#abcdef"}}, "theme"),
    ],
)
def test_create_validation_errors(auth_client, patch, expected_error_field):
    body = {**valid_body(), **patch}
    resp = auth_client.post(URL, body, format="json")
    assert resp.status_code == HTTPStatus.BAD_REQUEST
    assert expected_error_field in resp.json()
