from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiResponse
from drf_spectacular.utils import extend_schema
from rest_framework import filters
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.mixins import CreateModelMixin
from rest_framework.mixins import DestroyModelMixin
from rest_framework.mixins import ListModelMixin
from rest_framework.mixins import RetrieveModelMixin
from rest_framework.mixins import UpdateModelMixin
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from collateral_ai.materials import services
from collateral_ai.materials.models import MarketingMaterial
from collateral_ai.materials.models import Template

from .filters import MaterialFilter
from .serializers import MaterialCreateSerializer
from .serializers import MaterialDetailSerializer
from .serializers import MaterialListSerializer
from .serializers import MaterialRegenerateSerializer
from .serializers import MaterialUpdateSerializer
from .serializers import TemplateSerializer


class TemplateViewSet(
    ListModelMixin,
    RetrieveModelMixin,
    CreateModelMixin,
    GenericViewSet,
):
    """Templates are create-only in MVP: no update/delete (spec §5.1)."""

    serializer_class = TemplateSerializer
    queryset = Template.objects.all()


class MaterialViewSet(
    ListModelMixin,
    RetrieveModelMixin,
    CreateModelMixin,
    UpdateModelMixin,
    DestroyModelMixin,
    GenericViewSet,
):
    queryset = MarketingMaterial.objects.select_related(
        "sender_company",
        "receiver_company",
        "template",
    ).all()
    serializer_class = MaterialDetailSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_class = MaterialFilter
    search_fields = ["title"]

    def get_serializer_class(self):
        if self.action == "list":
            return MaterialListSerializer
        if self.action == "create":
            return MaterialCreateSerializer
        if self.action in {"update", "partial_update"}:
            return MaterialUpdateSerializer
        return MaterialDetailSerializer

    @extend_schema(
        request=MaterialCreateSerializer,
        responses={201: MaterialDetailSerializer},
    )
    def create(self, request, *args, **kwargs):
        # Overridden only to render the detail shape at 201 (wire contract);
        # creation itself runs through the serializer → services.create_material.
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        material = serializer.save()
        return Response(
            MaterialDetailSerializer(material, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        request=MaterialRegenerateSerializer,
        responses={
            202: MaterialDetailSerializer,
            409: OpenApiResponse(description="Generation already in progress"),
        },
    )
    @action(detail=True, methods=["post"])
    def regenerate(self, request, pk=None):
        # get_object() first so DRF's 404/permission checks still apply.
        material = self.get_object()
        body = MaterialRegenerateSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        material = services.regenerate_material(
            material,
            prompt=body.validated_data.get("prompt"),
        )
        return Response(
            MaterialDetailSerializer(material, context={"request": request}).data,
            status=status.HTTP_202_ACCEPTED,
        )
