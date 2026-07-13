import datetime
import logging

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter
from drf_spectacular.utils import OpenApiResponse
from drf_spectacular.utils import extend_schema
from drf_spectacular.utils import extend_schema_view
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

from collateral_ai.materials.models import MarketingMaterial
from collateral_ai.materials.models import Template
from collateral_ai.materials.statuses import GenerationStatus
from collateral_ai.materials.statuses import ReviewStatus
from collateral_ai.materials.worker_trigger import trigger_generation

from .serializers import MaterialCreateSerializer
from .serializers import MaterialDetailSerializer
from .serializers import MaterialListSerializer
from .serializers import MaterialUpdateSerializer
from .serializers import TemplateSerializer

logger = logging.getLogger(__name__)

# User-facing failure text. The real exception (which may leak infra details
# like internal hostnames) is logged server-side, never surfaced to the client.
_GENERIC_DISPATCH_ERROR = "Generation could not be started. Please try again."

# A queued/processing row older than this is considered stranded (crashed job)
# and may be regenerated (spec §5.2). Comfortably above the 600s job timeout.
STALE_AFTER = datetime.timedelta(minutes=15)

LIST_FILTER_PARAMS = [
    OpenApiParameter("company", int, description="Sender OR receiver company id"),
    OpenApiParameter("sender", int),
    OpenApiParameter("receiver", int),
    OpenApiParameter("generation_status", str),
    OpenApiParameter("review_status", str),
]


def _int_param(value: str | None) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


class TemplateViewSet(
    ListModelMixin,
    RetrieveModelMixin,
    CreateModelMixin,
    GenericViewSet,
):
    """Templates are create-only in MVP: no update/delete (spec §5.1)."""

    serializer_class = TemplateSerializer
    queryset = Template.objects.all()


@extend_schema_view(list=extend_schema(parameters=LIST_FILTER_PARAMS))
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
    filter_backends = [filters.SearchFilter]
    search_fields = ["title"]

    def get_serializer_class(self):
        if self.action == "list":
            return MaterialListSerializer
        if self.action == "create":
            return MaterialCreateSerializer
        if self.action in {"update", "partial_update"}:
            return MaterialUpdateSerializer
        return MaterialDetailSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        if (company := _int_param(params.get("company"))) is not None:
            qs = qs.filter(
                Q(sender_company_id=company) | Q(receiver_company_id=company),
            )
        if (sender := _int_param(params.get("sender"))) is not None:
            qs = qs.filter(sender_company_id=sender)
        if (receiver := _int_param(params.get("receiver"))) is not None:
            qs = qs.filter(receiver_company_id=receiver)
        if generation_status := params.get("generation_status"):
            qs = qs.filter(generation_status=generation_status)
        if review_status := params.get("review_status"):
            qs = qs.filter(review_status=review_status)
        return qs

    @extend_schema(
        request=MaterialCreateSerializer,
        responses={201: MaterialDetailSerializer},
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        material = serializer.save()
        self._dispatch(material)
        material.refresh_from_db()
        return Response(
            MaterialDetailSerializer(material, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    def _dispatch(self, material) -> None:
        """Trigger the worker inside its own savepoint (spec §5.5).

        The request runs under ATOMIC_REQUESTS; the inner atomic() means a
        failing trigger (or a poisoned inline run) can't take the created row
        down with it — we mark the material failed and still return 201.
        """
        try:
            with transaction.atomic():
                operation_name = trigger_generation(material)
        except Exception:  # any trigger failure → failed row, generic client message
            logger.exception(
                "Material %s generation dispatch failed", material.pk,
            )
            MarketingMaterial.objects.filter(pk=material.pk).update(
                generation_status=GenerationStatus.FAILED,
                error_message=_GENERIC_DISPATCH_ERROR,
                updated_at=timezone.now(),
            )
        else:
            if operation_name:
                MarketingMaterial.objects.filter(pk=material.pk).update(
                    job_operation_name=operation_name,
                    updated_at=timezone.now(),
                )

    @extend_schema(
        request=None,
        responses={
            202: MaterialDetailSerializer,
            409: OpenApiResponse(description="Generation already in progress"),
        },
    )
    @action(detail=True, methods=["post"])
    def regenerate(self, request, pk=None):
        # get_object() first so DRF's 404/permission checks still apply against
        # the unlocked queryset; the locked re-fetch below guards the actual
        # read-modify-write against a concurrent worker completion.
        material = self.get_object()
        with transaction.atomic():
            material = MarketingMaterial.objects.select_for_update().get(
                pk=material.pk,
            )
            is_active = material.generation_status in {
                GenerationStatus.QUEUED,
                GenerationStatus.PROCESSING,
            }
            is_stale = material.updated_at < timezone.now() - STALE_AFTER
            if is_active and not is_stale:
                return Response(
                    {"detail": "Generation is already in progress."},
                    status=status.HTTP_409_CONFLICT,
                )
            material.generation_status = GenerationStatus.QUEUED
            material.review_status = ReviewStatus.PENDING
            material.output_json = None
            material.validation_result = None
            material.retrieved_context = None
            material.error_message = ""
            material.job_operation_name = ""
            material.completed_at = None
            material.save()
            material.sources.all().delete()
        self._dispatch(material)
        material.refresh_from_db()
        return Response(
            MaterialDetailSerializer(material, context={"request": request}).data,
            status=status.HTTP_202_ACCEPTED,
        )
