"""CLI dry-run behavior for commands that would otherwise write files."""

from __future__ import annotations

import pytest


@pytest.fixture()
def store_dir(tmp_path, monkeypatch):
    d = tmp_path / "store"
    d.mkdir()
    monkeypatch.setattr("ai_rule_learning_mcp.store.LOCAL_DIR", d)
    return d


def test_memory_add_dry_run_does_not_write(store_dir, capsys):
    from ai_rule_learning_mcp.cli import cmd_memory
    from ai_rule_learning_mcp.memory import load_memory

    cmd_memory(["add", "preference", "Always use type hints", "--dry-run"])

    out = capsys.readouterr().out
    assert "Dry run" in out
    assert "Always use type hints" in out
    assert load_memory() == []


def test_memory_clear_dry_run_does_not_clear(store_dir, capsys):
    from ai_rule_learning_mcp.cli import cmd_memory
    from ai_rule_learning_mcp.memory import add_memory, load_memory

    add_memory("preference", "Keep tests focused")
    cmd_memory(["clear", "--dry-run"])

    out = capsys.readouterr().out
    assert "Dry run" in out
    assert "would clear 1 memory entries" in out
    assert len(load_memory()) == 1


def test_clear_dry_run_does_not_call_injector(monkeypatch, capsys):
    from ai_rule_learning_mcp import cli

    called = False

    def _remove_rules_all():
        nonlocal called
        called = True
        return ["Claude Code"]

    monkeypatch.setattr("ai_rule_learning_mcp.injector.remove_rules_all", _remove_rules_all)

    cli.cmd_clear(["--dry-run"])

    out = capsys.readouterr().out
    assert "Dry run" in out
    assert not called


def test_scheduler_install_dry_run_does_not_call_scheduler(monkeypatch, capsys):
    from ai_rule_learning_mcp import cli

    called = False

    def _install():
        nonlocal called
        called = True
        return "installed"

    monkeypatch.setattr("ai_rule_learning_mcp.scheduler.install", _install)

    cli.cmd_install_cron(["--dry-run"])

    out = capsys.readouterr().out
    assert "Dry run" in out
    assert not called
