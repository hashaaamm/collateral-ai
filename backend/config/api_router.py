from django.conf import settings
from django.urls import path
from rest_framework.routers import DefaultRouter
from rest_framework.routers import SimpleRouter
from rest_framework_nested import routers as nested_routers

from collateral_ai.companies.api.views import CompanyViewSet
from collateral_ai.dashboard.api.views import DashboardStatsView
from collateral_ai.documents.api.views import DocumentViewSet
from collateral_ai.users.api.views import UserViewSet

router = DefaultRouter() if settings.DEBUG else SimpleRouter()

router.register("users", UserViewSet)
router.register("companies", CompanyViewSet, basename="company")

# Documents are a sub-resource of a company: /api/companies/{company_pk}/documents/
companies_router = nested_routers.NestedSimpleRouter(
    router,
    "companies",
    lookup="company",
)
companies_router.register("documents", DocumentViewSet, basename="company-documents")

app_name = "api"
urlpatterns = [
    *router.urls,
    *companies_router.urls,
    path("dashboard/stats/", DashboardStatsView.as_view(), name="dashboard-stats"),
]
