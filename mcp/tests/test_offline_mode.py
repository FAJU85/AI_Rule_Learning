"""Regression tests for offline/no-network mode."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_rule_learning_mcp import community
from ai_rule_learning_mcp import store


@pytest.fixture
def local_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    store_dir = tmp_path / "store"
    monkeypatch.setattr(store, "LOCAL_DIR", store_dir)
    monkeypatch.setattr(store, "HF_TOKEN", "hf_fake")
    monkeypatch.setattr(store, "HF_DATASET", "owner/dataset")
    monkeypatch.setattr(community, "HF_TOKEN", "hf_fake")
    monkeypatch.setenv("ARL_OFFLINE", "true")
    return store_dir


def test_store_offline_download_uses_local_without_hf_import(local_store: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store._local_save("rules.jsonl", [{"rule_id": "local"}])

    def fail_import(name: str, *args, **kwargs):
        if name == "huggingface_hub":
            raise AssertionError("offline mode must not import huggingface_hub")
        return real_import(name, *args, **kwargs)

    real_import = __import__
    monkeypatch.setattr("builtins.__import__", fail_import)

    assert store._download("rules.jsonl") == [{"rule_id": "local"}]
    assert store.hf_enabled() is False


def test_store_offline_upload_only_writes_local(local_store: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(store, "_hf_api", lambda: (_ for _ in ()).throw(AssertionError("network disabled")))

    store._upload("rules.jsonl", [{"rule_id": "local"}])

    assert store._local_load("rules.jsonl") == [{"rule_id": "local"}]


def test_community_offline_blocks_public_template_download(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARL_OFFLINE", "true")
    monkeypatch.setattr(community, "HF_TOKEN", "hf_fake")

    assert community.fetch_community_patterns() == {}
    assert community.pull_community_templates() == []
    assert community.contribute_gaps({"explicit_correction": [{"turn": 1}]}, "abc") is False
