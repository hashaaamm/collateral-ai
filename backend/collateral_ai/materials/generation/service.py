"""Worker 2 orchestration: claim → LangGraph pipeline → save.

Ownership split: this service owns the DB state machine (claim, COMPLETED /
FAILED writes); graph.py owns compute and never touches the database rows.

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
from collateral_ai.materials.generation.graph import GenerationDeps
from collateral_ai.materials.generation.graph import build_generation_graph
from collateral_ai.materials.generation.model import GenerationModel
from collateral_ai.materials.generation.retrieval import RetrievalService
from collateral_ai.materials.generation.validation import OutputValidator
from collateral_ai.materials.models import GenerationSource
from collateral_ai.materials.models import MarketingMaterial
from collateral_ai.materials.statuses import GenerationStatus

logger = logging.getLogger(__name__)


class MaterialGenerationService:
    def __init__(
        self,
        *,
        embedder: EmbeddingService | None = None,
        retriever: RetrievalService | None = None,
        model: GenerationModel | None = None,
    ) -> None:
        self.embedder = embedder or EmbeddingService()
        self.retriever = retriever or RetrievalService()
        self.model = model or GenerationModel()
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
                # row: skip quietly (exit 0) so the K8s Job doesn't retry.
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
        deps = GenerationDeps(
            embedder=self.embedder,
            retriever=self.retriever,
            model=self.model,
            validator=self.validator,
            max_repair_attempts=self.max_repair_attempts,
        )
        final = build_generation_graph(deps).invoke(
            {
                "material_id": material.pk,
                "material": material,
                "template": material.template,
                "top_k": top_k,
                "attempts": 0,
            },
        )
        output = final["output"]
        result = final["validation"]
        retrieval = final["retrieval"]
        if not result.is_valid:
            MarketingMaterial.objects.filter(pk=material.pk).update(
                output_json=output,
                validation_result=result.to_dict(),
                retrieved_context=retrieval.context_snapshot,
                updated_at=timezone.now(),
            )
            msg = f"Generated output failed validation: {result.errors}"
            raise ValueError(msg)
        self._save_completed(material, output, result, retrieval)

    @transaction.atomic
    def _save_completed(self, material, output: dict, result, retrieval) -> None:
        now = timezone.now()
        MarketingMaterial.objects.filter(pk=material.pk).update(
            generation_status=GenerationStatus.COMPLETED,
            output_json=output,
            validation_result=result.to_dict(),
            retrieved_context=retrieval.context_snapshot,
            error_message="",
            completed_at=now,
            updated_at=now,
        )
        GenerationSource.objects.filter(material=material).delete()
        # Source validation guarantees every cited id maps to a retrieved chunk.
        rows = []
        for ref in output["source_references"]:
            src = retrieval.source_map[ref["source_id"]]
            rows.append(
                GenerationSource(
                    material=material,
                    company_id=src.company_id,
                    document_id=src.document_id,
                    chunk_id=src.chunk_id,
                    source_role=src.source_role,
                    page_number=src.page_number,
                    snippet=src.content[:500],
                    used_fact=ref["used_fact"][:1000],
                    relevance_score=src.relevance_score,
                ),
            )
        GenerationSource.objects.bulk_create(rows)
