from __future__ import annotations

import re

from rest_framework import serializers

from collateral_ai.materials.models import Template

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
