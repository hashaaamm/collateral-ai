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


class DocumentCreateSerializer(serializers.Serializer):
    """Body for reserving an upload: name + type only, no file bytes."""

    file_name = serializers.CharField(max_length=255)  # matches Document.file_name
    content_type = serializers.ChoiceField(choices=["application/pdf"])


class DocumentWithUploadUrlSerializer(DocumentSerializer):
    """201 body for create: the reserved row plus its signed PUT URL."""

    upload_url = serializers.URLField()

    class Meta(DocumentSerializer.Meta):
        fields = [*DocumentSerializer.Meta.fields, "upload_url"]


class DocumentViewUrlSerializer(serializers.Serializer):
    url = serializers.URLField()
