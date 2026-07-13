# Pulumi infra refactor: ComponentResource + state-preserving aliases

Date: 2026-07-13
Status: Approved (design)

## Goal

Refactor `deploy/__main__.py` (a ~400-line procedural script) and
`deploy/frontend_hosting.py` into an idiomatic Pulumi layout built on
`pulumi.ComponentResource` classes, improving readability and encapsulation.

This is a **structure-only** change. It provisions the exact same GCP resources
with the same names, configuration, and stack outputs. The live prod stack must
be untouched: `pulumi preview` must show **zero** creates, replacements, or
deletions of real cloud resources.

## Non-goals

- No change to which resources exist, their settings, sizing, or CORS/IAM policy.
- No change to stack output names (GitHub Actions `cd.yml` / `jobs.yml` consume them).
- No change to `Pulumi.yaml`, `Pulumi.prod.yaml`, the GCS state backend, or the
  `deploy/.env` / `env-template` config surface (same env var names + defaults).
- No unrelated refactoring of CI workflows, backend, or frontend code.

## The safety mechanism: aliases

Wrapping existing top-level resources in a `ComponentResource` changes each
resource's **URN** (the URN encodes the parent path). Without mitigation Pulumi
reads a URN change as delete-old + create-new — catastrophic for Cloud SQL (data),
the GKE cluster, and VPC peering.

Every resource in this stack is currently a **root-stack** resource (no explicit
parent). So the fix is uniform: when a resource moves under a component parent,
give it an alias declaring it previously had no parent:

```python
opts=pulumi.ResourceOptions(parent=self, aliases=[pulumi.Alias(no_parent=True)])
```

Pulumi matches the alias by (logical name + type) and re-parents the resource in
state as a **state-only** change — no cloud diff.

Hard constraints that make aliasing work:

1. **Logical names are frozen.** The first positional arg of every resource must
   remain byte-for-byte identical to today (e.g. `f"{NAME}-network"`,
   `f"{SLUG}-db-password"`, `"api-run"`). The name mix of `NAME`- vs `SLUG`-
   prefixes is preserved exactly, even where inconsistent.
2. **Resource types are frozen.** Same `gcp.*` constructors — a component wraps,
   it does not substitute.
3. A shared helper injects the alias so it can't be forgotten per-resource:

```python
# _iam.py
def child_opts(parent, *, depends_on=None):
    return pulumi.ResourceOptions(
        parent=parent,
        aliases=[pulumi.Alias(no_parent=True)],
        depends_on=depends_on,
    )
```

The synthetic ComponentResource nodes themselves appear as `+ create` in preview.
They have no provider and no cloud effect — that is expected and safe.

## File layout

```
deploy/
  __main__.py          # thin orchestrator: config -> components -> exports
  config.py            # InfraConfig dataclass; all env parsing
  _iam.py              # bind_project_roles(), child_opts()
  components/
    __init__.py
    apis.py            # ProjectApis
    network.py         # Network
    database.py        # Database
    secrets.py         # SecretStore
    registry.py        # ArtifactRegistry
    workers.py         # WorkerCluster
    identities.py      # RuntimeIdentity, CicdIdentity
    storage.py         # StaticMediaBucket
    frontend_cdn.py    # FrontendCdn (was frontend_hosting.py)
```

## Config object

Replaces the ~35 scattered `os.environ.get(...)` calls with one typed, frozen
dataclass. Same env var names, same defaults, same bool/int coercion rules.

```python
@dataclass(frozen=True)
class InfraConfig:
    project: str
    region: str
    slug: str = "collateral_ai"
    db_name: str = ...
    db_user: str = ...
    # networking, sql sizing, gke cidrs, feature flags, frontend hosting, secret seeds ...
    enable_payments: bool = True
    enable_email: bool = True
    github_repo: str = ""
    frontend_hosting: str = "cloudrun"

    @property
    def name(self) -> str:
        return self.slug.replace("_", "-")

    @classmethod
    def from_env(cls) -> "InfraConfig":
        load_dotenv()
        # centralized parsing: os.environ["GOOGLE_PROJECT"], .get with defaults,
        # _bool()/_int() helpers for coercion
        ...
```

`SLUG = "collateral_ai"` and `NAME = SLUG.replace("_", "-")` semantics are kept.

## Component interfaces

Each component is a `pulumi.ComponentResource` with type token
`collateralai:infra:<Name>`, registers its outputs via
`self.register_outputs({...})`, and exposes typed attributes. Dependencies are
passed **in** through the constructor (explicit wiring, no globals).

| Component | Constructor inputs | Exposes | Wraps (logical names unchanged) |
|---|---|---|---|
| `ProjectApis` | cfg | `.apis` (dict name->Service) | `api-{name}` for the 11 required APIs |
| `Network` | cfg, apis | `.network`, `.subnet`, `.connector`, `.private_vpc_connection`, `.private_ip` | `{NAME}-network`, `{NAME}-subnet`, `{NAME}-connector`, `{NAME}-private-ip`, `{SLUG}-private-vpc` |
| `Database` | cfg, network | `.instance`, `.password`, `.socket_url`, `.private_url` | `{SLUG}-db-password`, `{NAME}-sql`, `{SLUG}-database`, `{SLUG}-db-user` |
| `SecretStore` | cfg, apis; `.add(name, value)` | `.secrets` (dict) | existing `make_secret` names + `{name}-v1` versions |
| `ArtifactRegistry` | cfg, apis | `.repo` | `{NAME}-repo` |
| `WorkerCluster` | cfg, apis, network, repo (reads `network.subnet`) | `.cluster`, `.worker_sa` | `{NAME}-autopilot`, `{SLUG}-gke-worker-sa`, worker role members, `{SLUG}-worker-wi`, `{NAME}-node-ar-reader` |
| `RuntimeIdentity` | cfg | `.sa` | `{SLUG}-run-sa`, `{SLUG}-run-*` role members, `{SLUG}-run-sa-token-creator` |
| `CicdIdentity` | cfg, apis | `.sa`, `.wif_provider_name` | `{SLUG}-cicd-sa`, `{SLUG}-cicd-*` roles, `{NAME}-gh-pool`, `{NAME}-gh-provider`, `{NAME}-cicd-wif-binding` |
| `StaticMediaBucket` | cfg, apis | `.bucket` | `{NAME}-static-media` |
| `FrontendCdn` | cfg, apis (gated) | `.site`, exports | all `{NAME}-frontend-*` names + DNS provider/record |

### IAM dedup

The four copy-pasted role loops collapse to:

```python
def bind_project_roles(prefix, project, sa, roles):
    for role in roles:
        gcp.projects.IAMMember(
            f"{prefix}-{role.split('/')[-1]}",
            project=project, role=role,
            member=sa.email.apply(lambda e: f"serviceAccount:{e}"),
        )
```

Member-resource logical names (`{SLUG}-run-<rolebasename>` etc.) are unchanged.

## Orchestrator (`__main__.py`)

~40 lines. Dependency order preserved from today:

```python
cfg  = InfraConfig.from_env()
apis = ProjectApis(cfg)
net  = Network(cfg, apis)
db   = Database(cfg, net)
secrets = SecretStore(cfg, apis)
secrets.add("database-url", db.socket_url)
secrets.add("django-secret-key", ...)
# feature-gated resend/stripe secrets
repo    = ArtifactRegistry(cfg, apis)
workers = WorkerCluster(cfg, apis, net, repo)
secrets.add("database-url-private", db.private_url)
bucket  = StaticMediaBucket(cfg, apis)
runtime = RuntimeIdentity(cfg)
cicd    = CicdIdentity(cfg, apis)
if cfg.frontend_hosting == "gcs" and cfg.domain and cfg.dns_project and cfg.dns_zone:
    FrontendCdn(cfg, apis)
# pulumi.export(...) block — identical output names to today
```

Note the ordering subtlety preserved: `database-url-private` secret is added after
the worker section today; the sequence above keeps the same logical grouping while
the actual dependency is only on `db`. Export names (`project_id`, `region`,
`vpc_connector_id`, `cloud_run_service_account_email`,
`github_cicd_service_account_email`, `db_instance_connection_name`,
`artifact_registry_repo_url`, `static_media_bucket_name`, `gke_cluster_endpoint`,
`gke_cluster_ca_cert`, `gke_worker_namespace`, `gke_worker_ksa`,
`gke_worker_sa_email`, and conditional `wif_provider`) are unchanged.

## Verification (the gate before any apply)

1. `pip install -r deploy/requirements.txt` into the venv; `python -c "import __main__"`
   style import/parse check is not meaningful for Pulumi — use preview instead.
2. Run `pulumi preview` (or the `gcp-fullstack:infra-up` skill's preview) against
   the live `prod` stack in the GCS backend.
3. **Pass criteria:** the plan shows only unchanged real resources plus the new
   synthetic component nodes. **Zero** `replace`, `create` (of gcp.* resources),
   or `delete`. If any real resource shows replace/delete, an alias is missing or a
   logical name drifted — fix before proceeding.
4. Requires the operator's GCP credentials + state backend access. If unavailable
   in-session, produce the command and review the preview output together. **Do not
   `pulumi up` until the preview is clean and the user approves.**

## Risks

- **Alias miss / name drift** → destructive replace. Mitigated by the `child_opts`
  helper, frozen-name constraint, and the mandatory clean-preview gate.
- **`pulumi.Alias(no_parent=True)` semantics** must be confirmed against the pinned
  `pulumi>=3.165` SDK during implementation (it is the documented "was root-stack"
  form). Verified empirically by the preview showing re-parent-only diffs.
- **Import layout** — `deploy/` runs with `virtualenv: venv` and `__main__.py` as
  entrypoint; `components/` must import cleanly as a package (add `__init__.py`).
