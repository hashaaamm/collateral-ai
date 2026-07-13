# deploy/components/identities.py
"""Service accounts + IAM: the Cloud Run runtime SA (with self-impersonation for signed URLs)
and the GitHub Actions CI/CD SA (with keyless Workload Identity Federation to the repo)."""
from __future__ import annotations

import pulumi
import pulumi_gcp as gcp

from _iam import bind_project_roles, child_opts
from components.apis import ProjectApis
from config import InfraConfig

RUN_ROLES = [
    "roles/cloudsql.client", "roles/secretmanager.secretAccessor",
    "roles/storage.objectAdmin", "roles/aiplatform.user",
    "roles/run.developer", "roles/container.developer",
]
CICD_ROLES = ["roles/artifactregistry.writer", "roles/run.admin", "roles/iam.serviceAccountUser"]
CICD_GCS_ROLES = ["roles/storage.admin", "roles/compute.loadBalancerAdmin"]


class RuntimeIdentity(pulumi.ComponentResource):
    def __init__(self, cfg: InfraConfig, opts=None):
        super().__init__("collateralai:infra:RuntimeIdentity", "runtime-identity", None, opts)
        self.sa = gcp.serviceaccount.Account(
            f"{cfg.slug}-run-sa",
            account_id="cloud-run-sa",
            display_name="Cloud Run runtime",
            opts=child_opts(self),
        )
        bind_project_roles(f"{cfg.slug}-run", cfg.project, self.sa, RUN_ROLES, parent=self)

        # Sign blobs AS ITSELF (keyless V4 signed URLs via IAM SignBlob) — GCS logo upload/display.
        gcp.serviceaccount.IAMMember(
            f"{cfg.slug}-run-sa-token-creator",
            service_account_id=self.sa.name,
            role="roles/iam.serviceAccountTokenCreator",
            member=self.sa.email.apply(lambda e: f"serviceAccount:{e}"),
            opts=child_opts(self),
        )
        self.register_outputs({})


class CicdIdentity(pulumi.ComponentResource):
    def __init__(self, cfg: InfraConfig, apis: ProjectApis, opts=None):
        super().__init__("collateralai:infra:CicdIdentity", "cicd-identity", None, opts)
        self.sa = gcp.serviceaccount.Account(
            f"{cfg.slug}-cicd-sa",
            account_id="github-cicd-sa",
            display_name="GitHub Actions CI/CD",
            opts=child_opts(self),
        )
        roles = list(CICD_ROLES)
        # React SPA on GCS+CDN: CI also rsyncs the build + invalidates the CDN.
        if cfg.frontend_hosting == "gcs":
            roles += CICD_GCS_ROLES
        bind_project_roles(f"{cfg.slug}-cicd", cfg.project, self.sa, roles, parent=self)

        self.wif_provider_name: pulumi.Output | None = None
        if cfg.github_repo:
            self._provision_wif(cfg, apis)
        self.register_outputs({})

    def _provision_wif(self, cfg: InfraConfig, apis: ProjectApis) -> None:
        pool = gcp.iam.WorkloadIdentityPool(
            f"{cfg.name}-gh-pool",
            workload_identity_pool_id=f"{cfg.name}-gh-pool",
            display_name="GitHub Actions",
            opts=child_opts(self, depends_on=[apis.apis["iam"]]),
        )
        provider = gcp.iam.WorkloadIdentityPoolProvider(
            f"{cfg.name}-gh-provider",
            workload_identity_pool_id=pool.workload_identity_pool_id,
            workload_identity_pool_provider_id=f"{cfg.name}-gh-provider",
            display_name="GitHub OIDC",
            attribute_mapping={
                "google.subject": "assertion.sub",
                "attribute.repository": "assertion.repository",
            },
            attribute_condition=f"assertion.repository == '{cfg.github_repo}'",
            oidc=gcp.iam.WorkloadIdentityPoolProviderOidcArgs(
                issuer_uri="https://token.actions.githubusercontent.com",
            ),
            opts=child_opts(self),
        )
        gcp.serviceaccount.IAMMember(
            f"{cfg.name}-cicd-wif-binding",
            service_account_id=self.sa.name,
            role="roles/iam.workloadIdentityUser",
            member=pool.name.apply(
                lambda p: f"principalSet://iam.googleapis.com/{p}/attribute.repository/{cfg.github_repo}"
            ),
            opts=child_opts(self),
        )
        self.wif_provider_name = provider.name
