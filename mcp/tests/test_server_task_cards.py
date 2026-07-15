"""Regression tests for v0.2.0 MCP task-card UX fixes."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from ai_rule_learning_mcp import server
from ai_rule_learning_mcp.skills import get_skill


@pytest.fixture
def local_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    store_dir = tmp_path / "store"
    monkeypatch.setattr("ai_rule_learning_mcp.store.LOCAL_DIR", store_dir)
    monkeypatch.setattr("ai_rule_learning_mcp.store.HF_TOKEN", "")
    monkeypatch.setattr("ai_rule_learning_mcp.store.HF_DATASET", "")
    return store_dir


def _tool_by_name(tools, name: str):
    return next(tool for tool in tools if tool.name == name)


def test_record_feedback_description_documents_required_field() -> None:
    tools = asyncio.run(server.list_tools())
    tool = _tool_by_name(tools, "record_feedback")

    assert "description" in tool.description
    assert "Required" in tool.inputSchema["properties"]["description"]["description"]
    assert "description" in tool.inputSchema["required"]


def test_save_skill_accepts_array_steps(local_store: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server, "write_skills_all", lambda skills: [])

    result = asyncio.run(
        server._save_skill(
            skill_name="Array Steps",
            description="Skill with array steps",
            steps=["Step 1: Check input", "Step 2: Process data"],
        )
    )

    assert "✅ Skill saved" in result[0].text
    saved = get_skill("Array Steps")
    assert saved is not None
    assert "Step 1: Check input\nStep 2: Process data" in saved["steps"]


def test_save_skill_schema_documents_string_or_array_steps() -> None:
    tools = asyncio.run(server.list_tools())
    tool = _tool_by_name(tools, "save_skill")
    steps_schema = tool.inputSchema["properties"]["steps"]

    assert "oneOf" in steps_schema
    assert {entry["type"] for entry in steps_schema["oneOf"]} == {"string", "array"}
    assert "newline-separated string" in steps_schema["description"]


def test_remember_description_lists_valid_memory_types() -> None:
    tools = asyncio.run(server.list_tools())
    tool = _tool_by_name(tools, "remember")

    assert "preference, project, never, user_info, context" in tool.description
    assert tool.inputSchema["properties"]["type"]["enum"] == [
        "preference",
        "project",
        "never",
        "user_info",
        "context",
    ]


def test_sync_sessions_skips_missing_default_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    missing_projects = Path("/definitely/missing/.claude/projects")
    missing_claude = Path("/definitely/missing/.claude")
    monkeypatch.setattr(server, "_SESSION_PATHS", [missing_projects, missing_claude])

    result = asyncio.run(server._sync_sessions(paths=None, dry_run=True))

    text = result[0].text
    assert "No session directories found" in text
    assert "Set ARL_SESSIONS or pass paths/session_paths" in text
    assert str(missing_projects) in text
    assert str(missing_claude) in text


def test_sync_sessions_includes_existing_claude_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    existing_claude = tmp_path / ".claude"
    existing_claude.mkdir()
    missing_projects = tmp_path / ".claude" / "projects"
    monkeypatch.setattr(server, "_SESSION_PATHS", [missing_projects, existing_claude])

    result = asyncio.run(server._sync_sessions(paths=None, dry_run=True))

    text = result[0].text
    assert "Found 0 session file(s) across 1 path(s)" in text
    assert "Path not found" not in text


def test_get_guardrail_rules_displays_evidence_confidence_and_last_observed(
    local_store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(server, "write_rules_all", lambda rules: [])
    from ai_rule_learning_mcp.store import _local_save

    _local_save(
        "rules.jsonl",
        [
            {
                "rule_id": "r1",
                "name": "specific-rule",
                "instruction": "Use Repository Pattern.",
                "action": {"instruction": "Use Repository Pattern."},
                "priority": 4,
                "is_active": True,
                "status": "active",
                "evidence_count": 4,
                "confidence": 0.82,
                "last_observed": "2026-07-15T00:00:00",
            }
        ],
    )

    result = asyncio.run(server._get_guardrail_rules())

    assert "evidence=4" in result[0].text
    assert "confidence=82%" in result[0].text
    assert "last_observed=2026-07-15T00:00:00" in result[0].text


def test_record_feedback_reinforces_existing_rule(local_store: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server, "write_rules_all", lambda rules: [])

    asyncio.run(server._record_feedback("correction", "actually, that's wrong"))
    asyncio.run(server._record_feedback("correction", "actually, that's wrong again"))

    from ai_rule_learning_mcp.store import _local_load

    rules = _local_load("rules.jsonl")
    assert len(rules) == 1
    assert rules[0]["evidence_count"] == 2
    assert rules[0]["confidence"] > 0.55


def test_sync_sessions_reports_offline_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARL_OFFLINE", "true")
    monkeypatch.setattr(server, "_SESSION_PATHS", [Path("/definitely/missing/.claude")])

    result = asyncio.run(server._sync_sessions(paths=None, dry_run=True))

    assert "Offline mode enabled" in result[0].text
