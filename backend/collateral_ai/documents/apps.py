from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class DocumentsConfig(AppConfig):
    name = "collateral_ai.documents"
    verbose_name = _("Documents")

    def ready(self):
        from collateral_ai.documents import signals  # noqa: F401
