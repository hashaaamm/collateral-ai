from django.conf import settings
from rest_framework.routers import DefaultRouter
from rest_framework.routers import SimpleRouter

from collateral_ai.companies.api.views import CompanyViewSet
from collateral_ai.users.api.views import UserViewSet

router = DefaultRouter() if settings.DEBUG else SimpleRouter()

router.register("users", UserViewSet)
router.register("companies", CompanyViewSet, basename="company")


app_name = "api"
urlpatterns = router.urls
