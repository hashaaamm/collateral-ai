from rest_framework import serializers

from collateral_ai.documents.models import Document


class DocumentSerializer(serializers.ModelSerializer[Document]):
    class Meta:
        model = Document
        fields = [
            "id",
            "company",
            "file_name",
            "content_type",
            "status",
            "page_count",
            "chunks_count",
            "tables_count",
            "images_count",
            "error_message",
            "created_at",
        ]
        # `company` is set from the URL, never the request body.
        read_only_fields = [
            "id",
            "company",
            "status",
            "page_count",
            "chunks_count",
            "tables_count",
            "images_count",
            "error_message",
            "created_at",
        ]
