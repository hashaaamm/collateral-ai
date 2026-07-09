from rest_framework.mixins import CreateModelMixin
from rest_framework.mixins import ListModelMixin
from rest_framework.mixins import RetrieveModelMixin
from rest_framework.viewsets import GenericViewSet

from collateral_ai.materials.models import Template

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
