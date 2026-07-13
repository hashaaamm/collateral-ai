# deploy/components/secrets.py
"""Secret Manager wrapper. `.add(name, value)` creates a Secret + first version and tracks
it in `.secrets`; the former module-level make_secret() with the same resource names."""
from __future__ import annotations

import pulumi
import pulumi_gcp as gcp

from _iam import child_opts
from components.apis import ProjectApis
from config import InfraConfig


class SecretStore(pulumi.ComponentResource):
    def __init__(self, cfg: InfraConfig, apis: ProjectApis, opts=None):
        super().__init__("collateralai:infra:SecretStore", "secrets", None, opts)
        self._apis = apis
        self.secrets: dict[str, gcp.secretmanager.Secret] = {}
        self.register_outputs({})

    def add(self, name: str, value: pulumi.Input[str]) -> gcp.secretmanager.Secret:
        secret = gcp.secretmanager.Secret(
            name,
            secret_id=name,
            replication=gcp.secretmanager.SecretReplicationArgs(auto={}),
            opts=child_opts(self, depends_on=[self._apis.apis["secretmanager"]]),
        )
        gcp.secretmanager.SecretVersion(
            f"{name}-v1",
            secret=secret.id,
            secret_data=pulumi.Output.secret(value),
            opts=child_opts(self),
        )
        self.secrets[name] = secret
        return secret
