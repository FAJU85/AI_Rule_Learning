"""MCP server rule lifecycle tool coverage."""

from __future__ import annotations

from pathlib import Path

import asyncio

import pytest

from ai_rule_learning_mcp import server
from ai_rule_learning_mcp.store import _local_load
from ai_rule_learning_mcp.store import _local_save
from ai_rule_learning_mcp.store import get_rule


@pytest.fixture(autouse=True)
def isolated_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr("ai_rule_learning_mcp.store.LOCAL_DIR", tmp_path)
    monkeypatch.setattr("ai_rule_learning_mcp.store.HF_TOKEN", "")
    monkeypatch.setattr("ai_rule_learning_mcp.store.HF_DATASET", "")
    return tmp_path


def _rule(rule_id: str, status: str = "pending") -> dict:
    return {
        "rule_id": rule_id,
        "name": f"Rule {rule_id}",
        "instruction": "Use tests.",
        "action": {"instruction": "Use tests."},
        "status": status,
        "is_active": status == "active",
        "priority": 5,
        "effectiveness_score": 0.5,
        "suppression_count": 0,
        "times_triggered": 0,
    }


def test_list_rules_tool_filters_status() -> None:
    _local_save("rules.jsonl", [_rule("pending-1"), _rule("rejected-1", "rejected")])

    result = asyncio.run(server._list_rules("pending"))

    assert "pending-1" in result[0].text
    assert "rejected-1" not in result[0].text


def test_approve_rule_tool_activates_rule() -> None:
    _local_save("rules.jsonl", [_rule("rule-1")])

    result = asyncio.run(server._approve_rule("rule-1"))

    assert "Approved" in result[0].text
    assert get_rule("rule-1")["status"] == "active"
    assert get_rule("rule-1")["is_active"] is True


def test_reject_rule_tool_dry_run_does_not_write() -> None:
    _local_save("rules.jsonl", [_rule("rule-1")])

    result = asyncio.run(server._reject_rule("rule-1", dry_run=True))

    assert "Dry run" in result[0].text
    assert get_rule("rule-1")["status"] == "pending"


def test_edit_rule_tool_updates_instruction() -> None:
    _local_save("rules.jsonl", [_rule("rule-1")])

    result = asyncio.run(server._edit_rule("rule-1", "Always run focused tests first."))

    assert "Updated" in result[0].text
    assert get_rule("rule-1")["instruction"] == "Always run focused tests first."


def test_merge_rules_tool_marks_duplicate_merged() -> None:
    _local_save("rules.jsonl", [_rule("primary", "active"), _rule("duplicate", "active")])

    result = asyncio.run(server._merge_rules("primary", "duplicate"))
    stored = {rule["rule_id"]: rule for rule in _local_load("rules.jsonl")}

    assert "Merged" in result[0].text
    assert stored["duplicate"]["status"] == "merged"
    assert stored["duplicate"]["is_active"] is False
    assert stored["duplicate"]["merged_into"] == "primary"


def test_record_rule_outcome_tool_updates_effectiveness() -> None:
    _local_save("rules.jsonl", [_rule("rule-1", "active")])

    result = asyncio.run(server._record_rule_outcome("rule-1", worked=True))

    assert "Recorded outcome" in result[0].text
    assert get_rule("rule-1")["suppression_count"] == 1
    assert get_rule("rule-1")["effectiveness_score"] == 0.6


def test_call_tool_routes_rule_lifecycle() -> None:
    _local_save("rules.jsonl", [_rule("rule-1")])

    result = asyncio.run(server.call_tool("approve_rule", {"rule_id": "rule-1"}))

    assert "Approved" in result[0].text
    assert get_rule("rule-1")["status"] == "active"
