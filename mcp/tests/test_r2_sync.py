"""Tests for the Cloudflare R2 remote sync backend in store.py.

store.py is local-first and mirrors rules/conversations to an R2 bucket when the
R2_* credentials are configured. boto3 is mocked here so the tests need neither
the dependency nor network access.
"""

from __future__ import annotations

import io

import pytest

from ai_rule_learning_mcp import store


@pytest.fixture
def r2_env(monkeypatch: pytest.MonkeyPatch, tmp_path) -> pytest.MonkeyPatch:
    monkeypatch.setattr(store, "LOCAL_DIR", tmp_path)
    monkeypatch.setenv("R2_BUCKET", "test-bucket")
    monkeypatch.setenv("R2_ACCESS_KEY_ID", "ak")
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "sk")
    monkeypatch.setenv("R2_ACCOUNT_ID", "acct123")
    return monkeypatch


class _FakeClient:
    """In-memory stand-in for a boto3 S3 client."""

    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}

    def put_object(self, Bucket: str, Key: str, Body: bytes, **_kw) -> None:
        self.objects[(Bucket, Key)] = Body

    def get_object(self, Bucket: str, Key: str) -> dict:
        return {"Body": io.BytesIO(self.objects[(Bucket, Key)])}


def test_remote_enabled_reflects_env(r2_env: pytest.MonkeyPatch) -> None:
    assert store.remote_enabled() is True
    assert store.hf_enabled() is True  # backwards-compatible alias
    r2_env.delenv("R2_BUCKET", raising=False)
    assert store.remote_enabled() is False


def test_r2_config_derives_endpoint_from_account(r2_env: pytest.MonkeyPatch) -> None:
    cfg = store._r2_config()
    assert cfg["endpoint"] == "https://acct123.r2.cloudflarestorage.com"
    assert cfg["bucket"] == "test-bucket"


def test_explicit_endpoint_overrides_derived(r2_env: pytest.MonkeyPatch) -> None:
    r2_env.setenv("R2_ENDPOINT", "https://custom.example.com")
    assert store._r2_config()["endpoint"] == "https://custom.example.com"


def test_upload_then_download_roundtrips_via_r2(
    r2_env: pytest.MonkeyPatch, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _FakeClient()
    monkeypatch.setattr(store, "_r2_client", lambda: fake)
    records = [{"rule_id": "r1", "name": "a"}, {"rule_id": "r2", "name": "b"}]
    store._upload("rules.jsonl", records)
    assert ("test-bucket", "rules.jsonl") in fake.objects
    assert store._download("rules.jsonl") == records


def test_prefix_is_applied_to_keys(
    r2_env: pytest.MonkeyPatch, monkeypatch: pytest.MonkeyPatch
) -> None:
    r2_env.setenv("R2_PREFIX", "backups/")
    fake = _FakeClient()
    monkeypatch.setattr(store, "_r2_client", lambda: fake)
    store._upload("rules.jsonl", [{"rule_id": "r1"}])
    assert ("test-bucket", "backups/rules.jsonl") in fake.objects


def test_download_falls_back_to_local_on_missing_key(
    r2_env: pytest.MonkeyPatch, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _Missing:
        def get_object(self, **_kw):
            raise RuntimeError("NoSuchKey")

        def put_object(self, **_kw):
            pass

    monkeypatch.setattr(store, "_r2_client", lambda: _Missing())
    store._local_save("rules.jsonl", [{"rule_id": "local1"}])
    assert store._download("rules.jsonl") == [{"rule_id": "local1"}]


def test_disabled_when_credentials_missing(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setattr(store, "LOCAL_DIR", tmp_path)
    monkeypatch.setenv("R2_BUCKET", "test-bucket")  # no keys/endpoint
    assert store.remote_enabled() is False
    # _upload must still persist locally without a remote client
    store._upload("rules.jsonl", [{"rule_id": "x"}])
    assert store._download("rules.jsonl") == [{"rule_id": "x"}]
