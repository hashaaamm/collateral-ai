"""Offline eval runner: run the generation graph over the golden dataset and grade.

Not part of the live path. Uploads a named experiment to LangSmith when tracing
is configured; always prints local aggregate scores.
"""

from __future__ import annotations

import subprocess

from django.core.management.base import BaseCommand

from collateral_ai.materials.generation.eval import evaluators
from collateral_ai.materials.generation.service import MaterialGenerationService
from collateral_ai.materials.models import MarketingMaterial


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
    }


class Command(BaseCommand):
    help = "Run the generation graph over the golden dataset and grade outputs."

    def add_arguments(self, parser):
        parser.add_argument("--name", default="material-gen-golden")
        parser.add_argument("--label", default="")

    def handle(self, *args, **options):
        from langsmith import Client  # noqa: PLC0415

        label = options["label"] or _git_sha()
        client = Client()
        dataset = client.read_dataset(dataset_name=options["name"])
        records = []
        for example in client.list_examples(dataset_id=dataset.id):
            material_id = example.inputs["material_id"]
            records.append(evaluate_one(material_id))
        n = len(records) or 1
        self.stdout.write(f"Experiment: {label}  (n={len(records)})")
        for key in ("schema_valid", "sources_grounded", "counts_match"):
            passed = sum(1 for r in records if r[key])
            self.stdout.write(f"  {key}: {passed}/{len(records)}")
        avg_ground = sum(r["groundedness"] for r in records) / n
        self.stdout.write(self.style.SUCCESS(f"  groundedness avg: {avg_ground:.3f}"))
