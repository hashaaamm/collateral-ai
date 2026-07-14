"""Project-wide DRF exception handler.

DomainError (raised by app services) → {"detail": ...} with the error's
status code; everything else defers to DRF's default handler.
"""

from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler
from rest_framework.views import set_rollback

from collateral_ai.core.exceptions import DomainError


def api_exception_handler(exc, context):
    if isinstance(exc, DomainError):
        # Match DRF's default-handler semantics: an error response under
        # ATOMIC_REQUESTS must roll back the request transaction.
        set_rollback()
        return Response({"detail": exc.detail}, status=exc.status_code)
    return drf_exception_handler(exc, context)
