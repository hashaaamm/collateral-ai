"""Pulumi GCP infrastructure for Collateral AI.

Provisions everything the two Cloud Run services (frontend + backend) need:
VPC + connector, private Cloud SQL, Artifact Registry, Secret Manager, a static/media
bucket, and least-privilege service accounts for the runtime and for GitHub Actions CI/CD.

Pulumi owns infrastructure; GitHub Actions owns deploys (it updates the Cloud Run image
on each push). Config is read from deploy/.env — see env-template.
"""

import os

import pulumi
import pulumi_gcp as gcp
import pulumi_random as random
from dotenv import load_dotenv

load_dotenv()

PROJECT = os.environ["GOOGLE_PROJECT"]
REGION = os.environ.get("GOOGLE_REGION", "us-central1")
SLUG = "collateral_ai"          # snake_case (matches the Python package / DB identifiers)
NAME = SLUG.replace("_", "-")      # DNS-safe (GCP resource names disallow underscores)

DB_NAME = os.environ.get("DB_NAME", f"{SLUG}_db")
DB_USER = os.environ.get("DB_USER", f"{SLUG}_user")

# --- Enable required APIs -------------------------------------------------
REQUIRED_APIS = [
    "run", "sqladmin", "vpcaccess", "artifactregistry", "secretmanager",
    "compute", "storage", "servicenetworking", "iam", "iamcredentials",
    "aiplatform",  # Vertex AI — document embeddings (gemini-embedding-001)
    "container",   # GKE Autopilot — async worker jobs
]
apis = {
    name: gcp.projects.Service(
        f"api-{name}",
        project=PROJECT,
        service=f"{name}.googleapis.com",
        disable_on_destroy=False,
    )
    for name in REQUIRED_APIS
}

# --- Networking -----------------------------------------------------------
network = gcp.compute.Network(
    f"{NAME}-network",
    auto_create_subnetworks=False,
    opts=pulumi.ResourceOptions(depends_on=[apis["compute"]]),
)
subnet = gcp.compute.Subnetwork(
    f"{NAME}-subnet",
    network=network.id,
    ip_cidr_range=os.environ.get("SUBNET_IP", "10.10.0.0/24"),
    region=REGION,
    # VPC-native secondary ranges GKE Autopilot allocates pods/services from.
    secondary_ip_ranges=[
        gcp.compute.SubnetworkSecondaryIpRangeArgs(
            range_name="gke-pods",
            ip_cidr_range=os.environ.get("GKE_POD_CIDR", "10.20.0.0/16"),
        ),
        gcp.compute.SubnetworkSecondaryIpRangeArgs(
            range_name="gke-services",
            ip_cidr_range=os.environ.get("GKE_SVC_CIDR", "10.30.0.0/20"),
        ),
    ],
)
connector = gcp.vpcaccess.Connector(
    f"{NAME}-connector",
    # Deterministic name so CI (cd.yml / jobs.yml: collateral-ai-connector) can reference it.
    name=f"{NAME}-connector",
    region=REGION,
    network=network.name,
    ip_cidr_range=os.environ.get("VPC_CONNECTOR_CIDR", "10.8.0.0/28"),
    min_throughput=int(os.environ.get("VPC_CONNECTOR_MIN_THROUGHPUT", "200")),
    max_throughput=int(os.environ.get("VPC_CONNECTOR_MAX_THROUGHPUT", "300")),
    opts=pulumi.ResourceOptions(depends_on=[apis["vpcaccess"]]),
)

# Private services access for Cloud SQL private IP
private_ip = gcp.compute.GlobalAddress(
    f"{NAME}-private-ip",
    purpose="VPC_PEERING",
    address_type="INTERNAL",
    prefix_length=16,
    network=network.id,
)
private_vpc_connection = gcp.servicenetworking.Connection(
    f"{SLUG}-private-vpc",
    network=network.id,
    service="servicenetworking.googleapis.com",
    reserved_peering_ranges=[private_ip.name],
    opts=pulumi.ResourceOptions(depends_on=[apis["servicenetworking"]]),
)

# --- Cloud SQL (private) --------------------------------------------------
db_password = random.RandomPassword(
    f"{SLUG}-db-password",
    length=int(os.environ.get("DB_PASSWORD_LENGTH", "32")),
    special=False,
)
sql_instance = gcp.sql.DatabaseInstance(
    f"{NAME}-sql",
    database_version=os.environ.get("SQL_DB_VERSION", "POSTGRES_15"),
    region=REGION,
    # On by default (prod-safe). Set SQL_DELETION_PROTECTION=false for throwaway stacks so
    # `pulumi destroy` can tear the instance down.
    deletion_protection=os.environ.get("SQL_DELETION_PROTECTION", "true").lower() == "true",
    settings=gcp.sql.DatabaseInstanceSettingsArgs(
        # Cost-conscious defaults. db-custom-1-3840 = 1 vCPU / 3.75 GB. ZONAL (single zone) is far
        # cheaper than REGIONAL HA — set SQL_AVAILABILITY_TYPE=REGIONAL for production HA (roughly 2x).
        # ENTERPRISE (not ENTERPRISE_PLUS) is required for shared-core/legacy tiers like db-g1-small;
        # ENTERPRISE_PLUS only accepts db-perf-optimized-* tiers.
        edition=os.environ.get("SQL_EDITION", "ENTERPRISE"),
        tier=os.environ.get("SQL_INSTANCE_TIER", "db-custom-1-3840"),
        availability_type=os.environ.get("SQL_AVAILABILITY_TYPE", "ZONAL"),
        disk_type="PD_SSD",
        disk_size=20,
        disk_autoresize=True,
        ip_configuration=gcp.sql.DatabaseInstanceSettingsIpConfigurationArgs(
            ipv4_enabled=False,
            private_network=network.id,
        ),
        backup_configuration=gcp.sql.DatabaseInstanceSettingsBackupConfigurationArgs(
            enabled=True,
            point_in_time_recovery_enabled=True,
        ),
    ),
    opts=pulumi.ResourceOptions(depends_on=[private_vpc_connection]),
)
database = gcp.sql.Database(f"{SLUG}-database", instance=sql_instance.name, name=DB_NAME)
db_user = gcp.sql.User(
    f"{SLUG}-db-user", instance=sql_instance.name, name=DB_USER, password=db_password.result
)

database_url = pulumi.Output.all(db_password.result, sql_instance.connection_name).apply(
    lambda a: f"postgres://{DB_USER}:{a[0]}@/{DB_NAME}?host=/cloudsql/{a[1]}"
)

# --- Secret Manager -------------------------------------------------------
def make_secret(name: str, value: pulumi.Input[str]) -> gcp.secretmanager.Secret:
    secret = gcp.secretmanager.Secret(
        name,
        secret_id=name,
        replication=gcp.secretmanager.SecretReplicationArgs(auto={}),
        opts=pulumi.ResourceOptions(depends_on=[apis["secretmanager"]]),
    )
    gcp.secretmanager.SecretVersion(
        f"{name}-v1", secret=secret.id, secret_data=pulumi.Output.secret(value)
    )
    return secret


django_secret_key = random.RandomPassword(f"{SLUG}-django-secret", length=64, special=True)

# Optional feature secrets — created only when the feature is enabled (default on).
# Set ENABLE_PAYMENTS=false / ENABLE_EMAIL=false in deploy/.env for a simpler project.
ENABLE_PAYMENTS = os.environ.get("ENABLE_PAYMENTS", "true").lower() == "true"
ENABLE_EMAIL = os.environ.get("ENABLE_EMAIL", "true").lower() == "true"

secrets = {
    "database-url": make_secret("database-url", database_url),
    "django-secret-key": make_secret("django-secret-key", django_secret_key.result),
}
# Set these real values out-of-band (echo ... | gcloud secrets versions add ...).
if ENABLE_EMAIL:
    secrets["resend-api-key"] = make_secret(
        "resend-api-key", os.environ.get("RESEND_API_KEY_VALUE", "REPLACE_ME"))
if ENABLE_PAYMENTS:
    secrets["stripe-secret-key"] = make_secret(
        "stripe-secret-key", os.environ.get("STRIPE_SECRET_KEY_VALUE", "REPLACE_ME"))
    secrets["stripe-webhook-secret"] = make_secret(
        "stripe-webhook-secret", os.environ.get("STRIPE_WEBHOOK_SECRET_VALUE", "REPLACE_ME"))

# --- Artifact Registry (one repo, frontend + backend images) --------------
repo = gcp.artifactregistry.Repository(
    f"{NAME}-repo",
    repository_id=f"{NAME}-repo",
    location=REGION,
    format="DOCKER",
    opts=pulumi.ResourceOptions(depends_on=[apis["artifactregistry"]]),
)

# --- GKE Autopilot cluster (async worker jobs) ----------------------------
# Autopilot: node pools, VPC-native networking, and Workload Identity are managed/on by
# default. Nodes stay private (no public node IPs). The control-plane endpoint is PUBLIC and
# open to all source IPs (0.0.0.0/0) — access is still gated by GCP IAM + Kubernetes RBAC
# (kubectl needs `gcloud` auth; the backend uses its Cloud Run SA token). This is a
# deliberate POC choice: it removes the master-authorized-networks IP allowlist entirely, so
# there is no operator/CI/Cloud-Run source IP to pin and no flapping-IP failures. Override
# GKE_MASTER_AUTHORIZED_CIDR to re-restrict the endpoint later if needed.
# NOTE: Pulumi does NOT create anything inside the cluster — the backend creates the workers
# namespace + KSA itself (worker_jobs.ensure_worker_namespace), so no cluster API access is
# needed at deploy time.
GKE_MASTER_AUTHORIZED_CIDR = os.environ.get("GKE_MASTER_AUTHORIZED_CIDR", "0.0.0.0/0").strip()

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
        cidr_blocks=[gcp.container.ClusterMasterAuthorizedNetworksConfigCidrBlockArgs(
            cidr_block=GKE_MASTER_AUTHORIZED_CIDR, display_name="public-iam-gated")],
        gcp_public_cidrs_access_enabled=True,
    ),
    release_channel=gcp.container.ClusterReleaseChannelArgs(channel="REGULAR"),
    deletion_protection=False,
    opts=pulumi.ResourceOptions(depends_on=[apis["container"], private_vpc_connection]),
)

# Least-privilege GSA for worker pods (Vertex + GCS; DB is private IP + password).
worker_sa = gcp.serviceaccount.Account(
    f"{SLUG}-gke-worker-sa", account_id="gke-worker-sa", display_name="GKE worker pods"
)
for role in ["roles/aiplatform.user", "roles/storage.objectAdmin"]:
    gcp.projects.IAMMember(
        f"{SLUG}-worker-{role.split('/')[-1]}",
        project=PROJECT, role=role,
        member=worker_sa.email.apply(lambda e: f"serviceAccount:{e}"),
    )

# Workload Identity: bind the in-cluster KSA workers/worker to the worker GSA.
# depends_on the cluster: the PROJECT.svc.id.goog identity pool only exists once a
# Workload-Identity-enabled cluster is created, so this binding must come after it.
gcp.serviceaccount.IAMMember(
    f"{SLUG}-worker-wi",
    service_account_id=worker_sa.name,
    role="roles/iam.workloadIdentityUser",
    member=pulumi.Output.concat("serviceAccount:", PROJECT, ".svc.id.goog[workers/worker]"),
    opts=pulumi.ResourceOptions(depends_on=[cluster]),
)

# Autopilot's node service account (the default compute SA) must pull the backend image.
default_compute_sa = gcp.compute.get_default_service_account(project=PROJECT)
gcp.artifactregistry.RepositoryIamMember(
    f"{NAME}-node-ar-reader",
    project=PROJECT, location=REGION, repository=repo.repository_id,
    role="roles/artifactregistry.reader",
    member=f"serviceAccount:{default_compute_sa.email}",
)

# Private-IP DB URL for pods (base database-url uses the Cloud SQL unix socket).
database_url_private = pulumi.Output.all(
    db_password.result, sql_instance.private_ip_address
).apply(lambda a: f"postgres://{DB_USER}:{a[0]}@{a[1]}:5432/{DB_NAME}")
secrets["database-url-private"] = make_secret("database-url-private", database_url_private)

# NOTE: the workers namespace + Workload-Identity KSA are NOT created here. The backend
# creates them itself (worker_jobs.ensure_worker_namespace) from inside the VPC, so the
# control plane can stay fully private and Pulumi needs no cluster API access. The GSA-side
# Workload Identity binding above (worker-wi) is a plain IAM policy and needs no cluster
# access — the workers/worker principal is symbolic and need not exist when it's bound.

# --- Static / media bucket ------------------------------------------------
bucket = gcp.storage.Bucket(
    f"{NAME}-static-media",
    name=f"{PROJECT}-{NAME}-static-media",
    location=REGION,
    uniform_bucket_level_access=True,
    cors=[gcp.storage.BucketCorArgs(
        origins=os.environ.get("BUCKET_CORS_ALLOWED_ORIGINS", "http://localhost:3000,https://collateralai.tinyfleet.dev").split(","),
        methods=["GET", "PUT", "POST", "DELETE"],
        response_headers=["Content-Type", "Authorization"],
        max_age_seconds=3600,
    )],
    opts=pulumi.ResourceOptions(depends_on=[apis["storage"]]),
)

# --- Service accounts -----------------------------------------------------
run_sa = gcp.serviceaccount.Account(
    f"{SLUG}-run-sa", account_id="cloud-run-sa", display_name="Cloud Run runtime"
)
for role in ["roles/cloudsql.client", "roles/secretmanager.secretAccessor", "roles/storage.objectAdmin", "roles/aiplatform.user", "roles/run.developer", "roles/container.developer"]:
    gcp.projects.IAMMember(
        f"{SLUG}-run-{role.split('/')[-1]}",
        project=PROJECT, role=role,
        member=run_sa.email.apply(lambda e: f"serviceAccount:{e}"),
    )

# Let the Cloud Run runtime SA sign blobs AS ITSELF (keyless V4 signed URLs via the
# IAM SignBlob API) — required for GCS logo upload/display signed URLs.
gcp.serviceaccount.IAMMember(
    f"{SLUG}-run-sa-token-creator",
    service_account_id=run_sa.name,
    role="roles/iam.serviceAccountTokenCreator",
    member=run_sa.email.apply(lambda e: f"serviceAccount:{e}"),
)

cicd_sa = gcp.serviceaccount.Account(
    f"{SLUG}-cicd-sa", account_id="github-cicd-sa", display_name="GitHub Actions CI/CD"
)
cicd_roles = ["roles/artifactregistry.writer", "roles/run.admin", "roles/iam.serviceAccountUser"]
# For the React SPA on GCS+CDN, CI also needs to rsync the build + invalidate the CDN.
if os.environ.get("FRONTEND_HOSTING", "cloudrun") == "gcs":
    cicd_roles += ["roles/storage.admin", "roles/compute.loadBalancerAdmin"]
for role in cicd_roles:
    gcp.projects.IAMMember(
        f"{SLUG}-cicd-{role.split('/')[-1]}",
        project=PROJECT, role=role,
        member=cicd_sa.email.apply(lambda e: f"serviceAccount:{e}"),
    )

# --- Workload Identity Federation (GitHub Actions → github-cicd-sa, keyless) ---
# Set GITHUB_REPO="owner/repo" in deploy/.env to provision. Without it, WIF is skipped and you'd
# have to auth CI another way. This is what cd.yml's `secrets.GCP_WIF_PROVIDER` points at.
GITHUB_REPO = os.environ.get("GITHUB_REPO", "").strip()
wif_provider_name = None
if GITHUB_REPO:
    wif_pool = gcp.iam.WorkloadIdentityPool(
        f"{NAME}-gh-pool",
        workload_identity_pool_id=f"{NAME}-gh-pool",
        display_name="GitHub Actions",
        opts=pulumi.ResourceOptions(depends_on=[apis["iam"]]),
    )
    wif_prov = gcp.iam.WorkloadIdentityPoolProvider(
        f"{NAME}-gh-provider",
        workload_identity_pool_id=wif_pool.workload_identity_pool_id,
        workload_identity_pool_provider_id=f"{NAME}-gh-provider",
        display_name="GitHub OIDC",
        attribute_mapping={
            "google.subject": "assertion.sub",
            "attribute.repository": "assertion.repository",
        },
        # Only tokens from THIS repo may use the pool.
        attribute_condition=f"assertion.repository == '{GITHUB_REPO}'",
        oidc=gcp.iam.WorkloadIdentityPoolProviderOidcArgs(
            issuer_uri="https://token.actions.githubusercontent.com",
        ),
    )
    # Let the repo impersonate the CI service account.
    gcp.serviceaccount.IAMMember(
        f"{NAME}-cicd-wif-binding",
        service_account_id=cicd_sa.name,
        role="roles/iam.workloadIdentityUser",
        member=wif_pool.name.apply(
            lambda pool: f"principalSet://iam.googleapis.com/{pool}/attribute.repository/{GITHUB_REPO}"
        ),
    )
    # The value GitHub needs as the GCP_WIF_PROVIDER secret.
    wif_provider_name = wif_prov.name

# --- Frontend hosting (React SPA on GCS + Cloud CDN + custom domain) --------
# Only when FRONTEND_HOSTING=gcs and a domain + shared DNS project/zone are set. Next.js (SSR) stays
# on Cloud Run and skips this. The DNS record is created in the shared-infra project via a 2nd provider.
if (
    os.environ.get("FRONTEND_HOSTING", "cloudrun") == "gcs"
    and os.environ.get("DOMAIN")
    and os.environ.get("DNS_PROJECT")
    and os.environ.get("DNS_ZONE")
):
    from frontend_hosting import provision_frontend_cdn

    provision_frontend_cdn(
        name=NAME,
        project=PROJECT,
        region=REGION,
        domain=os.environ["DOMAIN"],
        subdomain=os.environ.get("FRONTEND_SUBDOMAIN", "app"),
        dns_project=os.environ["DNS_PROJECT"],
        dns_zone=os.environ["DNS_ZONE"],
        depends_on=[apis["compute"], apis["storage"]],
    )

# --- Outputs (consumed by GitHub Actions) ---------------------------------
pulumi.export("project_id", PROJECT)
pulumi.export("region", REGION)
pulumi.export("vpc_connector_id", connector.id)
pulumi.export("cloud_run_service_account_email", run_sa.email)
pulumi.export("github_cicd_service_account_email", cicd_sa.email)
pulumi.export("db_instance_connection_name", sql_instance.connection_name)
pulumi.export("artifact_registry_repo_url", repo.repository_id.apply(
    lambda r: f"{REGION}-docker.pkg.dev/{PROJECT}/{r}"))
pulumi.export("static_media_bucket_name", bucket.name)
# Public control-plane endpoint (open to all IPs, IAM-gated). The backend reaches it over the
# internet via Cloud Run's default egress; kubectl reaches it from anywhere with gcloud auth.
pulumi.export("gke_cluster_endpoint", cluster.endpoint)
pulumi.export("gke_cluster_ca_cert", cluster.master_auth.cluster_ca_certificate)
pulumi.export("gke_worker_namespace", pulumi.Output.from_input("workers"))
pulumi.export("gke_worker_ksa", pulumi.Output.from_input("worker"))
pulumi.export("gke_worker_sa_email", worker_sa.email)
if wif_provider_name is not None:
    # Set this as the GitHub Actions secret GCP_WIF_PROVIDER.
    pulumi.export("wif_provider", wif_provider_name)
