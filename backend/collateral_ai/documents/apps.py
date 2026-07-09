from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class DocumentsConfig(AppConfig):
    name = "collateral_ai.documents"
    verbose_name = _("Documents")

    def ready(self):
        # Signal registration must happen inside ready() (Django app-loading
        # contract), so the local import is deliberate.
        from collateral_ai.documents import signals  # noqa: F401, PLC0415
