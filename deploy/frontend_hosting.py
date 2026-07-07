"""Frontend hosting for a React SPA: GCS bucket + Cloud CDN behind an external HTTPS Application
Load Balancer with a Google-managed SSL cert, and the DNS A record in a SEPARATE (shared-infra)
project. Only used when FRONTEND_HOSTING=gcs and a domain + DNS project/zone are configured;
Next.js (SSR) stays on Cloud Run and does not use this.
"""

import pulumi
import pulumi_gcp as gcp


def provision_frontend_cdn(*, name, project, region, domain, subdomain, dns_project, dns_zone, depends_on):
    """Provision the SPA hosting + LB + CDN + managed cert, and the A record in the shared DNS project.

    Returns the hosting bucket. Exports frontend_url / frontend_lb_ip / frontend_bucket.
    """
    host = f"{subdomain}.{domain}" if subdomain else domain  # e.g. app.tinyfleet.dev

    # 1. SPA hosting bucket. Website config makes it serve index.html and fall back to index.html
    #    for client-side routes (SPA deep links). Objects are public-read (static site content).
    site = gcp.storage.Bucket(
        f"{name}-frontend",
        name=f"{project}-{name}-frontend",
        location=region,
        uniform_bucket_level_access=True,
        force_destroy=True,
        website=gcp.storage.BucketWebsiteArgs(
            main_page_suffix="index.html",
            not_found_page="index.html",
        ),
        opts=pulumi.ResourceOptions(depends_on=depends_on),
    )
    gcp.storage.BucketIAMMember(
        f"{name}-frontend-public",
        bucket=site.name,
        role="roles/storage.objectViewer",
        member="allUsers",
    )

    # 2. Backend bucket with Cloud CDN.
    backend_bucket = gcp.compute.BackendBucket(
        f"{name}-frontend-bb",
        bucket_name=site.name,
        enable_cdn=True,
        cdn_policy=gcp.compute.BackendBucketCdnPolicyArgs(
            cache_mode="CACHE_ALL_STATIC",
            client_ttl=3600,
            default_ttl=3600,
            max_ttl=86400,
        ),
    )

    # 3. URL map → the CDN backend bucket. Deterministic name so CI can invalidate it by name
    #    (cd.yml references collateral-ai-frontend-urlmap).
    url_map = gcp.compute.URLMap(
        f"{name}-frontend-urlmap", name=f"{name}-frontend-urlmap", default_service=backend_bucket.id
    )

    # 4. Google-managed SSL cert for the host (provisions once DNS resolves to the LB IP).
    cert = gcp.compute.ManagedSslCertificate(
        f"{name}-frontend-cert",
        managed=gcp.compute.ManagedSslCertificateManagedArgs(domains=[host]),
    )

    # 5. Global static IP + HTTPS proxy + forwarding rule.
    ip = gcp.compute.GlobalAddress(f"{name}-frontend-ip")
    https_proxy = gcp.compute.TargetHttpsProxy(
        f"{name}-frontend-https-proxy", url_map=url_map.id, ssl_certificates=[cert.id]
    )
    gcp.compute.GlobalForwardingRule(
        f"{name}-frontend-https-fr",
        target=https_proxy.id,
        ip_address=ip.address,
        port_range="443",
        load_balancing_scheme="EXTERNAL_MANAGED",
    )

    # 5b. HTTP → HTTPS redirect (so http://host also works).
    redirect_map = gcp.compute.URLMap(
        f"{name}-frontend-redirect",
        default_url_redirect=gcp.compute.URLMapDefaultUrlRedirectArgs(
            https_redirect=True, strip_query=False, redirect_response_code="MOVED_PERMANENTLY_DEFAULT"
        ),
    )
    http_proxy = gcp.compute.TargetHttpProxy(f"{name}-frontend-http-proxy", url_map=redirect_map.id)
    gcp.compute.GlobalForwardingRule(
        f"{name}-frontend-http-fr",
        target=http_proxy.id,
        ip_address=ip.address,
        port_range="80",
        load_balancing_scheme="EXTERNAL_MANAGED",
    )

    # 6. DNS A record in the SHARED-infra project (its own provider).
    dns_provider = gcp.Provider(f"{name}-dns-provider", project=dns_project)
    gcp.dns.RecordSet(
        f"{name}-frontend-dns",
        name=f"{host}.",
        type="A",
        ttl=300,
        managed_zone=dns_zone,
        rrdatas=[ip.address],
        project=dns_project,
        opts=pulumi.ResourceOptions(provider=dns_provider),
    )

    pulumi.export("frontend_url", f"https://{host}")
    pulumi.export("frontend_lb_ip", ip.address)
    pulumi.export("frontend_bucket", site.name)
    return site
