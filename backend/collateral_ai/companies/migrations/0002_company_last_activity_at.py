import django.utils.timezone
from django.db import migrations
from django.db import models
from django.db.models import Max


def backfill_last_activity(apps, schema_editor):
    Company = apps.get_model("companies", "Company")
    companies = Company.objects.annotate(_latest_doc=Max("documents__created_at"))
    for company in companies.iterator():
        latest_doc = company._latest_doc
        if latest_doc is None:
            value = company.created_at
        else:
            value = max(company.created_at, latest_doc)
        Company.objects.filter(pk=company.pk).update(last_activity_at=value)


class Migration(migrations.Migration):

    dependencies = [
        ("companies", "0001_initial"),
        ("documents", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="company",
            name="last_activity_at",
            field=models.DateTimeField(
                auto_now=True,
                default=django.utils.timezone.now,
            ),
            preserve_default=False,
        ),
        migrations.RunPython(
            backfill_last_activity,
            migrations.RunPython.noop,
        ),
    ]
