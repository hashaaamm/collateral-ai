from __future__ import annotations

from unittest import mock

from kubernetes import client
from kubernetes.client.rest import ApiException

from collateral_ai import worker_jobs


def test_create_worker_job_builds_manifest(settings, monkeypatch):
    image = "us-central1-docker.pkg.dev/p/collateral-ai-repo/backend:abc123"
    settings.WORKER_IMAGE = image
    settings.WORKER_NAMESPACE = "workers"
    settings.WORKER_SERVICE_ACCOUNT = "worker"
    settings.WORKER_DATABASE_URL = "postgres://u:p@10.1.2.3:5432/db"
    monkeypatch.setenv("DJANGO_SETTINGS_MODULE", "config.settings.production")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "proj")
    monkeypatch.setenv("VERTEX_LOCATION", "us-central1")

    batch = mock.MagicMock()
    batch.create_namespaced_job.return_value.metadata.name = "docproc-xyz"
    monkeypatch.setattr(worker_jobs, "_batch_api", lambda: batch)
    monkeypatch.setattr(worker_jobs, "ensure_worker_namespace", lambda: None)

    name = worker_jobs.create_worker_job(
        name_prefix="collateral-ai-backend-docproc",
        args=["manage.py", "process_document", "--document-id", "7"],
        backoff_limit=1,
        active_deadline_seconds=900,
        cpu="2",
        memory="2Gi",
    )

    assert name == "docproc-xyz"
    call = batch.create_namespaced_job.call_args
    assert call.kwargs["namespace"] == "workers"
    job = call.kwargs["body"]
    assert job.metadata.generate_name == "collateral-ai-backend-docproc-"
    assert job.spec.backoff_limit == 1
    assert job.spec.active_deadline_seconds == 900
    assert job.spec.ttl_seconds_after_finished == 3600
    pod = job.spec.template.spec
    assert pod.restart_policy == "Never"
    assert pod.service_account_name == "worker"
    container = pod.containers[0]
    assert container.image == settings.WORKER_IMAGE
    assert container.command == ["python"]
    assert container.args == ["manage.py", "process_document", "--document-id", "7"]
    assert container.resources.requests == {"cpu": "2", "memory": "2Gi"}
    env = {e.name: e.value for e in container.env}
    assert env["DATABASE_URL"] == "postgres://u:p@10.1.2.3:5432/db"
    assert env["GOOGLE_CLOUD_PROJECT"] == "proj"
    assert env["DJANGO_SETTINGS_MODULE"] == "config.settings.production"


def test_ensure_worker_namespace_is_idempotent(settings, monkeypatch):
    settings.WORKER_NAMESPACE = "workers"
    settings.WORKER_SERVICE_ACCOUNT = "worker"
    settings.WORKER_GCP_SERVICE_ACCOUNT = "gke-worker-sa@proj.iam.gserviceaccount.com"
    worker_jobs.ensure_worker_namespace.cache_clear()

    core = mock.MagicMock()
    # Namespace + KSA already exist -> API raises 409, which must be swallowed.
    core.create_namespace.side_effect = ApiException(status=409)
    core.create_namespaced_service_account.side_effect = ApiException(status=409)
    monkeypatch.setattr(client, "CoreV1Api", mock.Mock(return_value=core))
    monkeypatch.setattr(worker_jobs, "_api_client", mock.Mock())

    worker_jobs.ensure_worker_namespace()
    worker_jobs.ensure_worker_namespace()  # cached: no second control-plane sweep

    core.create_namespace.assert_called_once()
    ksa = core.create_namespaced_service_account.call_args.kwargs["body"]
    assert ksa.metadata.name == "worker"
    assert ksa.metadata.annotations == {
        "iam.gke.io/gcp-service-account": "gke-worker-sa@proj.iam.gserviceaccount.com",
    }
