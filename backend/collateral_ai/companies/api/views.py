from drf_spectacular.utils import extend_schema
from rest_framework import filters
from rest_framework.decorators import action
from rest_framework.mixins import CreateModelMixin
from rest_framework.mixins import DestroyModelMixin
from rest_framework.mixins import ListModelMixin
from rest_framework.mixins import RetrieveModelMixin
from rest_framework.mixins import UpdateModelMixin
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from collateral_ai.companies import services
from collateral_ai.companies.models import Company

from .serializers import CompanySerializer
from .serializers import LogoUploadUrlRequestSerializer
from .serializers import LogoUploadUrlResponseSerializer


class CompanyViewSet(
    RetrieveModelMixin,
    ListModelMixin,
    CreateModelMixin,
    UpdateModelMixin,
    DestroyModelMixin,
    GenericViewSet,
):
    serializer_class = CompanySerializer
    queryset = Company.objects.all()
    filter_backends = [filters.SearchFilter]
    search_fields = ["name"]

    def perform_destroy(self, instance):
        services.delete_company(instance)

    @extend_schema(
        request=LogoUploadUrlRequestSerializer,
        responses=LogoUploadUrlResponseSerializer,
    )
    @action(detail=False, methods=["post"], url_path="logo-upload-url")
    def logo_upload_url(self, request):
        body = LogoUploadUrlRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        upload_url, object_path = services.create_logo_upload_url(
            **body.validated_data,
        )
        data = {"upload_url": upload_url, "object_path": object_path}
        return Response(LogoUploadUrlResponseSerializer(data).data)
