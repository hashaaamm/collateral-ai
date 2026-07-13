from dataclasses import dataclass
from unittest.mock import MagicMock

import pytest

from collateral_ai.materials.generation.graph import build_generation_graph
from collateral_ai.materials.generation.validation import OutputValidator


@dataclass
class FakeChunk:
    source_id: str
    company_id: int = 1
    document_id: int = 1
    chunk_id: int = 1
    page_number: int = 1
    content: str = "fact text"
    relevance_score: float = 0.1
    source_role: str = "sender"

    def to_prompt_dict(self):
        return {"source_id": self.source_id, "content": self.content}


def _template():
    tmpl = MagicMock()
    tmpl.slug = "newsletter_article_v1"
    tmpl.name = "Newsletter Article"
    tmpl.theme = {"primary_color": "#000"}
    tmpl.constraints = {
        "headline_max_words": 10,
        "subheadline_max_words": 22,
        "body_section_count": 1,
        "body_section_max_words": 80,
        "cta_max_words": 15,
    }
    tmpl.image_slots = []
    return tmpl


def _company(company_id, name):
    c = MagicMock()
    c.pk = company_id
    c.name = name
    c.industry = "software"
    c.description = "A company."
    return c


def _material(tmpl):
    m = MagicMock()
    m.pk = 1
    m.sender_company_id = 1
    m.receiver_company_id = 2
    m.sender_company = _company(1, "Sender Co")
    m.receiver_company = _company(2, "Receiver Co")
    m.template = tmpl
    m.cta_link = ""
    m.prompt = "Introduce our product."
    m.tone = "professional"
    m.cta_style = "direct"
    m.language = "en"
    return m


def _valid_output():
    return {
        "article": {
            "headline": "Short headline",
            "subheadline": "Sub",
            "body_sections": [{"title": "T", "text": "body text"}],
            "cta": "Act now",
        },
        "image_slots": [],
        "source_references": [{"source_id": "SENDER_SOURCE_1", "used_fact": "f"}],
    }


def _initial_state(tmpl, material):
    return {
        "material_id": 1,
        "material": material,
        "template": tmpl,
        "top_k": 4,
        "attempts": 0,
    }


def _services(model):
    embedder = MagicMock()
    embedder.embed_query.return_value = [0.0] * 768
    retriever = MagicMock()
    retriever.retrieve.side_effect = lambda **kw: (
        [
            FakeChunk(source_id="SENDER_SOURCE_1"),
        ]
        if kw["source_role"] == "sender"
        else [FakeChunk(source_id="RECEIVER_SOURCE_1", source_role="receiver")]
    )
    return embedder, retriever, OutputValidator()


@pytest.mark.django_db
def test_graph_repairs_once_then_succeeds():
    (tmpl,) = (_template(),)
    material = _material(tmpl)
    model = MagicMock()
    invalid = {
        "article": {
            "headline": "x " * 40,
            "subheadline": "s",
            "body_sections": [{"title": "T", "text": "b"}],
            "cta": "c",
        },
        "image_slots": [],
        "source_references": [{"source_id": "SENDER_SOURCE_1", "used_fact": "f"}],
    }
    model.generate_structured.side_effect = [invalid, _valid_output()]
    embedder, retriever, validator = _services(model)

    graph = build_generation_graph(
        embedder=embedder,
        retriever=retriever,
        model=model,
        validator=validator,
        max_repair_attempts=2,
    )
    final = graph.invoke(_initial_state(tmpl, material))

    assert final["is_valid"] is True
    assert final["attempts"] == 1
    assert model.generate_structured.call_count == 2


@pytest.mark.django_db
def test_graph_fails_after_max_attempts():
    tmpl = _template()
    material = _material(tmpl)
    model = MagicMock()
    invalid = {
        "article": {
            "headline": "x " * 40,
            "subheadline": "s",
            "body_sections": [{"title": "T", "text": "b"}],
            "cta": "c",
        },
        "image_slots": [],
        "source_references": [{"source_id": "SENDER_SOURCE_1", "used_fact": "f"}],
    }
    model.generate_structured.return_value = invalid
    embedder, retriever, validator = _services(model)

    graph = build_generation_graph(
        embedder=embedder,
        retriever=retriever,
        model=model,
        validator=validator,
        max_repair_attempts=2,
    )
    final = graph.invoke(_initial_state(tmpl, material))

    assert final["is_valid"] is False
    assert final["attempts"] == 2
