from django.db import migrations

DEFAULT_CONSTRAINTS = {
    "headline_max_words": 10,
    "subheadline_max_words": 22,
    "body_section_count": 2,
    "body_section_max_words": 80,
    "cta_max_words": 15,
}
DEFAULT_IMAGE_SLOTS = [
    {
        "slot_id": "hero_image",
        "label": "Hero image",
        "spec": "1200×630",
        "source": "generated_placeholder",
    },
    {
        "slot_id": "sender_logo",
        "label": "Sender logo",
        "spec": "SVG/PNG",
        "source": "sender",
    },
]
DEFAULT_THEME = {"primary_color": "#5b5bd6", "accent_color": "#0f172a"}


def seed(apps, schema_editor):
    template = apps.get_model("materials", "Template")
    template.objects.get_or_create(
        slug="newsletter_article_v1",
        defaults={
            "name": "Newsletter Article",
            "description": "Short tailored B2B newsletter article.",
            "constraints": DEFAULT_CONSTRAINTS,
            "image_slots": DEFAULT_IMAGE_SLOTS,
            "theme": DEFAULT_THEME,
        },
    )


def unseed(apps, schema_editor):
    template = apps.get_model("materials", "Template")
    template.objects.filter(slug="newsletter_article_v1").delete()


class Migration(migrations.Migration):
    dependencies = [("materials", "0001_initial")]
    operations = [migrations.RunPython(seed, unseed)]
