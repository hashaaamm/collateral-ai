# deploy/components/apis.py
"""Enables the GCP service APIs the stack depends on."""
from __future__ import annotations

import pulumi
import pulumi_gcp as gcp

from _iam import child_opts
from config import InfraConfig

REQUIRED_APIS = [
    "run", "sqladmin", "vpcaccess", "artifactregistry", "secretmanager",
    "compute", "storage", "servicenetworking", "iam", "iamcredentials",
    "aiplatform",  # Vertex AI — document embeddings (gemini-embedding-001)
    "container",   # GKE Autopilot — async worker jobs
]


class ProjectApis(pulumi.ComponentResource):
    def __init__(self, cfg: InfraConfig, opts=None):
        super().__init__("collateralai:infra:ProjectApis", "apis", None, opts)
        self.apis = {
            name: gcp.projects.Service(
                f"api-{name}",
                project=cfg.project,
                service=f"{name}.googleapis.com",
                disable_on_destroy=False,
                opts=child_opts(self),
            )
            for name in REQUIRED_APIS
        }
        self.register_outputs({})
