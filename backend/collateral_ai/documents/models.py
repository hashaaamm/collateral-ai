from django.db import models
from django.utils.translation import gettext_lazy as _
from pgvector.django import VectorField

from collateral_ai.documents.statuses import DocumentStatus


class Document(models.Model):
    """A PDF uploaded to a company's knowledge base."""

    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="documents",
    )
    file_name = models.CharField(_("file name"), max_length=255)
    storage_path = models.CharField(
        _("storage object path"),
        max_length=512,
        blank=True,
    )
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
    summary = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("document")
        verbose_name_plural = _("documents")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.file_name} ({self.status})"


class DocumentChunk(models.Model):
    """One embedded chunk of a processed document (text, table, or image caption)."""

    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name="chunks",
    )
    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="document_chunks",
    )
    chunk_type = models.CharField(_("chunk type"), max_length=32)
    page_number = models.PositiveIntegerField()
    content = models.TextField()
    embedding = VectorField(dimensions=768)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("document chunk")
        verbose_name_plural = _("document chunks")
        ordering = ["document_id", "page_number", "id"]

    def __str__(self) -> str:
        return f"{self.document_id} p{self.page_number} {self.chunk_type}"
