"""
Unit tests for connectivity-aware object storage (AWS S3 online, MinIO offline).
Pure: no network, no DB. ``connectivity_service.is_online`` and ``settings`` are
monkeypatched.
"""
from __future__ import annotations

import pytest

from app.core.config import settings
import app.services.connectivity_service as cs
import app.utils.object_storage as obj
import app.core.tenant_mode as tenant_mode


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    monkeypatch.setattr(settings, "MINIO_ENDPOINT_URL", "http://localhost:9000", raising=False)
    monkeypatch.setattr(settings, "MINIO_ACCESS_KEY_ID", "minioadmin", raising=False)
    monkeypatch.setattr(settings, "MINIO_SECRET_ACCESS_KEY", "minioadmin123", raising=False)
    monkeypatch.setattr(settings, "AWS_ACCESS_KEY_ID", "AKIA_TEST", raising=False)
    monkeypatch.setattr(settings, "AWS_SECRET_ACCESS_KEY", "secret", raising=False)
    monkeypatch.setattr(settings, "AWS_DEFAULT_REGION", "eu-west-1", raising=False)
    monkeypatch.setattr(settings, "AWS_ENDPOINT_URL", None, raising=False)
    # These online/offline cases assume a HYBRID hospital (S3 online, MinIO offline).
    monkeypatch.setattr(tenant_mode, "current_mode", lambda: tenant_mode.HYBRID)
    yield


def test_backend_is_s3_when_online(monkeypatch):
    monkeypatch.setattr(cs, "is_online", lambda **k: True)
    assert obj.active_backend() == "s3"


def test_backend_is_minio_when_offline(monkeypatch):
    monkeypatch.setattr(cs, "is_online", lambda **k: False)
    assert obj.active_backend() == "minio"


def test_offline_without_minio_stays_s3(monkeypatch):
    monkeypatch.setattr(cs, "is_online", lambda **k: False)
    monkeypatch.setattr(settings, "MINIO_ENDPOINT_URL", None, raising=False)
    assert obj.active_backend() == "s3"


def test_online_without_aws_uses_minio(monkeypatch):
    monkeypatch.setattr(cs, "is_online", lambda **k: True)
    monkeypatch.setattr(settings, "AWS_ACCESS_KEY_ID", None, raising=False)
    assert obj.active_backend() == "minio"


def test_object_url_minio_is_path_style(monkeypatch):
    monkeypatch.setattr(cs, "is_online", lambda **k: False)
    url = obj.object_base_url("tenant-bucket", "folder/file.png")
    assert url == "http://localhost:9000/tenant-bucket/folder/file.png"


def test_object_url_s3_is_virtual_hosted(monkeypatch):
    monkeypatch.setattr(cs, "is_online", lambda **k: True)
    url = obj.object_base_url("tenant-bucket", "folder/file.png")
    assert url == "https://tenant-bucket.s3.eu-west-1.amazonaws.com/folder/file.png"


def test_drain_skips_when_offline(monkeypatch):
    monkeypatch.setattr(cs, "is_online", lambda **k: False)
    out = obj.drain_pending_to_cloud()
    assert out.get("skipped") is True
