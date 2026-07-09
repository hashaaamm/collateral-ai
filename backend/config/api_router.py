from django.conf import settings
from rest_framework.routers import DefaultRouter
from rest_framework.routers import SimpleRouter
from rest_framework_nested import routers as nested_routers

from collateral_ai.companies.api.views import CompanyViewSet
from collateral_ai.documents.api.views import DocumentViewSet
from collateral_ai.materials.api.views import MaterialViewSet
from collateral_ai.materials.api.views import TemplateViewSet
from collateral_ai.users.api.views import UserViewSet

router = DefaultRouter() if settings.DEBUG else SimpleRouter()

router.register("users", UserViewSet)
router.register("companies", CompanyViewSet, basename="company")
router.register("templates", TemplateViewSet, basename="template")
router.register("materials", MaterialViewSet, basename="material")

# Documents are a sub-resource of a company: /api/companies/{company_pk}/documents/
companies_router = nested_routers.NestedSimpleRouter(
    router,
    "companies",
    lookup="company",
)
companies_router.register("documents", DocumentViewSet, basename="company-documents")

app_name = "api"
urlpatterns = router.urls + companies_router.urls
