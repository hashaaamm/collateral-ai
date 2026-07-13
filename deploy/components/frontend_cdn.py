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

        # 6. DNS A record in the SHARED-infra project, written through its own provider.
        dns_provider = gcp.Provider(
            f"{name}-dns-provider", project=cfg.dns_project,
            opts=pulumi.ResourceOptions(parent=self))
        gcp.dns.RecordSet(
            f"{name}-frontend-dns",
            name=f"{host}.",
            type="A", ttl=300, managed_zone=cfg.dns_zone,
            rrdatas=[ip.address], project=cfg.dns_project,
            opts=pulumi.ResourceOptions(parent=self, provider=dns_provider),
        )

        pulumi.export("frontend_url", f"https://{host}")
        pulumi.export("frontend_lb_ip", ip.address)
        pulumi.export("frontend_bucket", self.site.name)
        self.register_outputs({})
