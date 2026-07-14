from __future__ import annotations

import re

from rest_framework import serializers

from collateral_ai.companies import gcs as companies_gcs
from collateral_ai.companies.models import Company
from collateral_ai.documents.models import Document
from collateral_ai.documents.statuses import DocumentStatus
from collateral_ai.materials import services
from collateral_ai.materials.models import GenerationSource
from collateral_ai.materials.models import MarketingMaterial
from collateral_ai.materials.models import Template
from collateral_ai.materials.statuses import GenerationStatus

# (min, max) for each required constraint key — spec §5.1.
CONSTRAINT_BOUNDS: dict[str, tuple[int, int]] = {
    "headline_max_words": (1, 60),
    "subheadline_max_words": (1, 60),
    "body_section_count": (1, 10),
    "body_section_max_words": (1, 300),
    "cta_max_words": (1, 60),
}
SLOT_SOURCES = {"sender", "receiver", "generated_placeholder"}
SLOT_ID_RE = re.compile(r"^[a-z0-9_]+$")
HEX_COLOR_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
MAX_IMAGE_SLOTS = 8


class TemplateSerializer(serializers.ModelSerializer[Template]):
    class Meta:
        model = Template
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "constraints",
            "image_slots",
            "theme",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["id", "slug", "is_active", "created_at"]

    def validate_constraints(self, value: dict) -> dict:
        if not isinstance(value, dict):
            msg = "constraints must be an object."
            raise serializers.ValidationError(msg)
        for key, (lo, hi) in CONSTRAINT_BOUNDS.items():
            v = value.get(key)
            if not isinstance(v, int) or isinstance(v, bool) or not lo <= v <= hi:
                msg = f"constraints.{key} must be an integer between {lo} and {hi}."
                raise serializers.ValidationError(msg)
        extra = set(value) - set(CONSTRAINT_BOUNDS)
        if extra:
            msg = f"Unknown constraint keys: {sorted(extra)}"
            raise serializers.ValidationError(msg)
        return value

    def validate_image_slots(self, value: list) -> list:
        if not isinstance(value, list) or len(value) > MAX_IMAGE_SLOTS:
            msg = f"image_slots must be a list of at most {MAX_IMAGE_SLOTS} slots."
            raise serializers.ValidationError(msg)
        seen: set[str] = set()
        for slot in value:
            if not isinstance(slot, dict):
                msg = "Each image slot must be an object."
                raise serializers.ValidationError(msg)
            slot_id = slot.get("slot_id", "")
            if not isinstance(slot_id, str) or not SLOT_ID_RE.match(slot_id):
                msg = f"Invalid slot_id: {slot_id!r} (lowercase letters, digits, _)."
                raise serializers.ValidationError(msg)
            if slot_id in seen:
                msg = f"Duplicate slot_id: {slot_id}"
                raise serializers.ValidationError(msg)
            seen.add(slot_id)
            if slot.get("source") not in SLOT_SOURCES:
                msg = f"slot {slot_id}: source must be one of {sorted(SLOT_SOURCES)}."
                raise serializers.ValidationError(msg)
            if not isinstance(slot.get("label", ""), str) or not slot.get("label"):
                msg = f"slot {slot_id}: label is required."
                raise serializers.ValidationError(msg)
            if not isinstance(slot.get("spec", ""), str):
                msg = f"slot {slot_id}: spec must be a string."
                raise serializers.ValidationError(msg)
        return value

    def validate_theme(self, value: dict) -> dict:
        if not isinstance(value, dict):
            msg = "theme must be an object."
            raise serializers.ValidationError(msg)
        for key in ("primary_color", "accent_color"):
            if not HEX_COLOR_RE.match(str(value.get(key, ""))):
                msg = f"theme.{key} must be a hex color like #5b5bd6."
                raise serializers.ValidationError(msg)
        return value


class CompanySummarySerializer(serializers.ModelSerializer[Company]):
    logo_url = serializers.SerializerMethodField()

    class Meta:
        model = Company
        fields = ["id", "name", "logo_url"]

    def get_logo_url(self, obj: Company) -> str | None:
        if obj.logo and companies_gcs.is_configured():
            return companies_gcs.signed_get_url(obj.logo)
        return None


class SourceDocumentSerializer(serializers.ModelSerializer[Document]):
    class Meta:
        model = Document
        fields = ["id", "file_name", "company"]


class GenerationSourceSerializer(serializers.ModelSerializer[GenerationSource]):
    document = SourceDocumentSerializer(read_only=True)

    class Meta:
        model = GenerationSource
        fields = [
            "id",
            "source_role",
            "page_number",
            "snippet",
            "used_fact",
            "relevance_score",
            "document",
        ]


class MaterialListSerializer(serializers.ModelSerializer[MarketingMaterial]):
    sender_company = CompanySummarySerializer(read_only=True)
    receiver_company = CompanySummarySerializer(read_only=True)
    template_slug = serializers.CharField(source="template.slug", read_only=True)

    class Meta:
        model = MarketingMaterial
        fields = [
            "id",
            "title",
            "sender_company",
            "receiver_company",
            "template_slug",
            "generation_status",
            "review_status",
            "created_at",
            "completed_at",
        ]


class MaterialDetailSerializer(MaterialListSerializer):
    template = TemplateSerializer(read_only=True)
    sources = GenerationSourceSerializer(many=True, read_only=True)

    class Meta(MaterialListSerializer.Meta):
        fields = [
            *MaterialListSerializer.Meta.fields,
            "description",
            "prompt",
            "tone",
            "cta_style",
            "cta_link",
            "language",
            "template",
            "output_json",
            "validation_result",
            "error_message",
            "updated_at",
            "sources",
        ]


class MaterialCreateSerializer(serializers.ModelSerializer[MarketingMaterial]):
    class Meta:
        model = MarketingMaterial
        fields = [
            "id",
            "title",
            "description",
            "sender_company",
            "receiver_company",
            "template",
            "prompt",
            "tone",
            "cta_style",
            "cta_link",
            "language",
        ]
        read_only_fields = ["id"]

    def validate(self, attrs: dict) -> dict:
        sender = attrs["sender_company"]
        receiver = attrs["receiver_company"]
        if sender == receiver:
            msg = "Sender and receiver must be different companies."
            raise serializers.ValidationError({"receiver_company": msg})
        if not attrs["template"].is_active:
            msg = "This template is not active."
            raise serializers.ValidationError({"template": msg})
        for field, company in (
            ("sender_company", sender),
            ("receiver_company", receiver),
        ):
            has_docs = Document.objects.filter(
                company=company,
                status=DocumentStatus.PROCESSED,
            ).exists()
            if not has_docs:
                msg = (
                    f"{company.name} has no processed documents — upload and "
                    "process documents before generating."
                )
                raise serializers.ValidationError({field: msg})
        return attrs

    def create(self, validated_data: dict) -> MarketingMaterial:
        return services.create_material(**validated_data)


class MaterialUpdateSerializer(serializers.ModelSerializer[MarketingMaterial]):
    class Meta:
        model = MarketingMaterial
        fields = ["id", "title", "description", "prompt", "cta_link", "review_status"]
        read_only_fields = ["id"]

    def validate_review_status(self, value: str) -> str:
        if (
            self.instance is not None
            and self.instance.generation_status != GenerationStatus.COMPLETED
        ):
            msg = "Review status can only change once generation is completed."
            raise serializers.ValidationError(msg)
        return value


class MaterialRegenerateSerializer(serializers.Serializer):
    """Body for the ``regenerate`` action.

    ``prompt`` is optional: omit it to re-run with the stored prompt, or pass a
    new one to edit-and-regenerate in a single request (no separate PATCH).
    """

    prompt = serializers.CharField(required=False, allow_blank=False)
