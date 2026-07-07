from drf_spectacular.utils import OpenApiResponse
from drf_spectacular.utils import extend_schema
from drf_spectacular.utils import inline_serializer
from rest_framework import serializers
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.mixins import CreateModelMixin
from rest_framework.mixins import ListModelMixin
from rest_framework.mixins import RetrieveModelMixin
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from collateral_ai.documents import gcs
from collateral_ai.documents.models import Document
from collateral_ai.documents.statuses import DocumentStatus

from .serializers import DocumentSerializer

ALLOWED_DOCUMENT_TYPES = {"application/pdf"}


class DocumentViewSet(
    ListModelMixin,
    RetrieveModelMixin,
    CreateModelMixin,
    GenericViewSet,
):
    serializer_class = DocumentSerializer
    queryset = Document.objects.all()

    def get_queryset(self):
        # Nested under companies: company comes from the URL, always present.
        return super().get_queryset().filter(company_id=self.kwargs["company_pk"])

    @extend_schema(
        request=inline_serializer(
            name="DocumentCreateRequest",
            fields={
                "file_name": serializers.CharField(),
                "content_type": serializers.CharField(),
            },
        ),
        responses=inline_serializer(
            name="DocumentCreateResponse",
            fields={
                "id": serializers.IntegerField(),
                "company": serializers.IntegerField(),
                "file_name": serializers.CharField(),
                "content_type": serializers.CharField(),
                "status": serializers.CharField(),
                "page_count": serializers.IntegerField(allow_null=True),
                "chunks_count": serializers.IntegerField(),
                "tables_count": serializers.IntegerField(),
                "images_count": serializers.IntegerField(),
                "error_message": serializers.CharField(),
                "created_at": serializers.DateTimeField(),
                "upload_url": serializers.URLField(),
            },
        ),
    )
    def create(self, request, *args, **kwargs):
        if not gcs.is_configured():
            return Response(
                {"detail": "Document upload is not configured in this environment."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        company_pk = int(self.kwargs["company_pk"])
        file_name = request.data.get("file_name")
        content_type = request.data.get("content_type")
        if not file_name or content_type not in ALLOWED_DOCUMENT_TYPES:
            return Response(
                {"detail": "A file_name and an application/pdf content_type are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        doc = Document.objects.create(
            company_id=company_pk,
            file_name=file_name,
            content_type=content_type,
            status=DocumentStatus.PENDING,
        )
        object_path = gcs.build_document_object_path(company_pk, doc.pk, file_name)
        doc.storage_path = object_path
        doc.save(update_fields=["storage_path", "updated_at"])
        upload_url = gcs.signed_upload_url(object_path, content_type)
        data = self.get_serializer(doc).data
        return Response({**data, "upload_url": upload_url}, status=status.HTTP_201_CREATED)

    @extend_schema(
        request=None,
        responses={202: OpenApiResponse(response=DocumentSerializer)},
    )
    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None, company_pk=None):
        doc = self.get_object()
        # Phase 1: the worker is a stub. Flip to processing so the UI shows a pill;
        # Phase 2 wires this to the Cloud Run Job / inline worker.
        doc.status = DocumentStatus.PROCESSING
        doc.error_message = ""
        doc.save(update_fields=["status", "error_message", "updated_at"])
        return Response(self.get_serializer(doc).data, status=status.HTTP_202_ACCEPTED)
