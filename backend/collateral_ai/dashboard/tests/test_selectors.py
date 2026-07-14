import pytest

from collateral_ai.companies.tests.factories import CompanyFactory
from collateral_ai.dashboard import selectors
from collateral_ai.documents.statuses import DocumentStatus
from collateral_ai.documents.tests.factories import DocumentFactory
from collateral_ai.materials.statuses import GenerationStatus
from collateral_ai.materials.statuses import ReviewStatus
from collateral_ai.materials.tests.factories import MarketingMaterialFactory

pytestmark = pytest.mark.django_db


def test_get_dashboard_stats_counts():
    CompanyFactory()
    DocumentFactory(status=DocumentStatus.PROCESSED)
    DocumentFactory(status=DocumentStatus.PROCESSING)
    MarketingMaterialFactory(
        generation_status=GenerationStatus.COMPLETED,
        review_status=ReviewStatus.PENDING,
    )
    stats = selectors.get_dashboard_stats()
    # Factories above create extra companies via SubFactories, so only the
    # non-company counts are exact.
    assert stats["companies_count"] >= 1
    assert stats["documents_processed"] == 1
    assert stats["documents_processing"] == 1
    assert stats["materials_generated"] == 1
    assert stats["materials_needs_review"] == 1
