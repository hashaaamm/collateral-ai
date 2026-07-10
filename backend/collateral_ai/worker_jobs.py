"""Create Kubernetes Jobs on GKE Autopilot for the async workers.

Auth uses Application Default Credentials (the Cloud Run runtime SA) as a bearer
token against the injected control-plane endpoint + CA cert — no kubeconfig on
disk. Secrets are passed as literal env forwarded from the backend's own
environment (see the spec's security note).
"""

from __future__ import annotations

import base64
import os
import tempfile
from functools import cache

from django.conf import settings

# GKE returns 409 Conflict when the namespace/KSA already exist — treated as success.
_HTTP_CONFLICT = 409

# Env var names the backend forwards verbatim into the worker pod. DATABASE_URL is
# handled separately (the pod needs the private-IP form, not the unix-socket form).
_FORWARDED_ENV = (
    "DJANGO_SETTINGS_MODULE",
    "DJANGO_ALLOWED_HOSTS",
    "DJANGO_ADMIN_URL",
    "DJANGO_GCP_STORAGE_BUCKET_NAME",
    "GOOGLE_CLOUD_PROJECT",
    "VERTEX_LOCATION",
    "DJANGO_SECRET_KEY",
)


def _api_client():
    """Build an authenticated Kubernetes ApiClient for the GKE control plane.

    Uses Application Default Credentials (the Cloud Run runtime SA) as a bearer
    token against the injected endpoint + CA cert — no kubeconfig on disk. The
    backend reaches the control plane privately through the VPC connector, so the
    cluster needs no public endpoint.
    """
    import google.auth  # noqa: PLC0415
    import google.auth.transport.requests  # noqa: PLC0415
    from kubernetes import client  # noqa: PLC0415

    creds, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    creds.refresh(google.auth.transport.requests.Request())

    ca_file = tempfile.NamedTemporaryFile(suffix=".crt", delete=False)  # noqa: SIM115
    ca_file.write(base64.b64decode(settings.GKE_CA_CERT))
    ca_file.flush()

    cfg = client.Configuration()
    cfg.host = settings.GKE_ENDPOINT
    cfg.ssl_ca_cert = ca_file.name
    cfg.api_key = {"authorization": f"Bearer {creds.token}"}
    return client.ApiClient(cfg)


def _batch_api():
    from kubernetes import client  # noqa: PLC0415

    return client.BatchV1Api(_api_client())


# @cache makes this run once per process: after the first success the namespace/KSA
# exist, so we skip the two extra control-plane calls on later job submissions. A raised
# exception is not cached, so a transient failure is retried on the next submission.
@cache
def ensure_worker_namespace() -> None:
    """Idempotently create the workers namespace + Workload-Identity KSA.

    Runs from the backend (inside the VPC, private control-plane endpoint) so
    Pulumi never needs cluster API access and the control plane stays fully
    private. Safe to call repeatedly: 409 (already exists) is ignored.
    """
    from kubernetes import client  # noqa: PLC0415
    from kubernetes.client.rest import ApiException  # noqa: PLC0415

    api = client.CoreV1Api(_api_client())
    namespace = settings.WORKER_NAMESPACE
    gsa = settings.WORKER_GCP_SERVICE_ACCOUNT

    try:
        api.create_namespace(
            client.V1Namespace(metadata=client.V1ObjectMeta(name=namespace)),
        )
    except ApiException as exc:
        if exc.status != _HTTP_CONFLICT:
            raise

    ksa = client.V1ServiceAccount(
        metadata=client.V1ObjectMeta(
            name=settings.WORKER_SERVICE_ACCOUNT,
            annotations={"iam.gke.io/gcp-service-account": gsa},
        ),
    )
    try:
        api.create_namespaced_service_account(namespace=namespace, body=ksa)
    except ApiException as exc:
        if exc.status != _HTTP_CONFLICT:
            raise


def _worker_env():
    from kubernetes import client  # noqa: PLC0415

    env = [
        client.V1EnvVar(name=name, value=os.environ[name])
        for name in _FORWARDED_ENV
        if os.environ.get(name)
    ]
    env.append(client.V1EnvVar(name="DATABASE_URL", value=settings.WORKER_DATABASE_URL))
    return env


def create_worker_job(  # noqa: PLR0913
    name_prefix: str,
    args: list[str],
    *,
    backoff_limit: int,
    active_deadline_seconds: int,
    cpu: str,
    memory: str,
) -> str:
    """Submit a one-off K8s Job on the backend image; return the created Job name."""
    from kubernetes import client  # noqa: PLC0415

    ensure_worker_namespace()

    resources = client.V1ResourceRequirements(
        requests={"cpu": cpu, "memory": memory},
        limits={"cpu": cpu, "memory": memory},
    )
    container = client.V1Container(
        name="worker",
        image=settings.WORKER_IMAGE,
        command=["python"],
        args=args,
        env=_worker_env(),
        resources=resources,
    )
    pod_spec = client.V1PodSpec(
        restart_policy="Never",
        service_account_name=settings.WORKER_SERVICE_ACCOUNT,
        containers=[container],
    )
    job = client.V1Job(
        metadata=client.V1ObjectMeta(generate_name=f"{name_prefix}-"),
        spec=client.V1JobSpec(
            backoff_limit=backoff_limit,
            active_deadline_seconds=active_deadline_seconds,
            ttl_seconds_after_finished=3600,
            template=client.V1PodTemplateSpec(spec=pod_spec),
        ),
    )
    created = _batch_api().create_namespaced_job(
        namespace=settings.WORKER_NAMESPACE,
        body=job,
    )
    return created.metadata.name or ""
