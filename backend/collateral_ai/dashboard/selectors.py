"""Read-side aggregates powering the dashboard's stat cards."""

from __future__ import annotations

from collateral_ai.companies.models import Company
from collateral_ai.documents.models import Document
from collateral_ai.documents.statuses import DocumentStatus
from collateral_ai.materials.models import MarketingMaterial
from collateral_ai.materials.statuses import GenerationStatus
from collateral_ai.materials.statuses import ReviewStatus


def get_dashboard_stats() -> dict[str, int]:
    return {
        "companies_count": Company.objects.count(),
        "documents_processed": Document.objects.filter(
            status=DocumentStatus.PROCESSED,
        ).count(),
        "documents_processing": Document.objects.filter(
            status=DocumentStatus.PROCESSING,
        ).count(),
        "materials_generated": MarketingMaterial.objects.filter(
            generation_status=GenerationStatus.COMPLETED,
        ).count(),
        "materials_needs_review": MarketingMaterial.objects.filter(
            review_status=ReviewStatus.PENDING,
        ).count(),
    }
