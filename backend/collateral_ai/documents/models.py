from django.db import models
from django.utils.translation import gettext_lazy as _

from collateral_ai.documents.statuses import DocumentStatus


class Document(models.Model):
    """A PDF uploaded to a company's knowledge base."""

    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="documents",
    )
    file_name = models.CharField(_("file name"), max_length=255)
    storage_path = models.CharField(_("storage object path"), max_length=512, blank=True)
    content_type = models.CharField(_("content type"), max_length=100)
    status = models.CharField(
        _("status"),
        max_length=32,
        choices=DocumentStatus.CHOICES,
        default=DocumentStatus.PENDING,
    )
    page_count = models.PositiveIntegerField(null=True, blank=True)
    chunks_count = models.PositiveIntegerField(default=0)
    tables_count = models.PositiveIntegerField(default=0)
    images_count = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("document")
        verbose_name_plural = _("documents")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.file_name} ({self.status})"
