from django.db import models
from django.utils.translation import gettext_lazy as _


class Company(models.Model):
    """A company profile — reusable context shared across the workspace."""

    name = models.CharField(_("name"), max_length=255)
    website = models.URLField(_("website"), blank=True)
    industry = models.CharField(_("industry"), max_length=120, blank=True)
    description = models.TextField(_("description"), blank=True)
    brand_colors = models.JSONField(_("brand colors"), default=list, blank=True)
    logo = models.CharField(_("logo object path"), max_length=512, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("company")
        verbose_name_plural = _("companies")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.name
