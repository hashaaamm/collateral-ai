"""Project-wide DRF exception handler.

DomainError (raised by app services) → {"detail": ...} with the error's
status code; everything else defers to DRF's default handler.
"""

from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from collateral_ai.core.exceptions import DomainError


def api_exception_handler(exc, context):
    if isinstance(exc, DomainError):
        return Response({"detail": exc.detail}, status=exc.status_code)
    return drf_exception_handler(exc, context)
