from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from collateral_ai.companies.models import Company
from collateral_ai.documents.models import Document
from collateral_ai.documents.statuses import DocumentStatus
from collateral_ai.materials.models import MarketingMaterial
from collateral_ai.materials.statuses import GenerationStatus
from collateral_ai.materials.statuses import ReviewStatus

from .serializers import DashboardStatsSerializer


class DashboardStatsView(APIView):
    """Aggregate counts powering the dashboard's stat cards."""

    @extend_schema(responses=DashboardStatsSerializer)
    def get(self, request: Request) -> Response:
        data = {
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
        return Response(DashboardStatsSerializer(data).data)
