# deploy/components/workers.py
"""GKE Autopilot cluster for async worker Jobs, plus the least-privilege worker GSA and its
Workload Identity binding. Pulumi creates nothing INSIDE the cluster — the backend creates the
workers namespace + KSA over the VPC connector — so no cluster API access is needed at deploy time.
"""
from __future__ import annotations

import pulumi
import pulumi_gcp as gcp

from _iam import bind_project_roles, child_opts
from components.apis import ProjectApis
from components.network import Network
from components.registry import ArtifactRegistry
from config import InfraConfig

WORKER_ROLES = ["roles/aiplatform.user", "roles/storage.objectAdmin"]


class WorkerCluster(pulumi.ComponentResource):
    def __init__(
        self,
        cfg: InfraConfig,
        apis: ProjectApis,
        network: Network,
        registry: ArtifactRegistry,
        opts=None,
    ):
        super().__init__("collateralai:infra:WorkerCluster", "workers", None, opts)

        self.cluster = gcp.container.Cluster(
            f"{cfg.name}-autopilot",
            name=f"{cfg.name}-autopilot",
            location=cfg.region,
            enable_autopilot=True,
            network=network.network.id,
            subnetwork=network.subnet.id,
            ip_allocation_policy=gcp.container.ClusterIpAllocationPolicyArgs(
                cluster_secondary_range_name="gke-pods",
                services_secondary_range_name="gke-services",
            ),
            private_cluster_config=gcp.container.ClusterPrivateClusterConfigArgs(
                # Public nodes: worker pods need internet egress (LangSmith trace
                # export, any non-Google API) and the VPC has no Cloud NAT (a
                # $0-idle choice). Inbound stays IAM/RBAC-gated — same POC posture
                # as the public control-plane endpoint below.
                enable_private_nodes=False,
                enable_private_endpoint=False,
                master_ipv4_cidr_block=cfg.gke_master_cidr,
                master_global_access_config=gcp.container.ClusterPrivateClusterConfigMasterGlobalAccessConfigArgs(
                    enabled=True,
                ),
            ),
            # Public control-plane endpoint, gated by GCP IAM + Kubernetes RBAC rather than a
            # source-IP allowlist. Defaults to 0.0.0.0/0 so the Cloud Run backend (dynamic egress)
            # and kubectl can reach it with auth — no operator/CI/Cloud-Run IP to pin, no
            # flapping-IP failures. Narrow GKE_MASTER_AUTHORIZED_CIDR to re-restrict it.
            master_authorized_networks_config=gcp.container.ClusterMasterAuthorizedNetworksConfigArgs(
                cidr_blocks=[gcp.container.ClusterMasterAuthorizedNetworksConfigCidrBlockArgs(
                    cidr_block=cfg.gke_master_authorized_cidr, display_name="public-iam-gated")],
                gcp_public_cidrs_access_enabled=True,
            ),
            release_channel=gcp.container.ClusterReleaseChannelArgs(channel="REGULAR"),
            deletion_protection=False,
            opts=child_opts(self, depends_on=[apis.apis["container"], network.private_vpc_connection]),
        )

        # Least-privilege GSA for worker pods (Vertex + GCS; DB is private IP + password).
        self.worker_sa = gcp.serviceaccount.Account(
            f"{cfg.name}-gke-worker-sa",
            account_id="gke-worker-sa",
            display_name="GKE worker pods",
            opts=child_opts(self),
        )
        bind_project_roles(
            f"{cfg.name}-worker", cfg.project, self.worker_sa, WORKER_ROLES, parent=self,
        )

        # Workload Identity: bind the in-cluster KSA workers/worker to the worker GSA.
        # depends_on the cluster: the PROJECT.svc.id.goog identity pool only exists once a
        # Workload-Identity-enabled cluster is created.
        gcp.serviceaccount.IAMMember(
            f"{cfg.name}-worker-wi",
            service_account_id=self.worker_sa.name,
            role="roles/iam.workloadIdentityUser",
            member=pulumi.Output.concat(
                "serviceAccount:", cfg.project, ".svc.id.goog[workers/worker]"),
            opts=child_opts(self, depends_on=[self.cluster]),
        )

        # Autopilot's node service account (the default compute SA) must pull the backend image.
        default_compute_sa = gcp.compute.get_default_service_account(project=cfg.project)
        gcp.artifactregistry.RepositoryIamMember(
            f"{cfg.name}-node-ar-reader",
            project=cfg.project,
            location=cfg.region,
            repository=registry.repo.repository_id,
            role="roles/artifactregistry.reader",
            member=f"serviceAccount:{default_compute_sa.email}",
            opts=child_opts(self),
        )
        self.register_outputs({})
