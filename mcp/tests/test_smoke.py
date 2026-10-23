"""Smoke test — fast, shallow critical-path check.

Not a substitute for the full suite: it proves the package imports, the version
is sane, the CLI entry point runs, and the core loop (record a preference ->
store -> load -> inject into a config) works end to end in a few milliseconds. If
this file fails, something is fundamentally broken; run it first.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    """Isolate HOME, cwd, and the local store into a temp directory."""
    home = tmp_path / "home"
    work = tmp_path / "work"
    home.mkdir()
    work.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setattr("ai_rule_learning_mcp.store.LOCAL_DIR", home / ".ai-rule-learning")
    monkeypatch.chdir(work)
    return {"home": home, "work": work}


def test_core_modules_import():
    import ai_rule_learning_mcp.catalog  # noqa: F401
    import ai_rule_learning_mcp.cli  # noqa: F401
    import ai_rule_learning_mcp.clustering  # noqa: F401
    import ai_rule_learning_mcp.dataset  # noqa: F401
    import ai_rule_learning_mcp.injector  # noqa: F401
    import ai_rule_learning_mcp.server  # noqa: F401
    import ai_rule_learning_mcp.similarity  # noqa: F401
    import ai_rule_learning_mcp.store  # noqa: F401


def test_version_is_sane():
    from ai_rule_learning_mcp import __version__

    assert isinstance(__version__, str)
    assert __version__.count(".") >= 2  # semver-ish


def test_cli_version_and_status_run(isolated):
    from ai_rule_learning_mcp.cli import main

    assert main(["--version"]) == 0
    assert main(["status"]) == 0


def test_core_loop_record_load_inject(isolated):
    """record a preference -> it is stored and loadable -> it injects into a config."""
    from ai_rule_learning_mcp import server
    from ai_rule_learning_mcp.injector import _ClaudeCodeTarget
    from ai_rule_learning_mcp.store import load_active_rules

    res = server.record_feedback(
        feedback_type="preference",
        description="I prefer the verdict stated first.",
        rule_hint="Always state the verdict first, then the reasoning.",
    )
    assert res["status"] in {"Created", "Updated", "AlreadyKnown"}

    active = load_active_rules()
    assert any("verdict first" in (r.get("instruction") or "") for r in active)

    # Inject into an isolated Claude Code config and read it back.
    (isolated["home"] / ".claude").mkdir()
    target = _ClaudeCodeTarget()
    target.write(active)
    text = (isolated["home"] / ".claude" / "CLAUDE.md").read_text(encoding="utf-8")
    assert "AI-Rule-Learning:start" in text
    assert "verdict first" in text


def test_dataset_export_runs(isolated, tmp_path):
    from ai_rule_learning_mcp.dataset import export_sft_jsonl

    rules = [{"name": "r", "instruction": "Always include type hints.", "action": {"instruction": "Always include type hints."}}]
    out = tmp_path / "ds.jsonl"
    assert export_sft_jsonl(out, rules=rules) == 1
    assert out.read_text(encoding="utf-8").strip() != ""
