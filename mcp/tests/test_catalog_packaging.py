"""Regression tests for packaged catalog assets and installed-package behaviour."""

from __future__ import annotations

import json
from pathlib import Path

from ai_rule_learning_mcp import catalog as catalog_module
from ai_rule_learning_mcp.catalog import RuleCatalog

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_DATA = Path(catalog_module.__file__).resolve().parent / "data"


def test_packaged_catalog_defaults_load_without_repo_cwd(tmp_path, monkeypatch) -> None:
    """The default catalog must resolve from package data, not the current directory."""
    monkeypatch.chdir(tmp_path)
    cat = RuleCatalog()
    assert cat.total_rules == 130
    assert cat.catalog_path == PACKAGE_DATA / "catalog_v1.json"
    assert cat.schema_path == PACKAGE_DATA / "context_schema.json"
    assert cat.validate()["valid"] is True


def test_packaged_data_matches_repository_source() -> None:
    """Packaged copies must stay in sync with the canonical repository data files."""
    for name in ("catalog_v1.json", "context_schema.json", "rule_metrics.json"):
        repo_file = REPO_ROOT / "data" / name
        packaged_file = PACKAGE_DATA / name
        assert packaged_file.exists(), f"missing packaged asset: {name}"
        assert json.loads(packaged_file.read_text(encoding="utf-8")) == json.loads(
            repo_file.read_text(encoding="utf-8")
        ), f"packaged {name} is out of sync with data/{name}"


def test_why_reads_active_rules_from_home_when_cwd_has_none(tmp_path, monkeypatch) -> None:
    """`why` must work from any cwd by falling back to local storage."""
    home = tmp_path / "home"
    workdir = tmp_path / "work"
    home.mkdir()
    workdir.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(workdir)

    arl_dir = home / ".ai-rule-learning"
    arl_dir.mkdir()
    (arl_dir / "active_rules.json").write_text(
        json.dumps(
            {
                "rules": [
                    {
                        "gap_type": "unverified_api_reference",
                        "category": "hallucination",
                        "priority": 5,
                        "instruction": "Verify APIs before use.",
                        "selection_reason": "High-priority hallucination guard.",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    explanations = RuleCatalog().why()
    assert len(explanations) == 1
    assert explanations[0]["gap_type"] == "unverified_api_reference"
    assert explanations[0]["reason"] == "High-priority hallucination guard."


def test_select_does_not_create_data_directory_in_arbitrary_cwd(tmp_path, monkeypatch) -> None:
    """Selection should only write user-local storage outside the repository layout."""
    home = tmp_path / "home"
    workdir = tmp_path / "work"
    home.mkdir()
    workdir.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(workdir)

    cat = RuleCatalog(metrics_path=tmp_path / "metrics.json")
    cat.select({"task_type": "code_generation", "language": "python"}, max_rules=3)

    assert (workdir / "active_rules.json").exists()
    assert (home / ".ai-rule-learning" / "active_rules.json").exists()
    assert not (workdir / "data").exists()


def test_server_does_not_import_repository_src_package() -> None:
    """The installed server must not depend on the repository-only ``src`` package."""
    from ai_rule_learning_mcp import server

    source = Path(server.__file__).read_text(encoding="utf-8")
    assert "from src" not in source
    assert "import src" not in source


def test_get_guardrail_rules_records_accurate_token_count(tmp_path, monkeypatch) -> None:
    """active_rules.json must report the real selected token count, not a constant."""
    import asyncio

    from ai_rule_learning_mcp import server

    home = tmp_path / "home"
    workdir = tmp_path / "work"
    home.mkdir()
    workdir.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(workdir)

    result = asyncio.run(server._get_guardrail_rules(dry_run=False))
    assert result and result[0].text

    payload = json.loads((home / ".ai-rule-learning" / "active_rules.json").read_text(encoding="utf-8"))
    assert payload["rules_count"] > 0
    assert 0 < payload["token_count"] <= 500
