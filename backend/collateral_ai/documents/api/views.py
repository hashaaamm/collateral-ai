import logging

from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse
from drf_spectacular.utils import extend_schema
from drf_spectacular.utils import inline_serializer
from rest_framework import serializers
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.mixins import CreateModelMixin
from rest_framework.mixins import DestroyModelMixin
from rest_framework.mixins import ListModelMixin
from rest_framework.mixins import RetrieveModelMixin
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from collateral_ai.documents import gcs
from collateral_ai.documents.models import Document
from collateral_ai.documents.statuses import DocumentStatus
from collateral_ai.documents.worker_trigger import trigger_processing

from .serializers import DocumentSerializer

ALLOWED_DOCUMENT_TYPES = {"application/pdf"}
logger = logging.getLogger(__name__)

FILE_NAME_MAX_LENGTH = 255  # matches Document.file_name max_length

# User-facing failure text; the real exception is logged server-side, never
# sent to clients.
_GENERIC_DISPATCH_ERROR = "Processing could not be started. Please try again."


class DocumentViewSet(
    ListModelMixin,
    RetrieveModelMixin,
    CreateModelMixin,
    DestroyModelMixin,
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
        if (
            not file_name
            or len(file_name) > FILE_NAME_MAX_LENGTH
            or content_type not in ALLOWED_DOCUMENT_TYPES
        ):
            return Response(
                {
                    "detail": (
                        "A file_name (<= 255 chars) and an application/pdf "
                        "content_type are required."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        doc = Document.objects.create(
            company_id=company_pk,
            file_name=file_name,
            content_type=content_type,
            status=DocumentStatus.PENDING,
        )
        # ATOMIC_REQUESTS wraps the whole request in a transaction, so if signing raises
        # below, this row is rolled back — no orphan PENDING row is left behind.
        object_path = gcs.build_document_object_path(company_pk, doc.pk, file_name)
        doc.storage_path = object_path
        doc.save(update_fields=["storage_path", "updated_at"])
        upload_url = gcs.signed_upload_url(object_path, content_type)
        data = self.get_serializer(doc).data
        return Response(
            {**data, "upload_url": upload_url},
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        request=None,
        responses={202: OpenApiResponse(response=DocumentSerializer)},
    )
    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None, company_pk=None):
        doc = self.get_object()
        doc.status = DocumentStatus.PROCESSING
        doc.error_message = ""
        doc.save(update_fields=["status", "error_message", "updated_at"])
        # trigger_processing runs the pipeline INLINE (synchronous, in this
        # request thread) when DOCUMENT_PROCESSOR_JOB is unset — dev/local
        # convenience. In prod it fires a Kubernetes Job and returns immediately.
        # If dispatch itself fails (e.g. the control plane is unreachable), mark
        # the row failed with a generic message — never leak the raw exception —
        # so the client stops polling a doc that will never progress.
        try:
            trigger_processing(doc)
        except Exception:
            logger.exception("Document %s processing dispatch failed", doc.pk)
            Document.objects.filter(pk=doc.pk).update(
                status=DocumentStatus.FAILED,
                error_message=_GENERIC_DISPATCH_ERROR,
                updated_at=timezone.now(),
            )
        doc.refresh_from_db()
        return Response(self.get_serializer(doc).data, status=status.HTTP_202_ACCEPTED)

    @extend_schema(
        request=None,
        responses=inline_serializer(
            name="DocumentViewUrl",
            fields={"url": serializers.URLField()},
        ),
    )
    @action(detail=True, methods=["get"], url_path="view-url")
    def view_url(self, request, pk=None, company_pk=None):
        """Signed GET URL so the browser can open the stored PDF (spec §5.3)."""
        doc = self.get_object()
        if not gcs.is_configured():
            return Response(
                {"detail": "Document viewing is not configured in this environment."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        if not doc.storage_path:
            return Response(
                {"detail": "Document has no stored file."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response({"url": gcs.signed_get_url(doc.storage_path)})

    def perform_destroy(self, instance):
        if instance.storage_path and gcs.is_configured():
            gcs.delete_object(instance.storage_path)
        instance.delete()
