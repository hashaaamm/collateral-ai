from django.core.management.base import BaseCommand

from collateral_ai.materials.generation.eval import datasets
from collateral_ai.materials.generation.eval import seed


class Command(BaseCommand):
    help = "Seed golden materials and push their ids to a LangSmith dataset."

    def add_arguments(self, parser):
        parser.add_argument("--name", default="material-gen-golden")
        parser.add_argument(
            "--hard",
            action="store_true",
            help="Also seed hard split-fact cases carrying expected_facts "
            "(run the eval with MATERIAL_RETRIEVAL_TOP_K=3 so retrieval "
            "must select).",
        )

    def handle(self, *args, **options):
        ids = seed.build_golden_materials()
        self.stdout.write(f"Created {len(ids)} golden materials: {ids}")
        examples = [{"material_id": mid} for mid in ids]
        if options["hard"]:
            hard_entries = seed.build_hard_materials()
            hard_ids = [entry["material_id"] for entry in hard_entries]
            self.stdout.write(f"Created {len(hard_entries)} hard materials: {hard_ids}")
            examples += hard_entries
        dataset_id = datasets.push_examples(options["name"], examples)
        self.stdout.write(
            self.style.SUCCESS(f"Pushed to LangSmith dataset {dataset_id}"),
        )
