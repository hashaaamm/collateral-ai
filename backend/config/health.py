"""Health-check view (plugin delta over cookiecutter-django).

Cloud Run's startup/liveness probes and the plugin smoke-test hit
``GET /health/`` and expect ``200 {"status": "ok"}``. This view is intentionally
dependency-free: no authentication, no database access, no template rendering,
so it succeeds even before migrations run or while the DB is unreachable.

Copy this file into the generated project at ``config/health.py`` (the
scaffolder does this when applying deltas) and wire it up via
``deltas/urls-health.snippet.py``.
"""

from django.http import HttpRequest
from django.http import JsonResponse


def health(_request: HttpRequest) -> JsonResponse:
    """Return a static liveness payload with no side effects."""
    return JsonResponse({"status": "ok"})
