from django.db.models import Q
from django_filters import rest_framework as df

from collateral_ai.materials.models import MarketingMaterial


class MaterialFilter(df.FilterSet):
    """List filters; ``company`` matches sender OR receiver.

    Statuses are CharFilters (not ChoiceFilters) on purpose: an unknown status
    string filters to an empty list, exactly like the pre-django-filter
    behavior, instead of becoming a 400.
    """

    company = df.NumberFilter(
        method="filter_company",
        help_text="Sender OR receiver company id",
    )
    sender = df.NumberFilter(field_name="sender_company_id")
    receiver = df.NumberFilter(field_name="receiver_company_id")
    generation_status = df.CharFilter()
    review_status = df.CharFilter()

    class Meta:
        model = MarketingMaterial
        fields = [
            "company",
            "sender",
            "receiver",
            "generation_status",
            "review_status",
        ]

    def filter_company(self, queryset, name, value):
        return queryset.filter(
            Q(sender_company_id=value) | Q(receiver_company_id=value),
        )
