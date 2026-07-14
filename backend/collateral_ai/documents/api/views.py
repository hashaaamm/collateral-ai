from drf_spectacular.utils import OpenApiResponse
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.mixins import CreateModelMixin
from rest_framework.mixins import DestroyModelMixin
from rest_framework.mixins import ListModelMixin
from rest_framework.mixins import RetrieveModelMixin
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from collateral_ai.documents import services
from collateral_ai.documents.models import Document

from .serializers import DocumentCreateSerializer
from .serializers import DocumentSerializer
from .serializers import DocumentViewUrlSerializer
from .serializers import DocumentWithUploadUrlSerializer


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
        request=DocumentCreateSerializer,
        responses={201: DocumentWithUploadUrlSerializer},
    )
    def create(self, request, *args, **kwargs):
        body = DocumentCreateSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        doc, upload_url = services.create_document_with_upload_url(
            company_id=int(self.kwargs["company_pk"]),
            **body.validated_data,
        )
        doc.upload_url = upload_url  # non-model field consumed by the serializer
        return Response(
            DocumentWithUploadUrlSerializer(doc).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        request=None,
        responses={202: OpenApiResponse(response=DocumentSerializer)},
    )
    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None, company_pk=None):
        doc = services.start_processing(self.get_object())
        return Response(self.get_serializer(doc).data, status=status.HTTP_202_ACCEPTED)

    @extend_schema(request=None, responses=DocumentViewUrlSerializer)
    @action(detail=True, methods=["get"], url_path="view-url")
    def view_url(self, request, pk=None, company_pk=None):
        """Signed GET URL so the browser can open the stored PDF (spec §5.3)."""
        url = services.get_view_url(self.get_object())
        return Response(DocumentViewUrlSerializer({"url": url}).data)

    def perform_destroy(self, instance):
        services.delete_document(instance)
