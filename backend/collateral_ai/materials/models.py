from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from collateral_ai.materials.statuses import GenerationStatus
from collateral_ai.materials.statuses import ReviewStatus
from collateral_ai.materials.statuses import SourceRole

DEFAULT_TEMPLATE_SLUG = "newsletter_article_v1"


class Template(models.Model):
    """A publishing layout: the fixed newsletter contract parameterized by constraints.

    There is no schema_json — the structured-output schema is built in code and
    parameterized by `constraints` / `image_slots` (spec §3.1).
    """

    name = models.CharField(_("name"), max_length=255)
    slug = models.SlugField(_("slug"), max_length=255, unique=True, blank=True)
    description = models.TextField(_("description"), blank=True)
    # {headline_max_words, subheadline_max_words, body_section_count,
    #  body_section_max_words, cta_max_words}
    constraints = models.JSONField(_("constraints"), default=dict)
    # [{slot_id, label, spec, source}] — source ∈ sender|receiver|generated_placeholder
    image_slots = models.JSONField(_("image slots"), default=list)
    # {primary_color, accent_color} hex strings
    theme = models.JSONField(_("theme"), default=dict)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("template")
        verbose_name_plural = _("templates")
        # Oldest first: the seeded default is always first, the wizard pre-selects it.
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"{self.name} ({self.slug})"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._unique_slug(self.name)
        super().save(*args, **kwargs)

    @staticmethod
    def _unique_slug(name: str) -> str:
        base = slugify(name).replace("-", "_") or "template"
        slug = base
        n = 2
        while Template.objects.filter(slug=slug).exists():
            slug = f"{base}_{n}"
            n += 1
        return slug


class MarketingMaterial(models.Model):
    """A generation request + its result, targeted sender → receiver."""

    title = models.CharField(_("title"), max_length=255)
    description = models.TextField(_("description"), blank=True)
    sender_company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="materials_as_sender",
    )
    receiver_company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="materials_as_receiver",
    )
    template = models.ForeignKey(
        Template,
        on_delete=models.PROTECT,
        related_name="materials",
    )
    prompt = models.TextField(_("prompt"))
    tone = models.CharField(_("tone"), max_length=32, default="professional")
    cta_style = models.CharField(_("cta style"), max_length=32, default="soft")
    cta_link = models.URLField(_("cta link"), blank=True, default="")
    language = models.CharField(_("language"), max_length=32, default="english")
    generation_status = models.CharField(
        _("generation status"),
        max_length=16,
        choices=GenerationStatus.CHOICES,
        default=GenerationStatus.QUEUED,
    )
    review_status = models.CharField(
        _("review status"),
        max_length=16,
        choices=ReviewStatus.CHOICES,
        default=ReviewStatus.PENDING,
    )
    output_json = models.JSONField(null=True, blank=True)
    validation_result = models.JSONField(null=True, blank=True)
    retrieved_context = models.JSONField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    job_operation_name = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = _("marketing material")
        verbose_name_plural = _("marketing materials")
        ordering = ["-created_at"]
        # FK columns are auto-indexed; generation_status powers list filters.
        indexes = [models.Index(fields=["generation_status"])]

    def __str__(self) -> str:
        return f"{self.title} ({self.generation_status}/{self.review_status})"


class GenerationSource(models.Model):
    """A retrieved chunk the LLM cited — the rows behind the Sources tab."""

    material = models.ForeignKey(
        MarketingMaterial,
        on_delete=models.CASCADE,
        related_name="sources",
    )
    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="generation_sources",
    )
    document = models.ForeignKey(
        "documents.Document",
        on_delete=models.CASCADE,
        related_name="generation_sources",
    )
    # Worker 1 deletes + recreates chunks on document reprocess, so this may dangle;
    # page_number/snippet are denormalized for exactly that reason (spec §3.3).
    chunk = models.ForeignKey(
        "documents.DocumentChunk",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="generation_sources",
    )
    source_role = models.CharField(
        max_length=16,
        choices=SourceRole.CHOICES,
    )
    page_number = models.PositiveIntegerField(null=True, blank=True)
    snippet = models.TextField(blank=True)
    used_fact = models.CharField(max_length=1000, blank=True)
    relevance_score = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("generation source")
        verbose_name_plural = _("generation sources")
        ordering = ["material_id", "id"]

    def __str__(self) -> str:
        return f"material={self.material_id} {self.source_role} doc={self.document_id}"
