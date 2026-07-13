# deploy/components/registry.py
"""One Docker Artifact Registry repo shared by the frontend + backend images."""
from __future__ import annotations

import pulumi
import pulumi_gcp as gcp

from _iam import child_opts
from components.apis import ProjectApis
from config import InfraConfig


class ArtifactRegistry(pulumi.ComponentResource):
    def __init__(self, cfg: InfraConfig, apis: ProjectApis, opts=None):
        super().__init__("collateralai:infra:ArtifactRegistry", "registry", None, opts)
        self.repo = gcp.artifactregistry.Repository(
            f"{cfg.name}-repo",
            repository_id=f"{cfg.name}-repo",
            location=cfg.region,
            format="DOCKER",
            opts=child_opts(self, depends_on=[apis.apis["artifactregistry"]]),
        )
        self.register_outputs({})
