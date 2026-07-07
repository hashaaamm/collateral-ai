from rest_framework import status
from rest_framework.decorators import action
from rest_framework.mixins import CreateModelMixin
from rest_framework.mixins import ListModelMixin
from rest_framework.mixins import RetrieveModelMixin
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from collateral_ai.companies import gcs
from collateral_ai.companies.models import Company

from .serializers import CompanySerializer

ALLOWED_LOGO_TYPES = {"image/png", "image/jpeg", "image/webp", "image/svg+xml"}


class CompanyViewSet(
    RetrieveModelMixin,
    ListModelMixin,
    CreateModelMixin,
    GenericViewSet,
):
    serializer_class = CompanySerializer
    queryset = Company.objects.all()

    @action(detail=False, methods=["post"], url_path="logo-upload-url")
    def logo_upload_url(self, request):
        if not gcs.is_configured():
            return Response(
                {"detail": "Logo upload is not configured in this environment."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        filename = request.data.get("filename")
        content_type = request.data.get("content_type")
        if not filename or content_type not in ALLOWED_LOGO_TYPES:
            return Response(
                {"detail": "A filename and a supported image content_type are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        object_path = gcs.build_logo_object_path(filename)
        upload_url = gcs.signed_upload_url(object_path, content_type)
        return Response({"upload_url": upload_url, "object_path": object_path})
