from django.db.models.signals import post_save
from django.dispatch import receiver

from collateral_ai.companies.models import Company
from collateral_ai.documents.models import Document


@receiver(post_save, sender=Document)
def bump_company_last_activity(sender, instance, created, **kwargs):
    """Mark a document's company as recently active when the document is added."""
    if not created:
        return
    Company.objects.filter(pk=instance.company_id).update(
        last_activity_at=instance.created_at,
    )
