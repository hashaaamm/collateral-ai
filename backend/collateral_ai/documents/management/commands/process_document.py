import time

from django.core.management.base import BaseCommand
from django.core.management.base import CommandError

from collateral_ai.documents.models import Document
from collateral_ai.documents.processing.pipeline import DocumentProcessingService


class Command(BaseCommand):
    help = "Process an uploaded PDF: extract, chunk, embed, and store DocumentChunks."

    def add_arguments(self, parser):
        parser.add_argument("--document-id", required=True, type=int)
        parser.add_argument("--force", action="store_true")

    def handle(self, *args, **options):
        document_id = options["document_id"]
        # First line of app code: task-start → here = image pull + interpreter + django.setup().
        started = time.monotonic()
        self.stdout.write(f"timing: worker alive, django ready (document={document_id})")
        try:
            DocumentProcessingService().process(document_id, force=options["force"])
        except Document.DoesNotExist as exc:
            raise CommandError(f"Document not found: {document_id}") from exc
        except Exception as exc:
            raise CommandError(f"process_document failed for {document_id}: {exc}") from exc
        self.stdout.write(f"timing: pipeline total {time.monotonic() - started:.2f}s")
        self.stdout.write(self.style.SUCCESS(f"process_document completed for {document_id}"))
