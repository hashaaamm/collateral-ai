import time

from django.core.management.base import BaseCommand
from django.core.management.base import CommandError

from collateral_ai.materials.generation.service import MaterialGenerationService
from collateral_ai.materials.models import MarketingMaterial


class Command(BaseCommand):
    help = "Generate marketing material JSON from sender/receiver company context."

    def add_arguments(self, parser):
        parser.add_argument("--material-id", required=True, type=int)
        parser.add_argument("--force", action="store_true")
        parser.add_argument("--top-k", type=int, default=None)

    def handle(self, *args, **options):
        material_id = options["material_id"]
        started = time.monotonic()
        self.stdout.write(f"timing: worker alive (material={material_id})")
        try:
            processed = MaterialGenerationService().generate(
                material_id,
                force=options["force"],
                top_k=options["top_k"],
            )
        except MarketingMaterial.DoesNotExist as exc:
            msg = f"Marketing material not found: {material_id}"
            raise CommandError(msg) from exc
        except Exception as exc:
            msg = f"generate_material failed for {material_id}: {exc}"
            raise CommandError(msg) from exc
        if not processed:
            # Duplicate/late execution: exit 0 so Cloud Run doesn't retry.
            self.stdout.write(f"generate_material skipped for {material_id}")
            return
        self.stdout.write(f"timing: pipeline total {time.monotonic() - started:.2f}s")
        self.stdout.write(
            self.style.SUCCESS(f"generate_material completed for {material_id}"),
        )
