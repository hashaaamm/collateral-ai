from rest_framework import serializers

from collateral_ai.companies import gcs
from collateral_ai.companies.models import Company


class CompanySerializer(serializers.ModelSerializer[Company]):
    logo_url = serializers.SerializerMethodField()
    last_updated = serializers.DateTimeField(
        source="last_activity_at",
        read_only=True,
    )
    # Declared explicitly so the OpenAPI schema types brand_colors as string[]
    # (a bare JSONField would emit a loose type that breaks the typed frontend).
    brand_colors = serializers.ListField(
        child=serializers.CharField(),
        required=False,
    )

    class Meta:
        model = Company
        fields = [
            "id",
            "name",
            "website",
            "industry",
            "description",
            "brand_colors",
            "logo",
            "logo_url",
            "created_at",
            "last_updated",
        ]
        read_only_fields = ["id", "created_at", "last_updated"]
        extra_kwargs = {"logo": {"write_only": True, "required": False}}

    def get_logo_url(self, obj: Company) -> str | None:
        if obj.logo and gcs.is_configured():
            return gcs.signed_get_url(obj.logo)
        return None
