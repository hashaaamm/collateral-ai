from io import StringIO
from unittest.mock import MagicMock

import pytest
from django.core.management import call_command

from collateral_ai.documents.tests.factories import DocumentChunkFactory
from collateral_ai.materials.management.commands import run_eval
from collateral_ai.materials.statuses import GenerationStatus
from collateral_ai.materials.tests.factories import MarketingMaterialFactory


def _valid_output():
    return {
        "article": {
            "headline": "Short",
            "subheadline": "Sub",
            "body_sections": [
                {"title": "T", "text": "b"},
                {"title": "T2", "text": "b2"},
            ],
            "cta": "Act",
        },
        "image_slots": [
            {
                "slot_id": "hero_image",
                "description": "d",
                "source": "generated_placeholder",
            },
            {"slot_id": "sender_logo", "description": "d", "source": "sender"},
        ],
        "source_references": [{"source_id": "SENDER_SOURCE_1", "used_fact": "f"}],
    }


@pytest.mark.django_db
def test_evaluate_one_returns_scored_record(monkeypatch):
    material = MarketingMaterialFactory(generation_status=GenerationStatus.QUEUED)
    DocumentChunkFactory(company=material.sender_company)
    DocumentChunkFactory(company=material.receiver_company)

    fake_model = MagicMock()
    fake_model.generate_structured.return_value = _valid_output()
    monkeypatch.setattr(
        "collateral_ai.materials.generation.service.GenerationModel",
        lambda: fake_model,
    )
    monkeypatch.setattr(
        "collateral_ai.materials.generation.service.EmbeddingService",
        _fake_embedder,
    )

    record = run_eval.evaluate_one(material.pk, judge=lambda prompt: "0.9")

    assert record["schema_valid"] is True
    assert record["sources_grounded"] is True
    assert record["groundedness"] == 0.9


def _fake_embedder():
    e = MagicMock()
    e.embed_query.return_value = [0.0] * 768
    return e


def test_handle_uploads_scored_experiment_to_langsmith(monkeypatch):
    fake_client_instance = MagicMock()
    fake_client_cls = MagicMock(return_value=fake_client_instance)
    monkeypatch.setattr("langsmith.Client", fake_client_cls)

    fake_results = MagicMock()
    fake_results.experiment_name = "abc123-experiment"
    fake_evaluate = MagicMock(return_value=fake_results)
    monkeypatch.setattr("langsmith.evaluation.evaluate", fake_evaluate)

    call_command(
        "run_eval",
        name="material-gen-golden",
        label="abc123",
        stdout=StringIO(),
    )

    fake_evaluate.assert_called_once()
    call_args, call_kwargs = fake_evaluate.call_args
    target = call_args[0]
    assert callable(target)
    assert call_kwargs["data"] == "material-gen-golden"
    assert call_kwargs["client"] is fake_client_instance
    assert call_kwargs["experiment_prefix"] == "abc123"
    evaluators_arg = call_kwargs["evaluators"]
    assert len(evaluators_arg) > 0
    assert all(callable(e) for e in evaluators_arg)


class _FakeRun:
    def __init__(self, outputs):
        self.outputs = outputs


@pytest.mark.parametrize("outputs", [None, {}])
def test_eval_wrappers_score_failure_when_outputs_missing(outputs):
    run = _FakeRun(outputs)

    assert run_eval._eval_schema_valid(run) == {  # noqa: SLF001
        "key": "schema_valid",
        "score": False,
    }
    assert run_eval._eval_sources_grounded(run) == {  # noqa: SLF001
        "key": "sources_grounded",
        "score": False,
    }
    assert run_eval._eval_counts_match(run) == {  # noqa: SLF001
        "key": "counts_match",
        "score": False,
    }
    assert run_eval._eval_groundedness(run) == {  # noqa: SLF001
        "key": "groundedness",
        "score": 0.0,
    }


def test_eval_wrappers_score_failure_when_output_falsy_but_present():
    run = _FakeRun({"output": {}, "template_id": None, "context": {}})

    assert run_eval._eval_schema_valid(run) == {  # noqa: SLF001
        "key": "schema_valid",
        "score": False,
    }
    assert run_eval._eval_sources_grounded(run) == {  # noqa: SLF001
        "key": "sources_grounded",
        "score": False,
    }
    assert run_eval._eval_counts_match(run) == {  # noqa: SLF001
        "key": "counts_match",
        "score": False,
    }
    assert run_eval._eval_groundedness(run) == {  # noqa: SLF001
        "key": "groundedness",
        "score": 0.0,
    }
