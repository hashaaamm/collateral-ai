"""Shared IAM + resource-option helpers for the Pulumi stack."""
from __future__ import annotations

import pulumi
import pulumi_gcp as gcp


def child_opts(parent, *, depends_on=None) -> pulumi.ResourceOptions:
    """ResourceOptions for a resource owned by `parent` (a ComponentResource)."""
    return pulumi.ResourceOptions(parent=parent, depends_on=depends_on)


def bind_project_roles(prefix: str, project: str, sa, roles, *, parent=None) -> None:
    """Bind project-level roles to a service account — one IAMMember per role.

    Member-resource logical names are f"{prefix}-{role basename}".
    """
    for role in roles:
        gcp.projects.IAMMember(
            f"{prefix}-{role.split('/')[-1]}",
            project=project,
            role=role,
            member=sa.email.apply(lambda e: f"serviceAccount:{e}"),
            opts=child_opts(parent) if parent is not None else None,
        )
