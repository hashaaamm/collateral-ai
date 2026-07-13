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
