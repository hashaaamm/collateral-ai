from django.core.management.base import BaseCommand

from collateral_ai.materials.generation.eval import datasets
from collateral_ai.materials.generation.eval import seed


class Command(BaseCommand):
    help = "Seed golden materials and push their ids to a LangSmith dataset."

    def add_arguments(self, parser):
        parser.add_argument("--name", default="material-gen-golden")

    def handle(self, *args, **options):
        ids = seed.build_golden_materials()
        self.stdout.write(f"Created {len(ids)} golden materials: {ids}")
        dataset_id = datasets.push_examples(
            options["name"],
            [{"material_id": mid} for mid in ids],
        )
        self.stdout.write(
            self.style.SUCCESS(f"Pushed to LangSmith dataset {dataset_id}"),
        )
