"""Worker 2 orchestration: claim → retrieve → generate → validate/repair → save.

State machine rules (spec §6.3): claim is its own short transaction so the row
lock is never held during the multi-minute pipeline; completed/processing
without --force skip with exit 0; review_status is never touched here.
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from collateral_ai.documents.processing.embeddings import EmbeddingService
from collateral_ai.materials.generation.llm import GenerationClient
from collateral_ai.materials.generation.prompts import SYSTEM_INSTRUCTION
from collateral_ai.materials.generation.prompts import build_generation_payload
from collateral_ai.materials.generation.prompts import build_retrieval_query
from collateral_ai.materials.generation.repair import OutputRepairService
from collateral_ai.materials.generation.retrieval import RetrievalService
from collateral_ai.materials.generation.schema import build_response_schema
from collateral_ai.materials.generation.validation import OutputValidator
from collateral_ai.materials.models import GenerationSource
from collateral_ai.materials.models import MarketingMaterial
from collateral_ai.materials.statuses import GenerationStatus
from collateral_ai.materials.statuses import SourceRole

logger = logging.getLogger(__name__)


class MaterialGenerationService:
    def __init__(
        self,
        *,
        embedder: EmbeddingService | None = None,
        retriever: RetrievalService | None = None,
        client: GenerationClient | None = None,
        repairer: OutputRepairService | None = None,
    ) -> None:
        self.embedder = embedder or EmbeddingService()
        self.retriever = retriever or RetrievalService()
        self.client = client or GenerationClient()
        self.repairer = repairer or OutputRepairService(self.client)
        self.validator = OutputValidator()
        self.default_top_k = int(settings.MATERIAL_RETRIEVAL_TOP_K)
        self.max_repair_attempts = int(settings.MATERIAL_MAX_REPAIR_ATTEMPTS)

    def generate(
        self,
        material_id: int,
        *,
        force: bool = False,
        top_k: int | None = None,
    ) -> bool:
        material = self._claim(material_id, force=force)
        if material is None:
            return False
        try:
            self._run_pipeline(material, top_k=top_k or self.default_top_k)
        except Exception as exc:
            logger.exception("generation failed material=%s", material_id)
            MarketingMaterial.objects.filter(pk=material.pk).update(
                generation_status=GenerationStatus.FAILED,
                error_message=str(exc),
                updated_at=timezone.now(),
            )
            raise
        return True

    def _claim(self, material_id: int, *, force: bool) -> MarketingMaterial | None:
        """Short standalone transaction: lock → check → set processing → commit.

        The command runs outside ATOMIC_REQUESTS, so select_for_update needs
        this explicit atomic block. Generation runs OUTSIDE it — the row lock
        must not be held for the whole pipeline.
        """
        with transaction.atomic():
            material = (
                MarketingMaterial.objects.select_for_update()
                .select_related("sender_company", "receiver_company", "template")
                .get(pk=material_id)
            )
            claimable = {GenerationStatus.QUEUED, GenerationStatus.FAILED}
            if not force and material.generation_status not in claimable:
                # Duplicate execution racing a running job, or an already-done
                # row: skip quietly (exit 0) so Cloud Run doesn't retry.
                logger.info(
                    "skipping material=%s status=%s (use --force to override)",
                    material_id,
                    material.generation_status,
                )
                return None
            material.generation_status = GenerationStatus.PROCESSING
            material.error_message = ""
            material.save(
                update_fields=["generation_status", "error_message", "updated_at"],
            )
        return material

    def _run_pipeline(self, material: MarketingMaterial, *, top_k: int) -> None:
        template = material.template
        query_embedding = self.embedder.embed_query(build_retrieval_query(material))
        sender_chunks = self.retriever.retrieve(
            company_id=material.sender_company_id,
            query_embedding=query_embedding,
            source_role=SourceRole.SENDER,
            source_prefix="SENDER_SOURCE",
            top_k=top_k,
        )
        receiver_chunks = self.retriever.retrieve(
            company_id=material.receiver_company_id,
            query_embedding=query_embedding,
            source_role=SourceRole.RECEIVER,
            source_prefix="RECEIVER_SOURCE",
            top_k=top_k,
        )
        for role, chunks, company in (
            ("sender", sender_chunks, material.sender_company),
            ("receiver", receiver_chunks, material.receiver_company),
        ):
            if not chunks:
                msg = (
                    f"No processed document chunks for {role} company "
                    f"{company.name!r} — upload and process documents first."
                )
                raise ValueError(msg)

        source_map = {c.source_id: c for c in [*sender_chunks, *receiver_chunks]}
        allowed_ids = set(source_map)
        response_schema = build_response_schema(
            constraints=template.constraints,
            image_slots=template.image_slots,
        )

        output = self.client.generate_json(
            system_instruction=SYSTEM_INSTRUCTION,
            user_input=build_generation_payload(
                material=material,
                sender_chunks=sender_chunks,
                receiver_chunks=receiver_chunks,
            ),
            response_schema=response_schema,
        )
        output = self._stamp(output, template)
        result = self._validate(output, template, allowed_ids)

        attempts = 0
        while not result.is_valid and attempts < self.max_repair_attempts:
            attempts += 1
            logger.warning(
                "validation failed material=%s attempt=%s errors=%s",
                material.pk,
                attempts,
                result.errors,
            )
            output = self.repairer.repair(
                output=output,
                errors=result.errors,
                constraints=template.constraints,
                image_slots=template.image_slots,
                allowed_source_ids=sorted(allowed_ids),
                response_schema=response_schema,
            )
            output = self._stamp(output, template)
            result = self._validate(output, template, allowed_ids)

        context_snapshot = {
            "sender_context": [c.to_prompt_dict() for c in sender_chunks],
            "receiver_context": [c.to_prompt_dict() for c in receiver_chunks],
        }
        if not result.is_valid:
            # Persist the evidence for debugging (JSON tab), then fail loudly.
            MarketingMaterial.objects.filter(pk=material.pk).update(
                output_json=output,
                validation_result=result.to_dict(),
                retrieved_context=context_snapshot,
                updated_at=timezone.now(),
            )
            msg = f"Generated output failed validation: {result.errors}"
            raise ValueError(msg)

        self._save_completed(material, output, result, context_snapshot, source_map)

    def _stamp(self, output: dict, template) -> dict:
        """template_id and theme are template-owned — never trusted from the model."""
        output["template_id"] = template.slug
        output["theme"] = dict(template.theme)
        return output

    def _validate(self, output, template, allowed_ids):
        return self.validator.validate(
            output=output,
            constraints=template.constraints,
            image_slots=template.image_slots,
            allowed_source_ids=allowed_ids,
        )

    @transaction.atomic
    def _save_completed(
        self,
        material,
        output: dict,
        result,
        context_snapshot: dict,
        source_map: dict,
    ) -> None:
        now = timezone.now()
        MarketingMaterial.objects.filter(pk=material.pk).update(
            generation_status=GenerationStatus.COMPLETED,
            output_json=output,
            validation_result=result.to_dict(),
            retrieved_context=context_snapshot,
            error_message="",
            completed_at=now,
            updated_at=now,
        )
        GenerationSource.objects.filter(material=material).delete()
        # Strict source validation (Task 7) guarantees every cited id maps.
        GenerationSource.objects.bulk_create(
            [
                GenerationSource(
                    material=material,
                    company_id=source_map[ref["source_id"]].company_id,
                    document_id=source_map[ref["source_id"]].document_id,
                    chunk_id=source_map[ref["source_id"]].chunk_id,
                    source_role=source_map[ref["source_id"]].source_role,
                    page_number=source_map[ref["source_id"]].page_number,
                    snippet=source_map[ref["source_id"]].content[:500],
                    used_fact=ref["used_fact"][:1000],
                    relevance_score=source_map[ref["source_id"]].relevance_score,
                )
                for ref in output["source_references"]
            ],
        )
