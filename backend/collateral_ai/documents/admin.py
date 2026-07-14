from django.contrib import admin

from .models import Document
from .models import DocumentChunk


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = [
        "file_name",
        "company",
        "status",
        "page_count",
        "chunks_count",
        "created_at",
    ]
    list_filter = ["status", "content_type"]
    search_fields = ["file_name", "storage_path"]
    raw_id_fields = ["company"]
    readonly_fields = ["created_at", "updated_at"]
    date_hierarchy = "created_at"


@admin.register(DocumentChunk)
class DocumentChunkAdmin(admin.ModelAdmin):
    list_display = [
        "document",
        "company",
        "chunk_type",
        "page_number",
        "created_at",
    ]
    list_filter = ["chunk_type"]
    search_fields = ["content"]
    raw_id_fields = ["document", "company"]
    # The 768-d embedding vector is not meaningfully editable in the admin.
    exclude = ["embedding"]
    readonly_fields = ["created_at"]
