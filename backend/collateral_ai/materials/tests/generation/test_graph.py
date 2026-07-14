import json
from dataclasses import dataclass
from unittest.mock import MagicMock

import pytest

from collateral_ai.documents.tests.factories import DocumentFactory
from collateral_ai.materials.generation.graph import GenerationDeps
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


def _template_with_slots():
    tmpl = _template()
    tmpl.image_slots = [
        {"slot_id": "hero_image", "source": "generated_placeholder"},
        {"slot_id": "sender_logo", "source": "sender"},
    ]
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
        "source_references": [{"source_id": "SENDER_SOURCE_1", "used_fact": "f"}],
    }
    model.generate_structured.side_effect = [invalid, _valid_output()]
    embedder, retriever, validator = _services(model)

    graph = _graph(embedder, retriever, model, validator)
    final = graph.invoke(_initial_state(tmpl, material))

    assert final["validation"].is_valid is True
    assert final["attempts"] == 1
    assert model.generate_structured.call_count == 2


@pytest.mark.django_db
def test_graph_repairs_inline_citation_token_then_succeeds():
    tmpl = _template()
    material = _material(tmpl)
    model = MagicMock()
    output_with_inline_token = {
        "article": {
            "headline": "Short headline",
            "subheadline": "Sub",
            "body_sections": [
                {
                    "title": "T",
                    "text": "Handles 50 million samples/sec (RECEIVER_SOURCE_1).",
                },
            ],
            "cta": "Act now",
        },
        "source_references": [{"source_id": "SENDER_SOURCE_1", "used_fact": "f"}],
    }
    model.generate_structured.side_effect = [output_with_inline_token, _valid_output()]
    embedder, retriever, validator = _services(model)

    graph = _graph(embedder, retriever, model, validator)
    final = graph.invoke(_initial_state(tmpl, material))

    assert final["validation"].is_valid is True
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
        "source_references": [{"source_id": "SENDER_SOURCE_1", "used_fact": "f"}],
    }
    model.generate_structured.return_value = invalid
    embedder, retriever, validator = _services(model)

    graph = _graph(embedder, retriever, model, validator)
    final = graph.invoke(_initial_state(tmpl, material))

    assert final["validation"].is_valid is False
    assert final["attempts"] == 2


@pytest.mark.django_db
def test_graph_stamps_image_slots_from_template_no_slots():
    tmpl = _template()  # image_slots == []
    material = _material(tmpl)
    model = MagicMock()
    model.generate_structured.return_value = _valid_output()
    embedder, retriever, validator = _services(model)

    graph = _graph(embedder, retriever, model, validator)
    final = graph.invoke(_initial_state(tmpl, material))

    assert final["output"]["image_slots"] == []


@pytest.mark.django_db
def test_graph_stamps_image_slots_from_template_with_slots():
    tmpl = _template_with_slots()
    material = _material(tmpl)
    model = MagicMock()
    # Model returns garbage image_slots data (and even omits the key on the
    # second call) — the stamp must overwrite it with the template's slots
    # regardless of what the model produced.
    output_with_garbage_slots = {
        **_valid_output(),
        "image_slots": [
            {
                "slot_id": "bogus_slot",
                "source": "sender",
                "description": "hallucinated",
            },
        ],
    }
    model.generate_structured.return_value = output_with_garbage_slots
    embedder, retriever, validator = _services(model)

    graph = _graph(embedder, retriever, model, validator)
    final = graph.invoke(_initial_state(tmpl, material))

    assert final["output"]["image_slots"] == [
        {"slot_id": "hero_image", "source": "generated_placeholder", "description": ""},
        {"slot_id": "sender_logo", "source": "sender", "description": ""},
    ]


def _graph(embedder, retriever, model, validator, max_repair_attempts=2):
    return build_generation_graph(
        GenerationDeps(
            embedder=embedder,
            retriever=retriever,
            model=model,
            validator=validator,
            max_repair_attempts=max_repair_attempts,
        ),
    )


@pytest.mark.django_db
def test_graph_passes_document_summaries_to_generation():
    doc = DocumentFactory(file_name="sender.pdf", summary="Sender doc summary.")
    tmpl = _template()
    material = _material(tmpl)
    model = MagicMock()
    model.generate_structured.return_value = _valid_output()
    embedder, retriever, validator = _services(model)
    retriever.retrieve.side_effect = lambda **kw: (
        [FakeChunk(source_id="SENDER_SOURCE_1", document_id=doc.pk)]
        if kw["source_role"] == "sender"
        else [
            FakeChunk(
                source_id="RECEIVER_SOURCE_1",
                source_role="receiver",
                document_id=doc.pk,
            ),
        ]
    )
    final = _graph(embedder, retriever, model, validator).invoke(
        _initial_state(tmpl, material),
    )
    payload = json.loads(
        model.generate_structured.call_args_list[0].kwargs["user_input"],
    )
    expected = [{"file_name": "sender.pdf", "summary": "Sender doc summary."}]
    assert payload["sender_document_summaries"] == expected
    assert final["retrieval"].context_snapshot["sender_document_summaries"] == expected


@pytest.mark.django_db
def test_graph_summaries_disabled_by_setting(settings):
    settings.MATERIAL_INCLUDE_DOC_SUMMARIES = False
    doc = DocumentFactory(file_name="sender.pdf", summary="Sender doc summary.")
    tmpl = _template()
    material = _material(tmpl)
    model = MagicMock()
    model.generate_structured.return_value = _valid_output()
    embedder, retriever, validator = _services(model)
    retriever.retrieve.side_effect = lambda **kw: (
        [FakeChunk(source_id="SENDER_SOURCE_1", document_id=doc.pk)]
        if kw["source_role"] == "sender"
        else [
            FakeChunk(
                source_id="RECEIVER_SOURCE_1",
                source_role="receiver",
                document_id=doc.pk,
            ),
        ]
    )
    _graph(embedder, retriever, model, validator).invoke(
        _initial_state(tmpl, material),
    )
    payload = json.loads(
        model.generate_structured.call_args_list[0].kwargs["user_input"],
    )
    assert "sender_document_summaries" not in payload


@pytest.mark.django_db
def test_graph_repairs_word_limit_deterministically_without_llm():
    tmpl = _template()  # body_section_max_words: 80
    material = _material(tmpl)
    model = MagicMock()
    over = _valid_output()
    over["article"]["body_sections"] = [
        {"title": "T", "text": "Keep this sentence. " + "pad " * 85 + "end."},
    ]
    model.generate_structured.return_value = over
    embedder, retriever, validator = _services(model)

    graph = _graph(embedder, retriever, model, validator)
    final = graph.invoke(_initial_state(tmpl, material))

    assert final["validation"].is_valid is True
    assert (
        final["output"]["article"]["body_sections"][0]["text"] == "Keep this sentence."
    )
    # generation happened once; the word-limit repair never hit the model
    assert model.generate_structured.call_count == 1
