"""Offline eval runner: run the generation graph over the golden dataset and grade.

Not part of the live path. Uploads a scored, named experiment to LangSmith
(populating the side-by-side comparison UI) and prints a short local summary.
"""

from __future__ import annotations

import subprocess

from django.core.management.base import BaseCommand

from collateral_ai.materials.generation.eval import evaluators
from collateral_ai.materials.generation.service import MaterialGenerationService
from collateral_ai.materials.models import MarketingMaterial
from collateral_ai.materials.models import Template


def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],  # noqa: S607
            text=True,
        ).strip()
    except (subprocess.SubprocessError, OSError):
        return "local"


def evaluate_one(material_id: int, *, judge=None) -> dict:
    MaterialGenerationService().generate(material_id, force=True)
    material = MarketingMaterial.objects.select_related("template").get(pk=material_id)
    output = material.output_json or {}
    context = material.retrieved_context or {}
    allowed_ids = {
        item["source_id"]
        for key in ("sender_context", "receiver_context")
        for item in context.get(key, [])
    }
    return {
        "material_id": material_id,
        "schema_valid": evaluators.schema_valid(output, material.template),
        "sources_grounded": evaluators.sources_grounded(output, allowed_ids),
        "counts_match": evaluators.counts_match(output, material.template),
        "groundedness": evaluators.groundedness_judge(output, context, judge=judge),
        "specificity": evaluators.specificity_judge(output, judge=judge),
    }


def _allowed_ids(context: dict) -> set[str]:
    return {
        item["source_id"]
        for key in ("sender_context", "receiver_context")
        for item in context.get(key, [])
    }


def _target(inputs: dict) -> dict:
    """LangSmith target: run generation for one dataset example and return outputs."""
    material_id = inputs["material_id"]
    MaterialGenerationService().generate(material_id, force=True)
    material = MarketingMaterial.objects.select_related("template").get(pk=material_id)
    return {
        "output": material.output_json or {},
        "context": material.retrieved_context or {},
        "template_id": material.template_id,
    }


def _eval_schema_valid(run, example=None):
    outputs = run.outputs or {}
    output = outputs.get("output")
    if not output:
        return {"key": "schema_valid", "score": False}
    template_id = outputs.get("template_id")
    if template_id is None:
        return {"key": "schema_valid", "score": False}
    template = Template.objects.get(pk=template_id)
    return {
        "key": "schema_valid",
        "score": evaluators.schema_valid(output, template),
    }


def _eval_sources_grounded(run, example=None):
    outputs = run.outputs or {}
    output = outputs.get("output")
    if not output:
        return {"key": "sources_grounded", "score": False}
    allowed_ids = _allowed_ids(outputs.get("context", {}))
    score = evaluators.sources_grounded(output, allowed_ids)
    return {"key": "sources_grounded", "score": score}


def _eval_counts_match(run, example=None):
    outputs = run.outputs or {}
    output = outputs.get("output")
    if not output:
        return {"key": "counts_match", "score": False}
    template_id = outputs.get("template_id")
    if template_id is None:
        return {"key": "counts_match", "score": False}
    template = Template.objects.get(pk=template_id)
    return {
        "key": "counts_match",
        "score": evaluators.counts_match(output, template),
    }


def _eval_groundedness(run, example=None):
    outputs = run.outputs or {}
    output = outputs.get("output")
    if not output:
        return {"key": "groundedness", "score": 0.0}
    score = evaluators.groundedness_judge(output, outputs.get("context", {}))
    return {"key": "groundedness", "score": score}


def _eval_specificity(run, example=None):
    outputs = run.outputs or {}
    output = outputs.get("output")
    if not output:
        return {"key": "specificity", "score": 0.0}
    score = evaluators.specificity_judge(output)
    return {"key": "specificity", "score": score}


class Command(BaseCommand):
    help = "Run generation over the golden dataset and upload a scored experiment"

    def add_arguments(self, parser):
        parser.add_argument("--name", default="material-gen-golden")
        parser.add_argument("--label", default="")

    def handle(self, *args, **options):
        from langsmith import Client  # noqa: PLC0415
        from langsmith.evaluation import evaluate  # noqa: PLC0415

        label = options["label"] or _git_sha()
        client = Client()
        results = evaluate(
            _target,
            data=options["name"],
            evaluators=[
                _eval_schema_valid,
                _eval_sources_grounded,
                _eval_counts_match,
                _eval_groundedness,
                _eval_specificity,
            ],
            experiment_prefix=label,
            client=client,
        )
        experiment_name = getattr(results, "experiment_name", label)
        msg = f"Uploaded experiment '{experiment_name}' (dataset={options['name']})"
        self.stdout.write(self.style.SUCCESS(msg))
