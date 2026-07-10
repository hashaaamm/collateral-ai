# Move worker jobs from Cloud Run Jobs to GKE Autopilot

**Date:** 2026-07-10
**Status:** Approved

## Summary

The backend triggers two asynchronous workers today as **Cloud Run Jobs**, created at
request time via the `run_v2.JobsClient().run_job()` API with a container override:

- `collateral-ai-backend-docproc` — document processing (`process_document --document-id N`)
- `collateral-ai-backend-matgen` — material generation (`generate_material --material-id N`)

This design moves those two workers to **Kubernetes Jobs** on a **GKE Autopilot** cluster.
The Django backend stays on **Cloud Run** and creates the K8s Jobs **directly via the
Kubernetes API client** (no Pub/Sub). The migrations Cloud Run Job (`jobs.yml`) is out of
scope and stays as-is.

## Goals

- One GKE Autopilot cluster (not custom/Standard GKE), provisioned via **Pulumi**.
- Backend on Cloud Run creates K8s Jobs at runtime using the K8s API client.
- Runtime backend → control-plane path is **private, through the existing VPC connector**.
- Worker pods reach Cloud SQL over **private IP**, and Vertex AI / GCS via **Workload Identity**.
- The two `gcloud run jobs deploy` steps are removed from `cd.yml`.
- Preserve today's per-worker semantics (retries, timeouts, resources, local inline path).

## Non-goals

- Pub/Sub (explicitly not used — direct K8s API).
- Migrating the manual migrations job (`jobs.yml`).
- Frontend changes.
- Moving the backend off Cloud Run.

## Cost / cold-start (project is cost-first, $0-idle biased)

- **Idle ≈ $0.** GKE waives the ~$0.10/hr (~$72/mo) cluster management fee for **one**
  zonal/Autopilot cluster per billing account via the ~$74.40/mo free credit. With a single
  cluster and no running pods, idle compute is $0 (Autopilot bills pod CPU/mem only while a
  job runs).
- **Per run:** Autopilot pod CPU/mem for the job's duration only.
- **Cold start ~60–120s** when no node is warm (schedule pod → provision node → pull image),
  comparable to the ~90s Cloud Run Job cold start already accepted.

## Architecture

```
                    (private path, VPC connector, all-egress)
Cloud Run backend  ───────────────────────────────────────▶  GKE control plane
  (cloud-run-sa,                                               (creates K8s Job)
   container.developer)                                              │
                                                                     ▼
                                                          Autopilot Job pod
                                                          (KSA `worker` → gke-worker-sa)
                                                            ├─ Cloud SQL (private IP + pw)
                                                            ├─ Vertex AI  (WI)
                                                            └─ GCS        (WI)
```

## Detailed design

### 1. Pulumi infra (`deploy/__main__.py`)

- **Enable API:** `container.googleapis.com`.
- **GKE Autopilot cluster** in the existing `network`/`subnet`:
  - `enable_autopilot=True` (Autopilot → VPC-native + Workload Identity are on by default).
  - `ip_allocation_policy` referencing the VPC-native pod/service ranges.
  - `private_cluster_config`: `enable_private_nodes=True`,
    `enable_private_endpoint=False` (a **restricted** public endpoint is kept **only** for
    Pulumi/CI to apply the namespace + KSA), `master_global_access_config` enabled so the
    in-VPC backend reaches the control plane privately, `master_ipv4_cidr_block` = a spare /28.
  - `master_authorized_networks_config`: the operator/CI egress IP only (public endpoint is
    for management, not the runtime path). Configurable via `deploy/.env`.
  - `release_channel` = REGULAR.
  - **Rationale for the endpoint split:** the backend's *runtime* path is fully private (VPC
    connector → private control-plane endpoint). The restricted public endpoint exists purely
    so IaC/CI (which run outside the VPC) can create the two cluster objects below. A
    fully-private-only endpoint would require a bastion/proxy for IaC — deliberately avoided.
- **`gke-worker-sa`** (GCP service account) — least privilege for pods:
  - `roles/aiplatform.user` (Vertex embeddings + LLM)
  - `roles/storage.objectAdmin` (GCS media)
  - No `cloudsql.client` (DB is reached over private IP + password, not the proxy).
- **Node image pull:** grant `roles/artifactregistry.reader` to the Autopilot node service
  account so pods can pull the backend image from Artifact Registry.
- **`cloud-run-sa` gains `roles/container.developer`** — authorizes K8s Job creation via IAM,
  so **no in-cluster RBAC** needs bootstrapping.
- **Workload Identity:** via Pulumi's **Kubernetes provider** (kubeconfig built from the
  cluster outputs), create:
  - Namespace `workers`.
  - K8s ServiceAccount `worker` annotated
    `iam.gke.io/gcp-service-account: gke-worker-sa@<project>.iam.gserviceaccount.com`.
  - IAM binding: `gke-worker-sa` ← `roles/iam.workloadIdentityUser` for
    `serviceAccount:<project>.svc.id.goog[workers/worker]`.
  - **No K8s Secret objects** are created in the cluster.
- **`database-url-private` secret** (Secret Manager): the private-IP DB URL
  `postgres://<user>:<pw>@<sql_instance.private_ip_address>:5432/<db>`. (The existing
  `database-url` uses the Cloud SQL unix socket `host=/cloudsql/...`, unusable from a pod.)
- **New outputs:** `gke_cluster_endpoint`, `gke_cluster_ca_cert`, `gke_worker_namespace`
  (`workers`), `gke_worker_ksa` (`worker`), `gke_worker_sa_email`.

### 2. Backend worker triggers

Both `worker_trigger.py` modules keep the same shape — the **local/dev/test inline path is
unchanged** (same settings flag → `call_command(...)` runs the management command inline).
Only the prod branch changes: replace the `run_v2` block with the **Kubernetes Python
client**.

- **Auth (no kubeconfig on disk):** obtain a GCP OAuth token via `google.auth` default
  credentials; build a `kubernetes.client.Configuration` with `host=GKE_ENDPOINT`,
  the CA from `GKE_CA_CERT` (written to a temp file), and the token as the bearer.
- **Job manifest** (`BatchV1Api().create_namespaced_job` into `WORKER_NAMESPACE`):
  - `image` = `WORKER_IMAGE` (SHA-pinned; forwarded from the backend's own env).
  - `command=["python"]`, `args=["manage.py","process_document","--document-id","<pk>"]`
    (matgen: `["manage.py","generate_material","--material-id","<pk>"]`).
  - `serviceAccountName: worker`, `restartPolicy: Never`.
  - **Env passed as literal values in the pod spec**, forwarded from the backend's own env:
    `DATABASE_URL` (= `WORKER_DATABASE_URL`, private-IP form), `DJANGO_SECRET_KEY`,
    `DJANGO_SETTINGS_MODULE`, `GOOGLE_CLOUD_PROJECT`, `VERTEX_LOCATION`,
    `DJANGO_GCP_STORAGE_BUCKET_NAME`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_ADMIN_URL`.
    No K8s Secret objects and no Secret Manager access from pods.
  - `backoffLimit`: docproc `1`, matgen `0` (preserves current retry semantics — matgen must
    not auto-retry).
  - `activeDeadlineSeconds`: docproc `900`, matgen `600`.
  - `ttlSecondsAfterFinished`: auto-delete finished Jobs (e.g. 3600).
  - Resources: docproc `2` CPU / `2Gi`, matgen `1` CPU / `1Gi` (Autopilot rounds to allowed
    combinations).
  - Unique Job name per run, e.g. `docproc-<pk>-<short-suffix>` (suffix derived from the pk /
    a counter — no `Math.random`; `metadata.generateName` is acceptable).
- **`materials/worker_trigger.py`** keeps its contract: callers must NOT suppress exceptions
  (the view marks the material failed). Return the created Job name (`''` inline), analogous
  to today's operation-name return.
- **`documents/worker_trigger.py`** keeps its fire-and-forget contract.

### 3. Settings (`config/settings/base.py`)

New env-driven settings (all empty by default → inline local path):

- `DOCUMENT_PROCESSOR_JOB` / `MATERIAL_GENERATOR_JOB` — retained; non-empty ⇒ K8s mode,
  and used as the Job name prefix.
- `GKE_ENDPOINT`, `GKE_CA_CERT` (base64 PEM), `WORKER_IMAGE`, `WORKER_NAMESPACE` (default
  `workers`), `WORKER_SERVICE_ACCOUNT` (default `worker`), `WORKER_DATABASE_URL`.
- The `*_REGION` settings are no longer needed for the K8s path but may remain harmlessly.

Add `kubernetes` and `google-auth` to backend dependencies.

### 4. Tests

- `documents/tests/test_worker_trigger.py` and `materials/tests/test_worker_trigger.py`:
  replace the `run_v2.JobsClient` mocks with mocks of the K8s client
  (`kubernetes.client.BatchV1Api.create_namespaced_job`), asserting the manifest carries the
  right command/args, namespace, service account, image, backoffLimit, and injected env.
- The inline-path tests (no job configured → `call_command`) stay unchanged.

### 5. CI (`.github/workflows/cd.yml`)

- **Remove** the two steps: "Deploy document-processor Cloud Run Job" and
  "Deploy material-generator Cloud Run Job".
- Backend deploy step:
  - Add `--vpc-egress all-traffic` (routes control-plane API calls through the VPC connector →
    private control-plane endpoint).
  - Add env: `WORKER_IMAGE=$AR_REPO/backend:${{ github.sha }}`, `GKE_ENDPOINT`, `GKE_CA_CERT`,
    `WORKER_NAMESPACE`, `WORKER_SERVICE_ACCOUNT`, and keep `DOCUMENT_PROCESSOR_JOB` /
    `MATERIAL_GENERATOR_JOB` (now K8s Job name prefixes).
  - Add `--set-secrets WORKER_DATABASE_URL=database-url-private:latest` alongside the existing
    secrets.
  - `GKE_ENDPOINT` / `GKE_CA_CERT` sourced from Pulumi outputs (via GitHub secrets, matching
    how `CLOUD_SQL_CONNECTION_NAME` etc. are already wired).
- `jobs.yml` (migrations) is untouched.

## Security note (accepted)

Worker DB/Django secrets appear as **literal env in the Job pod spec** (stored in GKE etcd,
encrypted at rest). This is the same trust level as the backend already holding them and
avoids the Secret Manager CSI driver. Accepted for MVP; can move to Secret Manager CSI later
if the threat model tightens.

## Rollout / ordering

1. `pulumi up` — creates cluster, worker SA, WI binding, namespace + KSA, `database-url-private`,
   `container.developer` on `cloud-run-sa`.
2. Wire the new Pulumi outputs into GitHub secrets.
3. Merge backend + `cd.yml` changes → CD deploys the backend with the new env/egress and stops
   deploying the two Cloud Run Jobs.
4. Verify an upload triggers a K8s Job (`kubectl get jobs -n workers`) and completes.
5. Delete the now-orphaned `collateral-ai-backend-docproc` / `-matgen` Cloud Run Jobs.
