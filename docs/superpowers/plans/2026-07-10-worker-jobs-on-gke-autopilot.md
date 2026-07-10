# Worker Jobs on GKE Autopilot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the two backend-triggered async workers (document processing, material generation) from Cloud Run Jobs to Kubernetes Jobs on a GKE Autopilot cluster, created directly from the Django backend via the Kubernetes API client.

**Architecture:** Pulumi provisions a GKE Autopilot cluster in the existing VPC plus a least-privilege worker service account, a Workload-Identity-annotated K8s ServiceAccount, and a private-IP database secret. The backend (still on Cloud Run) builds a K8s Job manifest at request time and submits it with a GCP bearer token against the injected control-plane endpoint. Worker pods reach Cloud SQL over private IP and Vertex/GCS via Workload Identity.

**Tech Stack:** Pulumi (Python) + `pulumi-gcp` + `pulumi-kubernetes`; Django 6; `kubernetes` + `google-auth` Python clients; GKE Autopilot; GitHub Actions.

## Global Constraints

- Backend stays on Cloud Run; only the two workers move. Migrations job (`jobs.yml`) is untouched.
- No Pub/Sub — the backend calls the Kubernetes API directly.
- Local/dev/test path is unchanged: when the job-name setting is empty, run the management command inline via `call_command`.
- Worker pods connect to Cloud SQL over **private IP + password** (`WORKER_DATABASE_URL`), never the unix-socket `database-url`.
- Secrets are injected as **literal env in the Job pod spec** (accepted in the spec) — no K8s Secret objects, no Secret Manager access from pods.
- Per-worker semantics preserved exactly: docproc `backoffLimit=1`, `activeDeadlineSeconds=900`, `2` CPU / `2Gi`; matgen `backoffLimit=0`, `activeDeadlineSeconds=600`, `1` CPU / `1Gi`. Both `restartPolicy: Never`, `ttlSecondsAfterFinished=3600`.
- Job image = `WORKER_IMAGE` (SHA-pinned, forwarded from the backend's env). Backend + workers always ship together.
- Follow existing repo patterns: Pulumi resource-naming with `NAME`/`SLUG`, `env(...)` settings, pytest + `mock.patch`, `docker compose run --rm django pytest`.
- Spec: `docs/superpowers/specs/2026-07-10-worker-jobs-on-gke-autopilot-design.md`.

---

### Task 1: Pulumi — GKE Autopilot cluster, worker SA, Workload Identity, private-IP secret, IAM

**Files:**
- Modify: `deploy/__main__.py`
- Modify: `deploy/requirements.txt`
- Modify: `deploy/env-template`

**Interfaces:**
- Produces (Pulumi stack outputs consumed by CI in Task 6): `gke_cluster_endpoint` (host, no scheme), `gke_cluster_ca_cert` (base64 PEM), `gke_worker_namespace` (`workers`), `gke_worker_ksa` (`worker`), `gke_worker_sa_email`.
- Produces (in-cluster): namespace `workers`, ServiceAccount `workers/worker` annotated to `gke-worker-sa`.

- [ ] **Step 1: Add the Kubernetes Pulumi provider dependency**

In `deploy/requirements.txt` add:

```
pulumi-kubernetes>=4.18,<5.0.0
```

- [ ] **Step 2: Enable the container API**

In `deploy/__main__.py`, add `"container"` to `REQUIRED_APIS` (the list starting near line 29):

```python
REQUIRED_APIS = [
    "run", "sqladmin", "vpcaccess", "artifactregistry", "secretmanager",
    "compute", "storage", "servicenetworking", "iam", "iamcredentials",
    "aiplatform",  # Vertex AI — document embeddings (gemini-embedding-001)
    "container",   # GKE Autopilot — worker jobs
]
```

- [ ] **Step 3: Add secondary IP ranges to the existing subnet (VPC-native GKE)**

Replace the `subnet` resource (near line 50) with one that carries pod/service secondary ranges GKE needs:

```python
subnet = gcp.compute.Subnetwork(
    f"{NAME}-subnet",
    network=network.id,
    ip_cidr_range=os.environ.get("SUBNET_IP", "10.10.0.0/24"),
    region=REGION,
    secondary_ip_ranges=[
        gcp.compute.SubnetworkSecondaryIpRangeArgs(
            range_name="gke-pods", ip_cidr_range=os.environ.get("GKE_POD_CIDR", "10.20.0.0/16")),
        gcp.compute.SubnetworkSecondaryIpRangeArgs(
            range_name="gke-services", ip_cidr_range=os.environ.get("GKE_SVC_CIDR", "10.30.0.0/20")),
    ],
)
```

- [ ] **Step 4: Add the import and the GKE Autopilot cluster**

Add `import pulumi_kubernetes as k8s` near the other imports (after `import pulumi_random as random`).

Then add the cluster block after the Cloud SQL section (after the `database_url` assignment, before `# --- Secret Manager`):

```python
# --- GKE Autopilot cluster (async worker jobs) ----------------------------
# Autopilot: node pools, VPC-native, and Workload Identity are managed/on by default.
# The backend (Cloud Run) reaches the control plane privately through the VPC connector
# (master_global_access). A restricted public endpoint is kept ONLY so Pulumi/CI can apply
# the namespace + KSA below — set GKE_MASTER_AUTHORIZED_CIDR to your CI/operator egress IP.
GKE_MASTER_AUTHORIZED_CIDR = os.environ.get("GKE_MASTER_AUTHORIZED_CIDR", "").strip()

cluster = gcp.container.Cluster(
    f"{NAME}-autopilot",
    name=f"{NAME}-autopilot",
    location=REGION,
    enable_autopilot=True,
    network=network.id,
    subnetwork=subnet.id,
    ip_allocation_policy=gcp.container.ClusterIpAllocationPolicyArgs(
        cluster_secondary_range_name="gke-pods",
        services_secondary_range_name="gke-services",
    ),
    private_cluster_config=gcp.container.ClusterPrivateClusterConfigArgs(
        enable_private_nodes=True,
        enable_private_endpoint=False,
        master_ipv4_cidr_block=os.environ.get("GKE_MASTER_CIDR", "172.16.0.0/28"),
        master_global_access_config=gcp.container.ClusterPrivateClusterConfigMasterGlobalAccessConfigArgs(
            enabled=True,
        ),
    ),
    master_authorized_networks_config=gcp.container.ClusterMasterAuthorizedNetworksConfigArgs(
        cidr_blocks=(
            [gcp.container.ClusterMasterAuthorizedNetworksConfigCidrBlockArgs(
                cidr_block=GKE_MASTER_AUTHORIZED_CIDR, display_name="operator-ci")]
            if GKE_MASTER_AUTHORIZED_CIDR else []
        ),
    ),
    release_channel=gcp.container.ClusterReleaseChannelArgs(channel="REGULAR"),
    deletion_protection=False,
    opts=pulumi.ResourceOptions(depends_on=[apis["container"], private_vpc_connection]),
)
```

- [ ] **Step 5: Add the worker GCP service account + least-privilege roles**

Add after the cluster block:

```python
worker_sa = gcp.serviceaccount.Account(
    f"{SLUG}-gke-worker-sa", account_id="gke-worker-sa", display_name="GKE worker pods",
)
for role in ["roles/aiplatform.user", "roles/storage.objectAdmin"]:
    gcp.projects.IAMMember(
        f"{SLUG}-worker-{role.split('/')[-1]}",
        project=PROJECT, role=role,
        member=worker_sa.email.apply(lambda e: f"serviceAccount:{e}"),
    )

# Workload Identity: bind the in-cluster KSA workers/worker to the worker GSA.
gcp.serviceaccount.IAMMember(
    f"{SLUG}-worker-wi",
    service_account_id=worker_sa.name,
    role="roles/iam.workloadIdentityUser",
    member=pulumi.Output.concat("serviceAccount:", PROJECT, ".svc.id.goog[workers/worker]"),
)

# Autopilot's node service account (default compute SA) needs to pull the backend image.
default_compute_sa = gcp.compute.get_default_service_account(project=PROJECT)
gcp.artifactregistry.RepositoryIamMember(
    f"{NAME}-node-ar-reader",
    project=PROJECT, location=REGION, repository=repo.repository_id,
    role="roles/artifactregistry.reader",
    member=f"serviceAccount:{default_compute_sa.email}",
)
```

Note: this references `repo`, which is defined lower in the file. Place this whole worker-SA block **after** the Artifact Registry `repo` resource (move it below the `# --- Artifact Registry` section), or split it so the `RepositoryIamMember` sits after `repo`. Simplest: put the entire GKE section (Steps 4–8) **after** the Artifact Registry block.

- [ ] **Step 6: Grant the Cloud Run SA permission to create K8s Jobs**

In the existing `run_sa` roles loop (near line 191), add `"roles/container.developer"`:

```python
for role in ["roles/cloudsql.client", "roles/secretmanager.secretAccessor", "roles/storage.objectAdmin", "roles/aiplatform.user", "roles/run.developer", "roles/container.developer"]:
```

- [ ] **Step 7: Add the private-IP database secret**

After the existing `secrets = {...}` dict (near line 152), add:

```python
database_url_private = pulumi.Output.all(db_password.result, sql_instance.private_ip_address).apply(
    lambda a: f"postgres://{DB_USER}:{a[0]}@{a[1]}:5432/{DB_NAME}"
)
secrets["database-url-private"] = make_secret("database-url-private", database_url_private)
```

- [ ] **Step 8: Create the namespace + Workload-Identity KSA via the Kubernetes provider**

Add after the worker-SA block (Step 5). Pulumi authenticates to the cluster with a short-lived client token:

```python
gke_client_config = gcp.organizations.get_client_config()
gke_kubeconfig = pulumi.Output.all(
    cluster.endpoint, cluster.master_auth.cluster_ca_certificate
).apply(lambda a: f"""apiVersion: v1
kind: Config
clusters:
- name: gke
  cluster:
    server: https://{a[0]}
    certificate-authority-data: {a[1]}
contexts:
- name: gke
  context:
    cluster: gke
    user: gke
current-context: gke
users:
- name: gke
  user:
    token: {gke_client_config.access_token}
""")
k8s_provider = k8s.Provider(f"{NAME}-k8s", kubeconfig=gke_kubeconfig)

worker_ns = k8s.core.v1.Namespace(
    f"{NAME}-workers-ns",
    metadata=k8s.meta.v1.ObjectMetaArgs(name="workers"),
    opts=pulumi.ResourceOptions(provider=k8s_provider, depends_on=[cluster]),
)
worker_ksa = k8s.core.v1.ServiceAccount(
    f"{NAME}-worker-ksa",
    metadata=k8s.meta.v1.ObjectMetaArgs(
        name="worker",
        namespace="workers",
        annotations={"iam.gke.io/gcp-service-account": worker_sa.email},
    ),
    opts=pulumi.ResourceOptions(provider=k8s_provider, depends_on=[worker_ns]),
)
```

- [ ] **Step 9: Export the new stack outputs**

At the end of the outputs section (after the existing `pulumi.export(...)` calls, before the `if wif_provider_name` block):

```python
pulumi.export("gke_cluster_endpoint", cluster.endpoint)
pulumi.export("gke_cluster_ca_cert", cluster.master_auth.cluster_ca_certificate)
pulumi.export("gke_worker_namespace", pulumi.Output.from_input("workers"))
pulumi.export("gke_worker_ksa", pulumi.Output.from_input("worker"))
pulumi.export("gke_worker_sa_email", worker_sa.email)
```

- [ ] **Step 10: Document the new env knobs**

In `deploy/env-template`, add (near the networking section):

```
# --- GKE Autopilot (worker jobs) ---
# Your CI/operator egress IP (CIDR) allowed to reach the cluster's public control-plane
# endpoint for `pulumi up` / kubectl. The backend's runtime path is private and does NOT
# need this. Leave blank to allow no public access (then apply namespace/KSA from in-VPC).
GKE_MASTER_AUTHORIZED_CIDR=""
# Control-plane /28 (must not overlap the subnet 10.10.0.0/24, connector 10.8.0.0/28, or peering range).
GKE_MASTER_CIDR="172.16.0.0/28"
# VPC-native secondary ranges for GKE pods/services (must not overlap the above).
GKE_POD_CIDR="10.20.0.0/16"
GKE_SVC_CIDR="10.30.0.0/20"
```

- [ ] **Step 11: Syntax-check the Pulumi program**

Run: `python -c "import ast; ast.parse(open('deploy/__main__.py').read())"`
Expected: no output (exit 0). If Pulumi/GCP creds are configured locally, also run `cd deploy && pulumi preview` and confirm it plans the new cluster, worker SA, secret, namespace, and KSA without errors.

- [ ] **Step 12: Commit**

```bash
git add deploy/__main__.py deploy/requirements.txt deploy/env-template
git commit -m "feat(infra): GKE Autopilot cluster + worker SA/WI for async jobs"
```

---

### Task 2: Backend — shared Kubernetes Job helper + settings + deps

**Files:**
- Create: `backend/collateral_ai/worker_jobs.py`
- Create: `backend/collateral_ai/tests/__init__.py` (if missing) and `backend/collateral_ai/tests/test_worker_jobs.py`
- Modify: `backend/config/settings/base.py`
- Modify: `backend/pyproject.toml` (+ `uv.lock`)

**Interfaces:**
- Produces: `collateral_ai.worker_jobs.create_worker_job(name_prefix: str, args: list[str], *, backoff_limit: int, active_deadline_seconds: int, cpu: str, memory: str) -> str` — builds a K8s Job manifest, submits it to `settings.WORKER_NAMESPACE`, returns the created Job name.
- Produces (settings): `WORKER_IMAGE`, `WORKER_NAMESPACE` (default `workers`), `WORKER_SERVICE_ACCOUNT` (default `worker`), `WORKER_DATABASE_URL`, `GKE_ENDPOINT`, `GKE_CA_CERT`.
- Consumes: nothing from other tasks.

- [ ] **Step 1: Add the Python client dependencies**

Run (from `backend/`): `uv add kubernetes google-auth`
This adds both to `pyproject.toml` `dependencies` and updates `uv.lock`. (`google-auth` is currently only transitive via `google-cloud-run`; pin it explicitly since we now import `google.auth` directly.)

- [ ] **Step 2: Add the worker settings**

In `backend/config/settings/base.py`, after the "Material generation (worker 2)" block (ends near line 358), add:

```python
# GKE Autopilot worker jobs (prod async workers)
# ------------------------------------------------------------------------------
# When DOCUMENT_PROCESSOR_JOB / MATERIAL_GENERATOR_JOB are set (prod), the workers run as
# Kubernetes Jobs on the Autopilot cluster instead of inline. These configure that path.
WORKER_IMAGE = env("WORKER_IMAGE", default="")
WORKER_NAMESPACE = env("WORKER_NAMESPACE", default="workers")
WORKER_SERVICE_ACCOUNT = env("WORKER_SERVICE_ACCOUNT", default="worker")
# Private-IP DB URL for pods (the base database-url uses the Cloud SQL unix socket).
WORKER_DATABASE_URL = env("WORKER_DATABASE_URL", default="")
GKE_ENDPOINT = env("GKE_ENDPOINT", default="")   # https://<control-plane-host>
GKE_CA_CERT = env("GKE_CA_CERT", default="")      # base64-encoded PEM
```

- [ ] **Step 3: Write the failing test for the helper**

Create `backend/collateral_ai/tests/__init__.py` (empty) if it does not exist, then create `backend/collateral_ai/tests/test_worker_jobs.py`:

```python
from __future__ import annotations

from unittest import mock

from collateral_ai import worker_jobs


def test_create_worker_job_builds_manifest(settings, monkeypatch):
    settings.WORKER_IMAGE = "us-central1-docker.pkg.dev/proj/collateral-ai-repo/backend:abc123"
    settings.WORKER_NAMESPACE = "workers"
    settings.WORKER_SERVICE_ACCOUNT = "worker"
    settings.WORKER_DATABASE_URL = "postgres://u:p@10.1.2.3:5432/db"
    monkeypatch.setenv("DJANGO_SETTINGS_MODULE", "config.settings.production")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "proj")
    monkeypatch.setenv("VERTEX_LOCATION", "us-central1")

    batch = mock.MagicMock()
    batch.create_namespaced_job.return_value.metadata.name = "docproc-xyz"
    monkeypatch.setattr(worker_jobs, "_batch_api", lambda: batch)

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
```

- [ ] **Step 4: Run the test to verify it fails**

Run: `docker compose -f docker-compose.local.yml run --rm django pytest collateral_ai/tests/test_worker_jobs.py -v`
Expected: FAIL (`ModuleNotFoundError: collateral_ai.worker_jobs`).

- [ ] **Step 5: Implement the helper**

Create `backend/collateral_ai/worker_jobs.py`:

```python
"""Create Kubernetes Jobs on GKE Autopilot for the async workers.

Auth uses Application Default Credentials (the Cloud Run runtime SA) as a bearer token
against the injected control-plane endpoint + CA cert — no kubeconfig on disk. Secrets are
passed as literal env forwarded from the backend's own environment (see spec §"Security note").
"""

from __future__ import annotations

import base64
import os
import tempfile

from django.conf import settings

# Env var names the backend forwards verbatim into the worker pod. DATABASE_URL is handled
# separately (the pod needs the private-IP form, not the backend's unix-socket form).
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
    import google.auth
    import google.auth.transport.requests
    from kubernetes import client

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
    from kubernetes import client

    env = [
        client.V1EnvVar(name=name, value=os.environ[name])
        for name in _FORWARDED_ENV
        if os.environ.get(name)
    ]
    env.append(client.V1EnvVar(name="DATABASE_URL", value=settings.WORKER_DATABASE_URL))
    return env


def create_worker_job(
    name_prefix: str,
    args: list[str],
    *,
    backoff_limit: int,
    active_deadline_seconds: int,
    cpu: str,
    memory: str,
) -> str:
    """Submit a one-off K8s Job running the backend image; return the created Job name."""
    from kubernetes import client

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
    created = _batch_api().create_namespaced_job(namespace=settings.WORKER_NAMESPACE, body=job)
    return created.metadata.name or ""
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `docker compose -f docker-compose.local.yml run --rm django pytest collateral_ai/tests/test_worker_jobs.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/collateral_ai/worker_jobs.py backend/collateral_ai/tests backend/config/settings/base.py backend/pyproject.toml backend/uv.lock
git commit -m "feat(workers): K8s Job helper + worker settings/deps"
```

---

### Task 3: Backend — documents worker trigger uses the K8s helper

**Files:**
- Modify: `backend/collateral_ai/documents/worker_trigger.py`
- Modify: `backend/collateral_ai/documents/tests/test_worker_trigger.py`

**Interfaces:**
- Consumes: `collateral_ai.worker_jobs.create_worker_job` (Task 2).
- Produces: `trigger_processing(document) -> None` (unchanged signature; fire-and-forget contract preserved).

- [ ] **Step 1: Rewrite the test's prod case for the K8s path**

Replace the `test_prod_executes_cloud_run_job` test in `backend/collateral_ai/documents/tests/test_worker_trigger.py` with (keep `test_local_runs_command_inline` as-is):

```python
def test_prod_creates_k8s_job(settings):
    settings.DOCUMENT_PROCESSOR_JOB = "collateral-ai-backend-docproc"
    doc = DocumentFactory()
    with (
        mock.patch(
            "collateral_ai.documents.worker_trigger.create_worker_job",
        ) as create_worker_job,
        mock.patch(
            "collateral_ai.documents.worker_trigger.call_command",
        ) as call_command,
    ):
        worker_trigger.trigger_processing(doc)
    call_command.assert_not_called()
    create_worker_job.assert_called_once_with(
        name_prefix="collateral-ai-backend-docproc",
        args=["manage.py", "process_document", "--document-id", str(doc.pk)],
        backoff_limit=1,
        active_deadline_seconds=900,
        cpu="2",
        memory="2Gi",
    )
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `docker compose -f docker-compose.local.yml run --rm django pytest collateral_ai/documents/tests/test_worker_trigger.py -v`
Expected: FAIL (`worker_trigger` has no attribute `create_worker_job`).

- [ ] **Step 3: Rewrite the trigger module**

Replace the entire contents of `backend/collateral_ai/documents/worker_trigger.py` with:

```python
"""Trigger document processing: inline command locally, K8s Job in prod."""

from __future__ import annotations

from django.conf import settings
from django.core.management import call_command

from collateral_ai.worker_jobs import create_worker_job


def trigger_processing(document) -> None:
    job = getattr(settings, "DOCUMENT_PROCESSOR_JOB", "")
    if not job:
        # Local/dev/test: run the management command inline.
        call_command("process_document", document_id=document.pk)
        return

    # Prod: submit a Kubernetes Job that runs the same command with --document-id.
    create_worker_job(
        name_prefix=job,
        args=["manage.py", "process_document", "--document-id", str(document.pk)],
        backoff_limit=1,
        active_deadline_seconds=900,
        cpu="2",
        memory="2Gi",
    )
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `docker compose -f docker-compose.local.yml run --rm django pytest collateral_ai/documents/tests/test_worker_trigger.py -v`
Expected: PASS (both tests).

- [ ] **Step 5: Commit**

```bash
git add backend/collateral_ai/documents/worker_trigger.py backend/collateral_ai/documents/tests/test_worker_trigger.py
git commit -m "feat(documents): trigger processing as a K8s Job"
```

---

### Task 4: Backend — materials worker trigger uses the K8s helper

**Files:**
- Modify: `backend/collateral_ai/materials/worker_trigger.py`
- Modify: `backend/collateral_ai/materials/tests/test_worker_trigger.py`

**Interfaces:**
- Consumes: `collateral_ai.worker_jobs.create_worker_job` (Task 2).
- Produces: `trigger_generation(material) -> str` (unchanged signature; returns created Job name, `''` inline; callers must NOT suppress exceptions).

- [ ] **Step 1: Rewrite the test's job-mode case for the K8s path**

Replace `test_job_mode_runs_cloud_run_job` in `backend/collateral_ai/materials/tests/test_worker_trigger.py` with (keep `test_inline_mode_runs_command` as-is):

```python
def test_job_mode_creates_k8s_job(settings):
    settings.MATERIAL_GENERATOR_JOB = "collateral-ai-backend-matgen"
    material = MarketingMaterialFactory()
    with mock.patch(
        "collateral_ai.materials.worker_trigger.create_worker_job",
        return_value="matgen-abc",
    ) as create_worker_job:
        result = trigger_generation(material)
    create_worker_job.assert_called_once_with(
        name_prefix="collateral-ai-backend-matgen",
        args=["manage.py", "generate_material", "--material-id", str(material.pk)],
        backoff_limit=0,
        active_deadline_seconds=600,
        cpu="1",
        memory="1Gi",
    )
    assert result == "matgen-abc"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `docker compose -f docker-compose.local.yml run --rm django pytest collateral_ai/materials/tests/test_worker_trigger.py -v`
Expected: FAIL (`worker_trigger` has no attribute `create_worker_job`).

- [ ] **Step 3: Rewrite the trigger module**

Replace the entire contents of `backend/collateral_ai/materials/worker_trigger.py` with:

```python
"""Trigger material generation: inline command locally, K8s Job in prod."""

from __future__ import annotations

from django.conf import settings
from django.core.management import call_command

from collateral_ai.worker_jobs import create_worker_job


def trigger_generation(material) -> str:
    """Dispatch worker 2 for `material`.

    Returns the created K8s Job name ('' inline).

    Unlike documents' trigger, callers must NOT suppress exceptions from this
    function — the view marks the material failed instead (spec §5.5).
    """
    job = getattr(settings, "MATERIAL_GENERATOR_JOB", "")
    if not job:
        # Local/dev/test: run the management command inline (synchronous).
        call_command("generate_material", material_id=material.pk)
        return ""

    # backoff_limit=0 is deliberate (unlike docproc): the command exits non-zero on
    # deterministic failures like validation exhaustion, and an auto re-run would burn
    # more LLM calls and flip a row the UI already shows as failed. (spec §6.6)
    return create_worker_job(
        name_prefix=job,
        args=["manage.py", "generate_material", "--material-id", str(material.pk)],
        backoff_limit=0,
        active_deadline_seconds=600,
        cpu="1",
        memory="1Gi",
    )
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `docker compose -f docker-compose.local.yml run --rm django pytest collateral_ai/materials/tests/test_worker_trigger.py -v`
Expected: PASS (both tests).

- [ ] **Step 5: Commit**

```bash
git add backend/collateral_ai/materials/worker_trigger.py backend/collateral_ai/materials/tests/test_worker_trigger.py
git commit -m "feat(materials): trigger generation as a K8s Job"
```

---

### Task 5: CI — cd.yml deploys backend for the K8s path, drops Cloud Run Jobs

**Files:**
- Modify: `.github/workflows/cd.yml`

**Interfaces:**
- Consumes: Pulumi outputs surfaced as GitHub secrets `GKE_CLUSTER_ENDPOINT`, `GKE_CLUSTER_CA_CERT` (added by the operator after `pulumi up`).

- [ ] **Step 1: Remove the two Cloud Run Job deploy steps**

Delete the entire `- name: Deploy document-processor Cloud Run Job` step and the entire `- name: Deploy material-generator Cloud Run Job` step (currently lines ~84–117). Also delete the now-unused `DOCPROC_JOB` / `MATGEN_JOB` env entries at the top ONLY if you re-add them below — they are still referenced by the backend deploy env string, so **keep** `DOCPROC_JOB` and `MATGEN_JOB` in the top-level `env:` block.

- [ ] **Step 2: Update the backend deploy step**

Replace the `- name: Deploy backend to Cloud Run` step's `run:` block with (adds `--vpc-egress all-traffic`, the `WORKER_DATABASE_URL` secret, and the GKE/worker env vars; keeps everything else):

```yaml
        run: |
          gcloud run deploy collateral-ai-backend \
            --image $AR_REPO/backend:${{ github.sha }} \
            --region $REGION \
            --service-account $RUN_SA_EMAIL \
            --vpc-connector collateral-ai-connector \
            --vpc-egress all-traffic \
            --add-cloudsql-instances ${{ secrets.CLOUD_SQL_CONNECTION_NAME }} \
            --set-secrets DATABASE_URL=database-url:latest,DJANGO_SECRET_KEY=django-secret-key:latest,WORKER_DATABASE_URL=database-url-private:latest \
            --set-env-vars "^@^DJANGO_SETTINGS_MODULE=config.settings.production@DJANGO_ALLOWED_HOSTS=${{ secrets.DJANGO_ALLOWED_HOSTS }}@DJANGO_ADMIN_URL=${{ secrets.DJANGO_ADMIN_URL }}@DJANGO_GCP_STORAGE_BUCKET_NAME=${{ secrets.DJANGO_GCP_STORAGE_BUCKET_NAME }}@CORS_ALLOWED_ORIGINS=${{ secrets.FRONTEND_SITE_URL }}@CSRF_TRUSTED_ORIGINS=${{ secrets.FRONTEND_SITE_URL }}@GOOGLE_CLOUD_PROJECT=${{ secrets.GCP_PROJECT_ID }}@VERTEX_LOCATION=$REGION@DOCUMENT_PROCESSOR_JOB=$DOCPROC_JOB@MATERIAL_GENERATOR_JOB=$MATGEN_JOB@WORKER_IMAGE=$AR_REPO/backend:${{ github.sha }}@WORKER_NAMESPACE=workers@WORKER_SERVICE_ACCOUNT=worker@GKE_ENDPOINT=https://${{ secrets.GKE_CLUSTER_ENDPOINT }}@GKE_CA_CERT=${{ secrets.GKE_CLUSTER_CA_CERT }}" \
            --cpu 1 --memory 512Mi --concurrency 80 --min-instances 0 --max-instances 4 \
            --timeout 300 --allow-unauthenticated
```

Note: `VERTEX_LOCATION` replaces the removed `DOCUMENT_PROCESSOR_REGION`/`MATERIAL_GENERATOR_REGION` (the K8s path forwards `VERTEX_LOCATION` to pods; the old per-worker region vars are obsolete). `DOCPROC_JOB`/`MATGEN_JOB` remain the Job **name prefixes**.

- [ ] **Step 3: Validate the workflow YAML**

Run: `python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/cd.yml')); print('ok')"`
Expected: `ok`. Confirm by eye that the two Cloud Run Job steps are gone and the backend deploy has `--vpc-egress all-traffic` and the new env/secret.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/cd.yml
git commit -m "ci: deploy backend for GKE worker path, drop Cloud Run Jobs"
```

---

### Task 6: Full backend test sweep + final verification

**Files:** none (verification only).

- [ ] **Step 1: Run the full backend test suite**

Run: `docker compose -f docker-compose.local.yml run --rm django pytest -q`
Expected: all pass (in particular the documents/materials worker-trigger tests and the new `test_worker_jobs.py`). Investigate any failure before proceeding.

- [ ] **Step 2: Lint (matches CI gates)**

Run: `pre-commit run --files backend/collateral_ai/worker_jobs.py backend/collateral_ai/documents/worker_trigger.py backend/collateral_ai/materials/worker_trigger.py backend/config/settings/base.py`
Expected: ruff (incl. PLC0415 — note the deliberate function-level imports in `worker_jobs.py` may trip PLC0415; if so, add `# noqa: PLC0415` to those import lines, matching how the old `worker_trigger.py` imported `run_v2` inside the function) and formatting pass.

- [ ] **Step 3: Confirm no lingering `run_v2` references**

Run: `grep -rn "run_v2\|google.cloud.run" backend/collateral_ai || echo "clean"`
Expected: `clean` (the Python worker path no longer uses the Cloud Run Jobs client).

---

## Post-implementation (operator steps — not code)

These require the user's GCP credentials/approval and run outside this plan's code changes:

1. `cd deploy && pulumi up` — creates the cluster, worker SA/WI, namespace+KSA, `database-url-private` secret, and grants `container.developer`. Set `GKE_MASTER_AUTHORIZED_CIDR` in `deploy/.env` to your CI/operator egress IP first.
2. Add GitHub Actions secrets from the new stack outputs: `GKE_CLUSTER_ENDPOINT` (= `pulumi stack output gke_cluster_endpoint`) and `GKE_CLUSTER_CA_CERT` (= `pulumi stack output gke_cluster_ca_cert --show-secrets`).
3. Merge to `main` → CD deploys the backend with the new env/egress and stops deploying the two Cloud Run Jobs.
4. Smoke test: upload a document / generate a material, then `kubectl get jobs -n workers` and confirm completion.
5. Delete the orphaned `collateral-ai-backend-docproc` and `collateral-ai-backend-matgen` Cloud Run Jobs.
