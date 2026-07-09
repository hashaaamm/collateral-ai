from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

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
