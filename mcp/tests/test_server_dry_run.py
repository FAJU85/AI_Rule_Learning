"""Dry-run coverage for MCP server write tools."""

from __future__ import annotations

from pathlib import Path

import asyncio

import pytest

from ai_rule_learning_mcp import server
from ai_rule_learning_mcp.memory import load_memory
from ai_rule_learning_mcp.skills import list_skills
from ai_rule_learning_mcp.store import _local_load
from ai_rule_learning_mcp.store import is_already_processed


@pytest.fixture
def local_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    store_dir = tmp_path / "store"
    monkeypatch.setattr("ai_rule_learning_mcp.store.LOCAL_DIR", store_dir)
    monkeypatch.setattr("ai_rule_learning_mcp.store.HF_TOKEN", "")
    monkeypatch.setattr("ai_rule_learning_mcp.store.HF_DATASET", "")
    return store_dir


def test_remember_dry_run_does_not_write_memory(local_store: Path) -> None:
    result = asyncio.run(server._remember("preference", "Use type hints", dry_run=True))

    assert "Dry run" in result[0].text
    assert load_memory() == []
    assert not (local_store / "memory.jsonl").exists()


def test_record_feedback_dry_run_does_not_write_rules(local_store: Path) -> None:
    result = asyncio.run(
        server._record_feedback(
            "correction",
            "The agent forgot to run tests.",
            dry_run=True,
        )
    )

    assert "Dry run" in result[0].text
    assert _local_load("rules.jsonl") == []
    assert not (local_store / "rules.jsonl").exists()


def test_save_skill_dry_run_does_not_write_skill(local_store: Path) -> None:
    result = asyncio.run(
        server._save_skill(
            "Create Test Plan",
            "Plan tests before coding.",
            "1. Identify changed behavior.\n2. Add regression tests.",
            dry_run=True,
        )
    )

    assert "Dry run" in result[0].text
    assert list_skills() == []
    assert not any((local_store / "skills").glob("*.md"))


def test_install_scheduler_dry_run_does_not_call_install(monkeypatch: pytest.MonkeyPatch) -> None:
    called = False

    def fake_install() -> str:
        nonlocal called
        called = True
        return "installed"

    monkeypatch.setattr("ai_rule_learning_mcp.scheduler.install", fake_install)

    result = asyncio.run(server._install_scheduler("install", dry_run=True))

    assert "Dry run" in result[0].text
    assert called is False


def test_sync_sessions_dry_run_does_not_mark_or_save(
    local_store: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_file = tmp_path / "session.jsonl"
    session_file.write_text("{}\n", encoding="utf-8")
    conversations = [
        {
            "session_id": "abc123",
            "turns": [{"gaps_detected": [{"type": "explicit_correction"}]}],
        }
    ]
    rule = {
        "rule_id": "dry-run-rule",
        "name": "Dry Run Rule",
        "instruction": "Remember to run tests.",
        "is_active": True,
        "priority": 10,
    }

    monkeypatch.setattr(server, "parse_any", lambda path: conversations)
    monkeypatch.setattr(server, "analyze_conversations", lambda convs: [rule])

    result = asyncio.run(server._sync_sessions(paths=[session_file], dry_run=True))

    assert "Dry run" in result[0].text
    assert not is_already_processed(session_file)
    assert _local_load("rules.jsonl") == []
    assert _local_load("conversations.jsonl") == []
    assert not (local_store / "processed.jsonl").exists()
