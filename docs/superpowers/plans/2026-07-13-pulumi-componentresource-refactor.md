# Pulumi ComponentResource Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure `deploy/` from a ~400-line procedural `__main__.py` into a typed config object plus one `pulumi.ComponentResource` per subsystem, preserving live prod state via `ROOT_STACK_RESOURCE` aliases.

**Architecture:** A frozen `InfraConfig` dataclass parses all env vars in one place. Each subsystem becomes a `ComponentResource` under `deploy/components/`, wired explicitly through constructors by a thin `__main__.py` orchestrator. Every wrapped resource keeps its exact current logical name and gets `pulumi.Alias(parent=pulumi.ROOT_STACK_RESOURCE)` so Pulumi re-parents in state with no cloud diff.

**Tech Stack:** Pulumi (Python) `>=3.165,<4`, `pulumi-gcp>=8.27,<9`, `pulumi-random>=4.16,<5`, `python-dotenv`, GCS-backed self-managed state.

## Global Constraints

- **Logical names are frozen.** The first positional arg of every `gcp.*` / `random.*` resource must stay byte-for-byte identical to the current `deploy/__main__.py` / `deploy/frontend_hosting.py`. This is what the aliases match on. The mixed `NAME`- vs `SLUG`-prefix scheme is preserved exactly, even where inconsistent.
- **Resource types are frozen.** Same constructors; components wrap, never substitute.
- **Every wrapped resource gets `aliases=[pulumi.Alias(parent=pulumi.ROOT_STACK_RESOURCE)]`** via the `child_opts()` helper. No exceptions.
- **Existing `depends_on` relationships are preserved** by threading them through `child_opts(..., depends_on=[...])`.
- **Stack output names are unchanged** (GitHub Actions `cd.yml` / `jobs.yml` consume them): `project_id`, `region`, `vpc_connector_id`, `cloud_run_service_account_email`, `github_cicd_service_account_email`, `db_instance_connection_name`, `artifact_registry_repo_url`, `static_media_bucket_name`, `gke_cluster_endpoint`, `gke_cluster_ca_cert`, `gke_worker_namespace`, `gke_worker_ksa`, `gke_worker_sa_email`, conditional `wif_provider`, and (gcs path) `frontend_url` / `frontend_lb_ip` / `frontend_bucket`.
- **`SLUG = "collateral_ai"`, `NAME = SLUG.replace("_", "-")`** semantics preserved.
- **Config surface unchanged:** same env var names + defaults as `deploy/env-template`. No changes to `Pulumi.yaml`, `Pulumi.prod.yaml`, or the GCS backend.
- **Hard gate:** the refactor is only complete when `pulumi preview` against the live `prod` stack shows **zero** create/replace/delete of real `gcp.*` resources (synthetic component nodes appearing as `+ create` is expected). Never `pulumi up` before that gate passes and the user approves.

**Component type-token convention:** `collateralai:infra:<ClassName>`. Component logical names are new synthetic names (`"apis"`, `"network"`, ...) and need no aliases.

**Per-component-task verification convention:** modules only *define* classes at import time (no resource instantiation), so the per-task gate is an import check run from `deploy/` with the stack venv:
`venv/bin/python -c "import components.<mod>"` → prints nothing, exit 0. Behavioral correctness is proven by the final preview gate (Task 13), not by mock-instantiating Pulumi resources.

---

### Task 1: Typed config object

**Files:**
- Create: `deploy/config.py`
- Test: `deploy/tests/test_config.py`
- Create: `deploy/tests/__init__.py` (empty)

**Interfaces:**
- Produces: `InfraConfig` frozen dataclass; classmethod `InfraConfig.from_env() -> InfraConfig`; property `.name -> str`; field `.slug = "collateral_ai"`. Fields (all consumed by later tasks): `project, region, subnet_ip, gke_pod_cidr, gke_svc_cidr, vpc_connector_cidr, vpc_connector_min_throughput:int, vpc_connector_max_throughput:int, db_name, db_user, db_password_length:int, sql_db_version, sql_edition, sql_instance_tier, sql_availability_type, sql_deletion_protection:bool, gke_master_authorized_cidr, gke_master_cidr, enable_payments:bool, enable_email:bool, resend_api_key_value, stripe_secret_key_value, stripe_webhook_secret_value, github_repo, bucket_cors_allowed_origins:list[str], frontend_hosting, domain, frontend_subdomain, dns_project, dns_zone`.

- [ ] **Step 1: Write the failing test**

```python
# deploy/tests/test_config.py
import os
import pytest
from config import InfraConfig


def test_from_env_coerces_and_defaults(monkeypatch):
    monkeypatch.setenv("GOOGLE_PROJECT", "proj-123")
    monkeypatch.setenv("SQL_DELETION_PROTECTION", "false")
    monkeypatch.setenv("VPC_CONNECTOR_MIN_THROUGHPUT", "250")
    monkeypatch.setenv("BUCKET_CORS_ALLOWED_ORIGINS", "http://a,http://b")
    cfg = InfraConfig.from_env()
    assert cfg.project == "proj-123"
    assert cfg.region == "us-central1"            # default
    assert cfg.sql_deletion_protection is False   # bool coercion
    assert cfg.vpc_connector_min_throughput == 250  # int coercion
    assert cfg.bucket_cors_allowed_origins == ["http://a", "http://b"]
    assert cfg.name == "collateral-ai"            # slug -> DNS-safe


def test_missing_required_project_raises(monkeypatch):
    monkeypatch.delenv("GOOGLE_PROJECT", raising=False)
    with pytest.raises(KeyError):
        InfraConfig.from_env()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd deploy && venv/bin/python -m pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'config'`
(If pytest is missing: `venv/bin/pip install pytest`.)

- [ ] **Step 3: Write minimal implementation**

```python
# deploy/config.py
"""Typed configuration for the Collateral AI Pulumi stack, parsed once from deploy/.env.

Centralizes every environment variable the stack reads. Same names + defaults as the
former inline os.environ.get() calls in __main__.py.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


def _bool(name: str, default: bool) -> bool:
    return os.environ.get(name, str(default)).lower() == "true"


def _int(name: str, default: int) -> int:
    return int(os.environ.get(name, str(default)))


@dataclass(frozen=True)
class InfraConfig:
    project: str
    region: str
    # networking
    subnet_ip: str
    gke_pod_cidr: str
    gke_svc_cidr: str
    vpc_connector_cidr: str
    vpc_connector_min_throughput: int
    vpc_connector_max_throughput: int
    # database
    db_name: str
    db_user: str
    db_password_length: int
    sql_db_version: str
    sql_edition: str
    sql_instance_tier: str
    sql_availability_type: str
    sql_deletion_protection: bool
    # gke
    gke_master_authorized_cidr: str
    gke_master_cidr: str
    # features
    enable_payments: bool
    enable_email: bool
    resend_api_key_value: str
    stripe_secret_key_value: str
    stripe_webhook_secret_value: str
    # ci / wif
    github_repo: str
    # storage
    bucket_cors_allowed_origins: list[str]
    # frontend hosting
    frontend_hosting: str
    domain: str
    frontend_subdomain: str
    dns_project: str
    dns_zone: str

    slug: str = "collateral_ai"

    @property
    def name(self) -> str:
        """DNS-safe name (GCP resource names disallow underscores)."""
        return self.slug.replace("_", "-")

    @classmethod
    def from_env(cls) -> "InfraConfig":
        load_dotenv()
        return cls(
            project=os.environ["GOOGLE_PROJECT"],
            region=os.environ.get("GOOGLE_REGION", "us-central1"),
            subnet_ip=os.environ.get("SUBNET_IP", "10.10.0.0/24"),
            gke_pod_cidr=os.environ.get("GKE_POD_CIDR", "10.20.0.0/16"),
            gke_svc_cidr=os.environ.get("GKE_SVC_CIDR", "10.30.0.0/20"),
            vpc_connector_cidr=os.environ.get("VPC_CONNECTOR_CIDR", "10.8.0.0/28"),
            vpc_connector_min_throughput=_int("VPC_CONNECTOR_MIN_THROUGHPUT", 200),
            vpc_connector_max_throughput=_int("VPC_CONNECTOR_MAX_THROUGHPUT", 300),
            db_name=os.environ.get("DB_NAME", "collateral_ai_db"),
            db_user=os.environ.get("DB_USER", "collateral_ai_user"),
            db_password_length=_int("DB_PASSWORD_LENGTH", 32),
            sql_db_version=os.environ.get("SQL_DB_VERSION", "POSTGRES_15"),
            sql_edition=os.environ.get("SQL_EDITION", "ENTERPRISE"),
            sql_instance_tier=os.environ.get("SQL_INSTANCE_TIER", "db-custom-1-3840"),
            sql_availability_type=os.environ.get("SQL_AVAILABILITY_TYPE", "ZONAL"),
            sql_deletion_protection=_bool("SQL_DELETION_PROTECTION", True),
            gke_master_authorized_cidr=os.environ.get("GKE_MASTER_AUTHORIZED_CIDR", "").strip(),
            gke_master_cidr=os.environ.get("GKE_MASTER_CIDR", "172.16.0.0/28"),
            enable_payments=_bool("ENABLE_PAYMENTS", True),
            enable_email=_bool("ENABLE_EMAIL", True),
            resend_api_key_value=os.environ.get("RESEND_API_KEY_VALUE", "REPLACE_ME"),
            stripe_secret_key_value=os.environ.get("STRIPE_SECRET_KEY_VALUE", "REPLACE_ME"),
            stripe_webhook_secret_value=os.environ.get("STRIPE_WEBHOOK_SECRET_VALUE", "REPLACE_ME"),
            github_repo=os.environ.get("GITHUB_REPO", "").strip(),
            bucket_cors_allowed_origins=os.environ.get(
                "BUCKET_CORS_ALLOWED_ORIGINS",
                "http://localhost:3000,https://collateralai.tinyfleet.dev",
            ).split(","),
            frontend_hosting=os.environ.get("FRONTEND_HOSTING", "cloudrun"),
            domain=os.environ.get("DOMAIN", ""),
            frontend_subdomain=os.environ.get("FRONTEND_SUBDOMAIN", "app"),
            dns_project=os.environ.get("DNS_PROJECT", ""),
            dns_zone=os.environ.get("DNS_ZONE", ""),
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd deploy && venv/bin/python -m pytest tests/test_config.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add deploy/config.py deploy/tests/__init__.py deploy/tests/test_config.py
git commit -m "refactor(deploy): add typed InfraConfig, centralize env parsing"
```

---

### Task 2: IAM + resource-option helpers

**Files:**
- Create: `deploy/_iam.py`
- Test: `deploy/tests/test_iam.py`

**Interfaces:**
- Produces: `child_opts(parent, *, depends_on=None) -> pulumi.ResourceOptions` (sets `parent`, `aliases=[pulumi.Alias(parent=pulumi.ROOT_STACK_RESOURCE)]`, `depends_on`). `bind_project_roles(prefix: str, project: str, sa, roles, *, parent=None) -> None` — one `gcp.projects.IAMMember` per role, named `f"{prefix}-{role.split('/')[-1]}"`, member `serviceAccount:{sa.email}`; when `parent` is set, children are aliased via `child_opts`.

- [ ] **Step 1: Write the failing test**

```python
# deploy/tests/test_iam.py
from unittest import mock

import pulumi
from _iam import child_opts


def test_child_opts_sets_root_stack_alias():
    sentinel = object()
    opts = child_opts(sentinel)
    assert opts.parent is sentinel
    assert len(opts.aliases) == 1
    # parent=ROOT_STACK_RESOURCE means "previously a root-stack resource"; name left as the
    # Ellipsis sentinel means "keep the current name".
    assert opts.aliases[0].parent is pulumi.ROOT_STACK_RESOURCE
    assert opts.aliases[0].name is ...


def test_child_opts_threads_depends_on():
    # ResourceOptions validates depends_on entries must be Resources; stand in with a mock.
    dep = mock.MagicMock(spec=pulumi.Resource)
    opts = child_opts(object(), depends_on=[dep])
    assert opts.depends_on == [dep]


def test_child_opts_defaults_depends_on_to_none():
    opts = child_opts(object())
    assert opts.depends_on is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd deploy && venv/bin/python -m pytest tests/test_iam.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named '_iam'`

- [ ] **Step 3: Write minimal implementation**

```python
# deploy/_iam.py
"""Shared IAM + resource-option helpers for the Pulumi stack."""
from __future__ import annotations

import pulumi
import pulumi_gcp as gcp


def child_opts(parent, *, depends_on=None) -> pulumi.ResourceOptions:
    """ResourceOptions for a resource moved under `parent`.

    The alias declares the resource was previously parented by the root stack, so re-parenting
    it under a ComponentResource is a state-only change (no replacement). `pulumi.ROOT_STACK_RESOURCE`
    is the SDK's self-descriptive spelling of "no original parent" (it is None); leaving the alias
    name unset keeps the same name. (The Go/TS `no_parent=True` flag has no Python equivalent.)
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd deploy && venv/bin/python -m pytest tests/test_iam.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add deploy/_iam.py deploy/tests/test_iam.py
git commit -m "refactor(deploy): add child_opts alias + bind_project_roles helpers"
```

---

### Task 3: ProjectApis component

**Files:**
- Create: `deploy/components/__init__.py` (empty)
- Create: `deploy/components/apis.py`

**Interfaces:**
- Consumes: `InfraConfig`.
- Produces: `ProjectApis(cfg)` with `.apis: dict[str, gcp.projects.Service]` keyed by short API name (`"run"`, `"compute"`, `"vpcaccess"`, `"servicenetworking"`, `"secretmanager"`, `"artifactregistry"`, `"container"`, `"storage"`, `"iam"`, ...).

- [ ] **Step 1: Write the implementation**

```python
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
```

- [ ] **Step 2: Verify the module imports**

Run: `cd deploy && venv/bin/python -c "import components.apis"`
Expected: exit 0, no output

- [ ] **Step 3: Commit**

```bash
git add deploy/components/__init__.py deploy/components/apis.py
git commit -m "refactor(deploy): extract ProjectApis component"
```

---

### Task 4: Network component

**Files:**
- Create: `deploy/components/network.py`

**Interfaces:**
- Consumes: `InfraConfig`, `ProjectApis`.
- Produces: `Network(cfg, apis)` with `.network`, `.subnet`, `.connector`, `.private_ip`, `.private_vpc_connection`.

- [ ] **Step 1: Write the implementation**

```python
# deploy/components/network.py
"""VPC, subnet (with GKE secondary ranges), Serverless VPC connector, and private
services access (peering range + connection) for Cloud SQL private IP."""
from __future__ import annotations

import pulumi
import pulumi_gcp as gcp

from _iam import child_opts
from components.apis import ProjectApis
from config import InfraConfig


class Network(pulumi.ComponentResource):
    def __init__(self, cfg: InfraConfig, apis: ProjectApis, opts=None):
        super().__init__("collateralai:infra:Network", "network", None, opts)

        self.network = gcp.compute.Network(
            f"{cfg.name}-network",
            auto_create_subnetworks=False,
            opts=child_opts(self, depends_on=[apis.apis["compute"]]),
        )
        self.subnet = gcp.compute.Subnetwork(
            f"{cfg.name}-subnet",
            network=self.network.id,
            ip_cidr_range=cfg.subnet_ip,
            region=cfg.region,
            # VPC-native secondary ranges GKE Autopilot allocates pods/services from.
            secondary_ip_ranges=[
                gcp.compute.SubnetworkSecondaryIpRangeArgs(
                    range_name="gke-pods", ip_cidr_range=cfg.gke_pod_cidr),
                gcp.compute.SubnetworkSecondaryIpRangeArgs(
                    range_name="gke-services", ip_cidr_range=cfg.gke_svc_cidr),
            ],
            opts=child_opts(self),
        )
        self.connector = gcp.vpcaccess.Connector(
            f"{cfg.name}-connector",
            # Deterministic name so CI (cd.yml / jobs.yml) can reference it.
            name=f"{cfg.name}-connector",
            region=cfg.region,
            network=self.network.name,
            ip_cidr_range=cfg.vpc_connector_cidr,
            min_throughput=cfg.vpc_connector_min_throughput,
            max_throughput=cfg.vpc_connector_max_throughput,
            opts=child_opts(self, depends_on=[apis.apis["vpcaccess"]]),
        )
        self.private_ip = gcp.compute.GlobalAddress(
            f"{cfg.name}-private-ip",
            purpose="VPC_PEERING",
            address_type="INTERNAL",
            prefix_length=16,
            network=self.network.id,
            opts=child_opts(self),
        )
        self.private_vpc_connection = gcp.servicenetworking.Connection(
            f"{cfg.slug}-private-vpc",
            network=self.network.id,
            service="servicenetworking.googleapis.com",
            reserved_peering_ranges=[self.private_ip.name],
            opts=child_opts(self, depends_on=[apis.apis["servicenetworking"]]),
        )
        self.register_outputs({})
```

- [ ] **Step 2: Verify the module imports**

Run: `cd deploy && venv/bin/python -c "import components.network"`
Expected: exit 0, no output

- [ ] **Step 3: Commit**

```bash
git add deploy/components/network.py
git commit -m "refactor(deploy): extract Network component"
```

---

### Task 5: Database component

**Files:**
- Create: `deploy/components/database.py`

**Interfaces:**
- Consumes: `InfraConfig`, `Network`.
- Produces: `Database(cfg, network)` with `.password` (`random.RandomPassword`), `.instance` (`gcp.sql.DatabaseInstance`), `.socket_url` (`pulumi.Output[str]`, Cloud SQL unix-socket URL), `.private_url` (`pulumi.Output[str]`, private-IP URL for GKE pods).

- [ ] **Step 1: Write the implementation**

```python
# deploy/components/database.py
"""Cloud SQL (Postgres, private IP): random password, instance, database, user, and the
two connection URLs the app uses (unix socket for Cloud Run, private IP for GKE pods)."""
from __future__ import annotations

import pulumi
import pulumi_gcp as gcp
import pulumi_random as random

from _iam import child_opts
from components.network import Network
from config import InfraConfig


class Database(pulumi.ComponentResource):
    def __init__(self, cfg: InfraConfig, network: Network, opts=None):
        super().__init__("collateralai:infra:Database", "database", None, opts)

        self.password = random.RandomPassword(
            f"{cfg.slug}-db-password",
            length=cfg.db_password_length,
            special=False,
            opts=child_opts(self),
        )
        self.instance = gcp.sql.DatabaseInstance(
            f"{cfg.name}-sql",
            database_version=cfg.sql_db_version,
            region=cfg.region,
            deletion_protection=cfg.sql_deletion_protection,
            settings=gcp.sql.DatabaseInstanceSettingsArgs(
                edition=cfg.sql_edition,
                tier=cfg.sql_instance_tier,
                availability_type=cfg.sql_availability_type,
                disk_type="PD_SSD",
                disk_size=20,
                disk_autoresize=True,
                ip_configuration=gcp.sql.DatabaseInstanceSettingsIpConfigurationArgs(
                    ipv4_enabled=False,
                    private_network=network.network.id,
                ),
                backup_configuration=gcp.sql.DatabaseInstanceSettingsBackupConfigurationArgs(
                    enabled=True,
                    point_in_time_recovery_enabled=True,
                ),
            ),
            opts=child_opts(self, depends_on=[network.private_vpc_connection]),
        )
        gcp.sql.Database(
            f"{cfg.slug}-database",
            instance=self.instance.name,
            name=cfg.db_name,
            opts=child_opts(self),
        )
        gcp.sql.User(
            f"{cfg.slug}-db-user",
            instance=self.instance.name,
            name=cfg.db_user,
            password=self.password.result,
            opts=child_opts(self),
        )

        self.socket_url = pulumi.Output.all(
            self.password.result, self.instance.connection_name
        ).apply(lambda a: f"postgres://{cfg.db_user}:{a[0]}@/{cfg.db_name}?host=/cloudsql/{a[1]}")
        self.private_url = pulumi.Output.all(
            self.password.result, self.instance.private_ip_address
        ).apply(lambda a: f"postgres://{cfg.db_user}:{a[0]}@{a[1]}:5432/{cfg.db_name}")
        self.register_outputs({})
```

- [ ] **Step 2: Verify the module imports**

Run: `cd deploy && venv/bin/python -c "import components.database"`
Expected: exit 0, no output

- [ ] **Step 3: Commit**

```bash
git add deploy/components/database.py
git commit -m "refactor(deploy): extract Database component"
```

---

### Task 6: SecretStore component

**Files:**
- Create: `deploy/components/secrets.py`

**Interfaces:**
- Consumes: `InfraConfig`, `ProjectApis`.
- Produces: `SecretStore(cfg, apis)` with `.add(name: str, value: pulumi.Input[str]) -> gcp.secretmanager.Secret` (creates the Secret named `name` + a `f"{name}-v1"` SecretVersion) and `.secrets: dict[str, gcp.secretmanager.Secret]` accumulating every added secret.

- [ ] **Step 1: Write the implementation**

```python
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
```

- [ ] **Step 2: Verify the module imports**

Run: `cd deploy && venv/bin/python -c "import components.secrets"`
Expected: exit 0, no output

- [ ] **Step 3: Commit**

```bash
git add deploy/components/secrets.py
git commit -m "refactor(deploy): extract SecretStore component"
```

---

### Task 7: ArtifactRegistry + StaticMediaBucket components

**Files:**
- Create: `deploy/components/registry.py`
- Create: `deploy/components/storage.py`

**Interfaces:**
- Consumes: `InfraConfig`, `ProjectApis`.
- Produces: `ArtifactRegistry(cfg, apis)` with `.repo` (`gcp.artifactregistry.Repository`); `StaticMediaBucket(cfg, apis)` with `.bucket` (`gcp.storage.Bucket`).

- [ ] **Step 1: Write the registry implementation**

```python
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
```

- [ ] **Step 2: Write the storage implementation**

```python
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
            cors=[gcp.storage.BucketCorArgs(
                origins=cfg.bucket_cors_allowed_origins,
                methods=["GET", "PUT", "POST", "DELETE"],
                response_headers=["Content-Type", "Authorization"],
                max_age_seconds=3600,
            )],
            opts=child_opts(self, depends_on=[apis.apis["storage"]]),
        )
        self.register_outputs({})
```

- [ ] **Step 3: Verify both modules import**

Run: `cd deploy && venv/bin/python -c "import components.registry, components.storage"`
Expected: exit 0, no output

- [ ] **Step 4: Commit**

```bash
git add deploy/components/registry.py deploy/components/storage.py
git commit -m "refactor(deploy): extract ArtifactRegistry + StaticMediaBucket components"
```

---

### Task 8: WorkerCluster component (GKE Autopilot + worker identity)

**Files:**
- Create: `deploy/components/workers.py`

**Interfaces:**
- Consumes: `InfraConfig`, `ProjectApis`, `Network`, `ArtifactRegistry`.
- Produces: `WorkerCluster(cfg, apis, network, registry)` with `.cluster` (`gcp.container.Cluster`), `.worker_sa` (`gcp.serviceaccount.Account`). Reads `network.network`, `network.subnet`, `network.private_vpc_connection`, `registry.repo`.

- [ ] **Step 1: Write the implementation**

```python
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

        authorized = cfg.gke_master_authorized_cidr
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
                enable_private_nodes=True,
                enable_private_endpoint=False,
                master_ipv4_cidr_block=cfg.gke_master_cidr,
                master_global_access_config=gcp.container.ClusterPrivateClusterConfigMasterGlobalAccessConfigArgs(
                    enabled=True,
                ),
            ),
            master_authorized_networks_config=gcp.container.ClusterMasterAuthorizedNetworksConfigArgs(
                cidr_blocks=(
                    [gcp.container.ClusterMasterAuthorizedNetworksConfigCidrBlockArgs(
                        cidr_block=authorized, display_name="operator-ci")]
                    if authorized else []
                ),
            ),
            release_channel=gcp.container.ClusterReleaseChannelArgs(channel="REGULAR"),
            deletion_protection=False,
            opts=child_opts(self, depends_on=[apis.apis["container"], network.private_vpc_connection]),
        )

        # Least-privilege GSA for worker pods (Vertex + GCS; DB is private IP + password).
        self.worker_sa = gcp.serviceaccount.Account(
            f"{cfg.slug}-gke-worker-sa",
            account_id="gke-worker-sa",
            display_name="GKE worker pods",
            opts=child_opts(self),
        )
        bind_project_roles(
            f"{cfg.slug}-worker", cfg.project, self.worker_sa, WORKER_ROLES, parent=self,
        )

        # Workload Identity: bind the in-cluster KSA workers/worker to the worker GSA.
        # depends_on the cluster: the PROJECT.svc.id.goog identity pool only exists once a
        # Workload-Identity-enabled cluster is created.
        gcp.serviceaccount.IAMMember(
            f"{cfg.slug}-worker-wi",
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
```

- [ ] **Step 2: Verify the module imports**

Run: `cd deploy && venv/bin/python -c "import components.workers"`
Expected: exit 0, no output

- [ ] **Step 3: Commit**

```bash
git add deploy/components/workers.py
git commit -m "refactor(deploy): extract WorkerCluster component"
```

---

### Task 9: RuntimeIdentity + CicdIdentity components

**Files:**
- Create: `deploy/components/identities.py`

**Interfaces:**
- Consumes: `InfraConfig`, `ProjectApis`.
- Produces: `RuntimeIdentity(cfg)` with `.sa` (`gcp.serviceaccount.Account`, `cloud-run-sa`); `CicdIdentity(cfg, apis)` with `.sa` (`gcp.serviceaccount.Account`, `github-cicd-sa`) and `.wif_provider_name: pulumi.Output[str] | None` (the WIF provider resource name, or `None` when `cfg.github_repo` is blank).

- [ ] **Step 1: Write the implementation**

```python
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
```

- [ ] **Step 2: Verify the module imports**

Run: `cd deploy && venv/bin/python -c "import components.identities"`
Expected: exit 0, no output

- [ ] **Step 3: Commit**

```bash
git add deploy/components/identities.py
git commit -m "refactor(deploy): extract RuntimeIdentity + CicdIdentity components"
```

---

### Task 10: FrontendCdn component (from frontend_hosting.py)

**Files:**
- Create: `deploy/components/frontend_cdn.py`
- (Deletion of `deploy/frontend_hosting.py` happens in Task 11, when the last caller is removed.)

**Interfaces:**
- Consumes: `InfraConfig`, `ProjectApis`. Only instantiated when `cfg.frontend_hosting == "gcs"` and `cfg.domain`/`cfg.dns_project`/`cfg.dns_zone` are set.
- Produces: `FrontendCdn(cfg, apis)` with `.site` (`gcp.storage.Bucket`); registers exports `frontend_url`, `frontend_lb_ip`, `frontend_bucket`.

- [ ] **Step 1: Write the implementation** (1:1 port of `frontend_hosting.provision_frontend_cdn`, same logical names, now aliased children of the component; the `depends_on=[apis.apis["compute"], apis.apis["storage"]]` from the caller is applied to the hosting bucket as before)

```python
# deploy/components/frontend_cdn.py
"""React SPA hosting: GCS website bucket + Cloud CDN behind an external HTTPS ALB with a
Google-managed cert, plus the DNS A record in a SEPARATE shared-infra project (2nd provider).
Only used when FRONTEND_HOSTING=gcs; Next.js (SSR) stays on Cloud Run and skips this."""
from __future__ import annotations

import pulumi
import pulumi_gcp as gcp

from _iam import child_opts
from components.apis import ProjectApis
from config import InfraConfig


class FrontendCdn(pulumi.ComponentResource):
    def __init__(self, cfg: InfraConfig, apis: ProjectApis, opts=None):
        super().__init__("collateralai:infra:FrontendCdn", "frontend-cdn", None, opts)
        name = cfg.name
        host = f"{cfg.frontend_subdomain}.{cfg.domain}" if cfg.frontend_subdomain else cfg.domain
        bucket_dep = [apis.apis["compute"], apis.apis["storage"]]

        # 1. SPA hosting bucket (index.html fallback for client-side routes; public-read).
        self.site = gcp.storage.Bucket(
            f"{name}-frontend",
            name=f"{cfg.project}-{name}-frontend",
            location=cfg.region,
            uniform_bucket_level_access=True,
            force_destroy=True,
            website=gcp.storage.BucketWebsiteArgs(
                main_page_suffix="index.html", not_found_page="index.html"),
            opts=child_opts(self, depends_on=bucket_dep),
        )
        gcp.storage.BucketIAMMember(
            f"{name}-frontend-public",
            bucket=self.site.name,
            role="roles/storage.objectViewer",
            member="allUsers",
            opts=child_opts(self),
        )

        # 2. Backend bucket with Cloud CDN.
        backend_bucket = gcp.compute.BackendBucket(
            f"{name}-frontend-bb",
            bucket_name=self.site.name,
            enable_cdn=True,
            cdn_policy=gcp.compute.BackendBucketCdnPolicyArgs(
                cache_mode="CACHE_ALL_STATIC", client_ttl=3600, default_ttl=3600, max_ttl=86400),
            opts=child_opts(self),
        )

        # 3. URL map → CDN backend bucket. Deterministic name so CI can invalidate by name.
        url_map = gcp.compute.URLMap(
            f"{name}-frontend-urlmap",
            name=f"{name}-frontend-urlmap",
            default_service=backend_bucket.id,
            opts=child_opts(self),
        )

        # 4. Google-managed SSL cert (provisions once DNS resolves to the LB IP).
        cert = gcp.compute.ManagedSslCertificate(
            f"{name}-frontend-cert",
            managed=gcp.compute.ManagedSslCertificateManagedArgs(domains=[host]),
            opts=child_opts(self),
        )

        # 5. Global static IP + HTTPS proxy + forwarding rule.
        ip = gcp.compute.GlobalAddress(f"{name}-frontend-ip", opts=child_opts(self))
        https_proxy = gcp.compute.TargetHttpsProxy(
            f"{name}-frontend-https-proxy",
            url_map=url_map.id, ssl_certificates=[cert.id],
            opts=child_opts(self),
        )
        gcp.compute.GlobalForwardingRule(
            f"{name}-frontend-https-fr",
            target=https_proxy.id, ip_address=ip.address, port_range="443",
            load_balancing_scheme="EXTERNAL_MANAGED",
            opts=child_opts(self),
        )

        # 5b. HTTP → HTTPS redirect.
        redirect_map = gcp.compute.URLMap(
            f"{name}-frontend-redirect",
            default_url_redirect=gcp.compute.URLMapDefaultUrlRedirectArgs(
                https_redirect=True, strip_query=False,
                redirect_response_code="MOVED_PERMANENTLY_DEFAULT"),
            opts=child_opts(self),
        )
        http_proxy = gcp.compute.TargetHttpProxy(
            f"{name}-frontend-http-proxy", url_map=redirect_map.id, opts=child_opts(self))
        gcp.compute.GlobalForwardingRule(
            f"{name}-frontend-http-fr",
            target=http_proxy.id, ip_address=ip.address, port_range="80",
            load_balancing_scheme="EXTERNAL_MANAGED",
            opts=child_opts(self),
        )

        # 6. DNS A record in the SHARED-infra project (its own provider).
        dns_provider = gcp.Provider(
            f"{name}-dns-provider", project=cfg.dns_project, opts=pulumi.ResourceOptions(parent=self))
        gcp.dns.RecordSet(
            f"{name}-frontend-dns",
            name=f"{host}.",
            type="A", ttl=300, managed_zone=cfg.dns_zone,
            rrdatas=[ip.address], project=cfg.dns_project,
            opts=pulumi.ResourceOptions(
                parent=self, provider=dns_provider, aliases=[pulumi.Alias(parent=pulumi.ROOT_STACK_RESOURCE)]),
        )

        pulumi.export("frontend_url", f"https://{host}")
        pulumi.export("frontend_lb_ip", ip.address)
        pulumi.export("frontend_bucket", self.site.name)
        self.register_outputs({})
```

> **Note on `{name}-dns-provider`:** it is a `pulumi.Provider`, not a cloud resource, but it *is* tracked in state and was previously root-parented, so it also carries the re-parent. Providers may not re-parent cleanly in all SDK versions — if the Task 13 preview shows the provider as replace/create, drop the alias for it (a provider replacement has no cloud effect) or set `parent=self` only. Resolve empirically against the preview.

- [ ] **Step 2: Verify the module imports**

Run: `cd deploy && venv/bin/python -c "import components.frontend_cdn"`
Expected: exit 0, no output

- [ ] **Step 3: Commit**

```bash
git add deploy/components/frontend_cdn.py
git commit -m "refactor(deploy): port frontend CDN to FrontendCdn component"
```

---

### Task 11: Orchestrator (`__main__.py`) rewrite

**Files:**
- Modify (full rewrite): `deploy/__main__.py`
- Delete: `deploy/frontend_hosting.py`

**Interfaces:**
- Consumes: every component from Tasks 3–10 and `InfraConfig`.
- Produces: the stack itself + all exports (names per Global Constraints).

- [ ] **Step 1: Replace `deploy/__main__.py` with the orchestrator**

```python
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
```

> **Ordering note:** `django_secret_key` and `database-url-private` retain their original creation order relative to the other secrets. The `django-secret-key` RandomPassword logical name (`{slug}-django-secret`) and the `database-url-private` secret name are unchanged, so no alias is needed for the RandomPassword (it stays root-parented — created here in `__main__`, exactly as before) and the secret is aliased by SecretStore.

- [ ] **Step 2: Delete the obsolete module**

```bash
git rm deploy/frontend_hosting.py
```

- [ ] **Step 3: Verify the orchestrator imports**

Run: `cd deploy && venv/bin/python -c "import __main__"`
Expected: FAILS only if run outside a Pulumi context (resource construction needs the monitor). To parse-check without a monitor instead run:
`cd deploy && venv/bin/python -c "import ast; ast.parse(open('__main__.py').read()); print('parsed')"`
Expected: `parsed`

- [ ] **Step 4: Commit**

```bash
git add deploy/__main__.py
git commit -m "refactor(deploy): thin orchestrator over components; drop frontend_hosting.py"
```

---

### Task 12: Update env-template comment + docs cross-check

**Files:**
- Modify: `deploy/env-template` (only if any comment references `__main__.py` internals; otherwise no-op)

**Interfaces:** none (documentation only).

- [ ] **Step 1: Grep for stale references to the old structure**

Run: `grep -rn "frontend_hosting\|provision_frontend_cdn\|make_secret" deploy/ --include=*.md --include=env-template --include=*.sh`
Expected: any hit in `env-template`/`*.sh`/`*.md` that names the removed function or module is stale. `env-template` uses only env var names (no code refs) so likely zero hits — in which case this task is a no-op and you skip the commit.

- [ ] **Step 2: Fix any stale reference found** (edit the specific line to describe the new structure; only if Step 1 produced hits)

- [ ] **Step 3: Commit (only if changed)**

```bash
git add deploy/env-template && git commit -m "docs(deploy): fix stale references after component refactor"
```

---

### Task 13: State-safety gate — `pulumi preview` (zero-replace)

**Files:** none (verification).

**Interfaces:** none.

> **This is the hard gate. Do not `pulumi up`. This step needs the operator's GCP credentials + access to the `gs://collateralai-501708-pulumi-state` backend. If those are not available in-session, STOP and hand the exact commands to the user to run, then review the output together.**

- [ ] **Step 1: Select the stack**

Run: `cd deploy && pulumi stack select prod`
Expected: stack selected (auth via `gcloud auth application-default login` if prompted).

- [ ] **Step 2: Run preview with detail**

Run: `cd deploy && pulumi preview --diff 2>&1 | tee /tmp/pulumi-preview.txt`

- [ ] **Step 3: Assert zero destructive changes**

Run: `grep -E "replace|delete|\bcreate\b" /tmp/pulumi-preview.txt | grep -viE "collateralai:infra:" | grep -vi "unchanged"`
Expected: **no lines** referencing any `gcp:*` or `random:*` resource under create/replace/delete. The only creates allowed are the synthetic `collateralai:infra:*` component nodes (which the filter excludes). The summary line should read like `Resources: NN unchanged` (plus `+ M to create` where all M are `collateralai:infra:*` components).

- [ ] **Step 4: If any real resource shows replace/delete — DO NOT PROCEED**

Diagnose: (a) a logical name drifted from the original — diff against `git show HEAD~N:deploy/__main__.py`; (b) a missing `child_opts` alias; (c) the `{name}-dns-provider` provider (see Task 10 note). Fix the offending module, re-run Step 2. Only a clean preview clears the gate.

- [ ] **Step 5: Record the result**

Paste the `Resources:` summary line into the PR description / hand it to the user. No commit (verification only). Await user approval before any `pulumi up`.

---

## Self-Review

**Spec coverage:**
- File layout (config.py, _iam.py, components/*) → Tasks 1–11. ✓
- Alias safety mechanism (`child_opts` / `Alias(parent=ROOT_STACK_RESOURCE)`) → Task 2, applied in every component. ✓
- Config object killing scattered `os.environ.get` → Task 1. ✓
- Component interfaces table (ProjectApis…FrontendCdn) → Tasks 3–10, matching exposed attributes. ✓
- IAM dedup (`bind_project_roles`) → Task 2, used in Tasks 8–9. ✓
- Thin `__main__.py`, unchanged export names → Task 11. ✓
- `frontend_cdn` conversion → Task 10; old module deleted → Task 11. ✓
- Verification / zero-replace gate → Task 13. ✓
- Ordering subtlety for `database-url-private` → Task 11 note. ✓

**Placeholder scan:** No TBD/TODO; every code step shows full code; the only conditional-skip tasks (12) state the skip condition explicitly. ✓

**Type/name consistency:** `child_opts` / `bind_project_roles` signatures match between Task 2 and all callers. Component attribute names (`network.network`, `network.subnet`, `registry.repo`, `database.socket_url`/`private_url`, `runtime.sa`, `cicd.sa`/`wif_provider_name`, `workers.cluster`/`worker_sa`, `bucket.bucket`, `apis.apis`) are consistent across producer and consumer tasks. Export names verified against the current `__main__.py`. ✓

**Known empirical unknowns flagged inline:** `pulumi.Alias(parent=pulumi.ROOT_STACK_RESOURCE)` exact behavior and the `{name}-dns-provider` provider alias — both are gated by the Task 13 preview, which is the source of truth.
