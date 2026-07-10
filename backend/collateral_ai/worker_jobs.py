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

from django.conf import settings

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


def _batch_api():
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
    return client.BatchV1Api(client.ApiClient(cfg))


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
