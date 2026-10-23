"""Tests for the KPI snapshot (Phase: observability)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from ai_rule_learning_mcp.kpi import compute_kpis, format_kpis


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    home = tmp_path / "home"
    work = tmp_path / "work"
    home.mkdir()
    work.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setattr("ai_rule_learning_mcp.store.LOCAL_DIR", home / ".ai-rule-learning")
    monkeypatch.chdir(work)
    return {"home": home, "work": work}


def test_structure_on_empty_store(isolated):
    k = compute_kpis()
    assert set(k) == {"rules", "quality", "reach", "usage"}
    assert k["rules"]["total"] == 0
    assert k["rules"]["active"] == 0
    assert k["quality"]["duplicate_pairs"] == 0
    assert k["reach"]["injection_coverage"] == 0.0
    # Metrics are opt-in and off by default -> success_rate is n/a.
    assert k["usage"]["success_rate"] is None


def test_counts_rules_after_feedback(isolated):
    from ai_rule_learning_mcp import server

    server.record_feedback(
        feedback_type="preference",
        description="State the verdict first.",
        rule_hint="Always state the verdict first.",
    )
    k = compute_kpis()
    assert k["rules"]["total"] >= 1
    assert k["rules"]["active"] >= 1


def test_injection_coverage_reflects_written_config(isolated):
    from ai_rule_learning_mcp import server
    from ai_rule_learning_mcp.injector import _ClaudeCodeTarget
    from ai_rule_learning_mcp.store import load_active_rules

    (isolated["home"] / ".claude").mkdir()
    server.record_feedback(
        feedback_type="preference",
        description="State the verdict first.",
        rule_hint="Always state the verdict first.",
    )
    _ClaudeCodeTarget().write(load_active_rules())

    k = compute_kpis()
    assert "Claude Code" in k["reach"]["agents_detected"]
    assert "Claude Code" in k["reach"]["agents_injected"]
    assert k["reach"]["injection_coverage"] > 0.0


def test_format_is_readable(isolated):
    out = format_kpis()
    assert "KPI snapshot" in out
    assert "Rules" in out and "Quality" in out and "Reach" in out and "Usage" in out
