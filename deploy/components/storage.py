# deploy/components/storage.py
"""Static / media bucket (uniform access + CORS) for app-uploaded assets."""
from __future__ import annotations

import pulumi
import pulumi_gcp as gcp

from _iam import child_opts
from components.apis import ProjectApis
from config import InfraConfig


class StaticMediaBucket(pulumi.ComponentResource):
    def __init__(self, cfg: InfraConfig, apis: ProjectApis, opts=None):
        super().__init__("collateralai:infra:StaticMediaBucket", "storage", None, opts)
        self.bucket = gcp.storage.Bucket(
            f"{cfg.name}-static-media",
            name=f"{cfg.project}-{cfg.name}-static-media",
            location=cfg.region,
            uniform_bucket_level_access=True,
            force_destroy=True,  # allow teardown of a non-empty bucket (app-uploaded assets)
            cors=[gcp.storage.BucketCorArgs(
                origins=cfg.bucket_cors_allowed_origins,
                methods=["GET", "PUT", "POST", "DELETE"],
                response_headers=["Content-Type", "Authorization"],
                max_age_seconds=3600,
            )],
            opts=child_opts(self, depends_on=[apis.apis["storage"]]),
        )
        self.register_outputs({})
