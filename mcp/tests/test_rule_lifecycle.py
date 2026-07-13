"""Rule lifecycle tests for review and governance commands."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_rule_learning_mcp import store as store_module
from ai_rule_learning_mcp.cli import cmd_rules
from ai_rule_learning_mcp.store import _local_load
from ai_rule_learning_mcp.store import _local_save
from ai_rule_learning_mcp.store import edit_rule_instruction
from ai_rule_learning_mcp.store import list_rules
from ai_rule_learning_mcp.store import merge_rules
from ai_rule_learning_mcp.store import update_rule_status


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
    }


def test_list_rules_filters_by_lifecycle_status() -> None:
    _local_save("rules.jsonl", [_rule("pending-1"), _rule("rejected-1", "rejected")])

    pending = list_rules(status="pending")

    assert [rule["rule_id"] for rule in pending] == ["pending-1"]


def test_update_rule_status_approves_and_activates_rule() -> None:
    _local_save("rules.jsonl", [_rule("rule-1")])

    updated = update_rule_status("rule-1", "active")

    assert updated is not None
    assert updated["status"] == "active"
    assert updated["is_active"] is True
    assert updated["active_at"]


def test_update_rule_status_rejects_and_deactivates_rule() -> None:
    _local_save("rules.jsonl", [_rule("rule-1", "active")])

    updated = update_rule_status("rule-1", "rejected", note="Too broad")

    assert updated is not None
    assert updated["status"] == "rejected"
    assert updated["is_active"] is False
    assert updated["review_note"] == "Too broad"


def test_edit_rule_instruction_updates_action_instruction() -> None:
    _local_save("rules.jsonl", [_rule("rule-1")])

    updated = edit_rule_instruction("rule-1", "Always run focused tests first.")

    assert updated is not None
    assert updated["instruction"] == "Always run focused tests first."
    assert updated["action"]["instruction"] == "Always run focused tests first."


def test_merge_rules_marks_duplicate_as_merged() -> None:
    _local_save("rules.jsonl", [_rule("primary", "active"), _rule("duplicate", "active")])

    merged = merge_rules("primary", "duplicate")
    stored = {rule["rule_id"]: rule for rule in _local_load("rules.jsonl")}

    assert merged is not None
    assert stored["primary"]["merged_rule_ids"] == ["duplicate"]
    assert stored["duplicate"]["status"] == "merged"
    assert stored["duplicate"]["is_active"] is False
    assert stored["duplicate"]["merged_into"] == "primary"


def test_cli_rules_approve_updates_rule(capsys: pytest.CaptureFixture[str]) -> None:
    _local_save("rules.jsonl", [_rule("rule-1")])

    cmd_rules(["approve", "rule-1"])

    out = capsys.readouterr().out
    assert "Approved" in out
    assert _local_load("rules.jsonl")[0]["status"] == "active"


def test_cli_rules_reject_dry_run_does_not_update(capsys: pytest.CaptureFixture[str]) -> None:
    _local_save("rules.jsonl", [_rule("rule-1")])

    cmd_rules(["reject", "rule-1", "--dry-run"])

    out = capsys.readouterr().out
    assert "Dry run" in out
    assert _local_load("rules.jsonl")[0]["status"] == "pending"


def test_cli_rules_outcome_records_effectiveness(capsys: pytest.CaptureFixture[str]) -> None:
    _local_save("rules.jsonl", [_rule("rule-1", "active")])

    cmd_rules(["outcome", "rule-1", "--worked"])

    out = capsys.readouterr().out
    assert "Recorded outcome" in out
    assert store_module.get_rule("rule-1")["suppression_count"] == 1
