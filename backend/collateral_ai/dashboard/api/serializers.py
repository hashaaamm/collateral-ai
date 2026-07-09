from rest_framework import serializers


class DashboardStatsSerializer(serializers.Serializer):
    """Read-only aggregate counts for the dashboard stat cards."""

    companies_count = serializers.IntegerField()
    documents_processed = serializers.IntegerField()
    documents_processing = serializers.IntegerField()
