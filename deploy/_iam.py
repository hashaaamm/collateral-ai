"""Shared IAM + resource-option helpers for the Pulumi stack."""
from __future__ import annotations

import pulumi
import pulumi_gcp as gcp


def child_opts(parent, *, depends_on=None) -> pulumi.ResourceOptions:
    """ResourceOptions for a resource moved under `parent`.

    The alias declares the resource was previously parented by the root stack, so
    re-parenting it under a ComponentResource is a state-only change (no replacement).
    `pulumi.ROOT_STACK_RESOURCE` is the SDK's self-descriptive spelling of "no original
    parent" (it is None); `Alias(parent=...)` with the name left unset keeps the same name.
    """
    return pulumi.ResourceOptions(
        parent=parent,
        aliases=[pulumi.Alias(parent=pulumi.ROOT_STACK_RESOURCE)],
        depends_on=depends_on,
    )


def bind_project_roles(prefix: str, project: str, sa, roles, *, parent=None) -> None:
    """Bind project-level roles to a service account (one IAMMember per role).

    Member-resource logical names are f"{prefix}-{role basename}" — unchanged from the
    former inline loops. When `parent` is given the members are aliased + re-parented.
    """
    for role in roles:
        gcp.projects.IAMMember(
            f"{prefix}-{role.split('/')[-1]}",
            project=project,
            role=role,
            member=sa.email.apply(lambda e: f"serviceAccount:{e}"),
            opts=child_opts(parent) if parent is not None else None,
        )
