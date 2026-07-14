from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from collateral_ai.dashboard import selectors

from .serializers import DashboardStatsSerializer


class DashboardStatsView(APIView):
    """Aggregate counts powering the dashboard's stat cards."""

    @extend_schema(responses=DashboardStatsSerializer)
    def get(self, request: Request) -> Response:
        return Response(
            DashboardStatsSerializer(selectors.get_dashboard_stats()).data,
        )
