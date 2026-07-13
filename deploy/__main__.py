"""Pulumi GCP infrastructure for Collateral AI.

Provisions everything the two Cloud Run services (frontend + backend) need: VPC + connector,
private Cloud SQL, Artifact Registry, Secret Manager, a static/media bucket, a GKE Autopilot
cluster for async workers, and least-privilege service accounts for the runtime and CI/CD.

Pulumi owns infrastructure; GitHub Actions owns deploys. Config is read from deploy/.env
(see env-template) into InfraConfig. Each subsystem is a ComponentResource under components/.
"""

import pulumi

from components.apis import ProjectApis
from components.database import Database
from components.frontend_cdn import FrontendCdn
from components.identities import CicdIdentity, RuntimeIdentity
from components.network import Network
from components.registry import ArtifactRegistry
from components.secrets import SecretStore
from components.storage import StaticMediaBucket
from components.workers import WorkerCluster
from config import InfraConfig

cfg = InfraConfig.from_env()

apis = ProjectApis(cfg)
network = Network(cfg, apis)
database = Database(cfg, network)
registry = ArtifactRegistry(cfg, apis)
workers = WorkerCluster(cfg, apis, network, registry)
bucket = StaticMediaBucket(cfg, apis)
runtime = RuntimeIdentity(cfg)
cicd = CicdIdentity(cfg, apis)

# Secrets. django-secret-key value is a generated RandomPassword; feature secrets are gated.
import pulumi_random as random  # noqa: E402  (local: only the orchestrator needs it)

django_secret_key = random.RandomPassword(f"{cfg.slug}-django-secret", length=64, special=True)

secrets = SecretStore(cfg, apis)
secrets.add("database-url", database.socket_url)
secrets.add("django-secret-key", django_secret_key.result)
if cfg.enable_email:
    secrets.add("resend-api-key", cfg.resend_api_key_value)
if cfg.enable_payments:
    secrets.add("stripe-secret-key", cfg.stripe_secret_key_value)
    secrets.add("stripe-webhook-secret", cfg.stripe_webhook_secret_value)
secrets.add("database-url-private", database.private_url)

if (
    cfg.frontend_hosting == "gcs"
    and cfg.domain
    and cfg.dns_project
    and cfg.dns_zone
):
    FrontendCdn(cfg, apis)

# --- Outputs (consumed by GitHub Actions) ---------------------------------
pulumi.export("project_id", cfg.project)
pulumi.export("region", cfg.region)
pulumi.export("vpc_connector_id", network.connector.id)
pulumi.export("cloud_run_service_account_email", runtime.sa.email)
pulumi.export("github_cicd_service_account_email", cicd.sa.email)
pulumi.export("db_instance_connection_name", database.instance.connection_name)
pulumi.export("artifact_registry_repo_url", registry.repo.repository_id.apply(
    lambda r: f"{cfg.region}-docker.pkg.dev/{cfg.project}/{r}"))
pulumi.export("static_media_bucket_name", bucket.bucket.name)
pulumi.export("gke_cluster_endpoint", workers.cluster.endpoint)
pulumi.export("gke_cluster_ca_cert", workers.cluster.master_auth.cluster_ca_certificate)
pulumi.export("gke_worker_namespace", pulumi.Output.from_input("workers"))
pulumi.export("gke_worker_ksa", pulumi.Output.from_input("worker"))
pulumi.export("gke_worker_sa_email", workers.worker_sa.email)
if cicd.wif_provider_name is not None:
    # Set this as the GitHub Actions secret GCP_WIF_PROVIDER.
    pulumi.export("wif_provider", cicd.wif_provider_name)
