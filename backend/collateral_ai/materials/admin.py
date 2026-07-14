from django.contrib import admin

from .models import GenerationSource
from .models import MarketingMaterial
from .models import Template


@admin.register(Template)
class TemplateAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "is_active", "created_at"]
    list_filter = ["is_active"]
    search_fields = ["name", "slug", "description"]
    prepopulated_fields = {"slug": ["name"]}
    readonly_fields = ["created_at", "updated_at"]


@admin.register(MarketingMaterial)
class MarketingMaterialAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "sender_company",
        "receiver_company",
        "generation_status",
        "review_status",
        "created_at",
    ]
    list_filter = ["generation_status", "review_status", "language"]
    search_fields = ["title", "description", "prompt"]
    raw_id_fields = ["sender_company", "receiver_company", "template"]
    readonly_fields = ["created_at", "updated_at", "completed_at"]
    date_hierarchy = "created_at"


@admin.register(GenerationSource)
class GenerationSourceAdmin(admin.ModelAdmin):
    list_display = [
        "material",
        "company",
        "document",
        "source_role",
        "page_number",
        "relevance_score",
    ]
    list_filter = ["source_role"]
    search_fields = ["snippet", "used_fact"]
    raw_id_fields = ["material", "company", "document", "chunk"]
    readonly_fields = ["created_at"]
