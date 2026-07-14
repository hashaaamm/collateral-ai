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
    enable_tracing: bool
    resend_api_key_value: str
    stripe_secret_key_value: str
    stripe_webhook_secret_value: str
    langsmith_api_key_value: str
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

    # DNS-safe project prefix for every resource's logical + GCP name (no underscores).
    name: str = "collateral-ai"

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
            gke_master_authorized_cidr=os.environ.get("GKE_MASTER_AUTHORIZED_CIDR", "0.0.0.0/0").strip(),
            gke_master_cidr=os.environ.get("GKE_MASTER_CIDR", "172.16.0.0/28"),
            enable_payments=_bool("ENABLE_PAYMENTS", True),
            enable_email=_bool("ENABLE_EMAIL", True),
            enable_tracing=_bool("ENABLE_TRACING", True),
            resend_api_key_value=os.environ.get("RESEND_API_KEY_VALUE", "REPLACE_ME"),
            stripe_secret_key_value=os.environ.get("STRIPE_SECRET_KEY_VALUE", "REPLACE_ME"),
            stripe_webhook_secret_value=os.environ.get("STRIPE_WEBHOOK_SECRET_VALUE", "REPLACE_ME"),
            langsmith_api_key_value=os.environ.get("LANGSMITH_API_KEY_VALUE", "REPLACE_ME"),
            github_repo=os.environ.get("GITHUB_REPO", "").strip(),
            bucket_cors_allowed_origins=os.environ.get(
                "BUCKET_CORS_ALLOWED_ORIGINS", "http://localhost:3000",
            ).split(","),
            frontend_hosting=os.environ.get("FRONTEND_HOSTING", "cloudrun"),
            domain=os.environ.get("DOMAIN", ""),
            frontend_subdomain=os.environ.get("FRONTEND_SUBDOMAIN", "app"),
            dns_project=os.environ.get("DNS_PROJECT", ""),
            dns_zone=os.environ.get("DNS_ZONE", ""),
        )
