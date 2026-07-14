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
from ai_rule_learning_mcp.store import review_rule_health
from ai_rule_learning_mcp.store import suggest_duplicate_rules
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


def test_review_rule_health_preview_finds_low_effectiveness_without_writing() -> None:
    rule = _rule("weak-rule", "active")
    rule["effectiveness_score"] = 0.2
    rule["times_triggered"] = 4
    _local_save("rules.jsonl", [rule])

    report = review_rule_health(apply=False)

    assert [item["rule_id"] for item in report["needs_review"]] == ["weak-rule"]
    stored = _local_load("rules.jsonl")[0]
    assert stored["status"] == "active"
    assert stored["is_active"] is True


def test_review_rule_health_apply_marks_low_effectiveness_for_review() -> None:
    rule = _rule("weak-rule", "active")
    rule["effectiveness_score"] = 0.2
    rule["times_triggered"] = 4
    _local_save("rules.jsonl", [rule])

    report = review_rule_health(apply=True)

    assert report["applied"] is True
    stored = _local_load("rules.jsonl")[0]
    assert stored["status"] == "needs_review"
    assert stored["is_active"] is False
    assert "effectiveness_score" in stored["review_reason"]


def test_cli_rules_health_dry_run_does_not_update(capsys: pytest.CaptureFixture[str]) -> None:
    rule = _rule("weak-rule", "active")
    rule["effectiveness_score"] = 0.2
    rule["times_triggered"] = 4
    _local_save("rules.jsonl", [rule])

    cmd_rules(["health", "--apply", "--dry-run"])

    out = capsys.readouterr().out
    assert "Dry run" in out
    assert "weak-rule" in out
    assert _local_load("rules.jsonl")[0]["status"] == "active"


def test_suggest_duplicate_rules_returns_read_only_candidates() -> None:
    first = _rule("dup-1", "active")
    second = _rule("dup-2", "active")
    first["name"] = "Always run focused tests"
    second["name"] = "Always run focused tests"
    first["instruction"] = "Run focused tests before changing production code."
    second["instruction"] = "Run focused tests before changing production code."
    first["action"] = {"instruction": first["instruction"]}
    second["action"] = {"instruction": second["instruction"]}
    _local_save("rules.jsonl", [first, second])

    suggestions = suggest_duplicate_rules(min_similarity=0.7)

    assert suggestions[0]["primary_rule_id"] == "dup-1"
    assert suggestions[0]["duplicate_rule_id"] == "dup-2"
    assert _local_load("rules.jsonl")[1]["status"] == "active"


def test_cli_rules_duplicates_lists_candidates(capsys: pytest.CaptureFixture[str]) -> None:
    first = _rule("dup-1", "active")
    second = _rule("dup-2", "active")
    first["name"] = "Always run focused tests"
    second["name"] = "Always run focused tests"
    first["instruction"] = "Run focused tests before changing production code."
    second["instruction"] = "Run focused tests before changing production code."
    first["action"] = {"instruction": first["instruction"]}
    second["action"] = {"instruction": second["instruction"]}
    _local_save("rules.jsonl", [first, second])

    cmd_rules(["duplicates"])

    out = capsys.readouterr().out
    assert "Likely duplicate rules" in out
    assert "dup-1" in out
    assert "dup-2" in out


def test_update_rule_status_preserves_local_only_rules(isolated_store, monkeypatch):
    from ai_rule_learning_mcp import store

    local_only = {
        "rule_id": "local-only",
        "name": "Local only",
        "status": "pending",
        "is_active": False,
    }
    remote_rule = {
        "rule_id": "remote-rule",
        "name": "Remote rule",
        "status": "pending",
        "is_active": False,
    }
    store._local_save("rules.jsonl", [local_only])
    monkeypatch.setattr(store, "_download", lambda filename: [remote_rule.copy()] if filename == "rules.jsonl" else [])

    updated = store.update_rule_status("remote-rule", "active")

    assert updated is not None
    saved = store._local_load("rules.jsonl")
    assert {rule["rule_id"] for rule in saved} == {"remote-rule", "local-only"}
    assert next(rule for rule in saved if rule["rule_id"] == "remote-rule")["status"] == "active"


def test_cli_rules_edit_reports_empty_instruction(isolated_store, capsys):
    from ai_rule_learning_mcp.cli import cmd_rules

    cmd_rules(["edit", "rule-1", "   "])

    out = capsys.readouterr().out
    assert "❌ instruction cannot be empty" in out


def test_cli_rules_merge_reports_same_rule_ids(isolated_store, capsys):
    from ai_rule_learning_mcp.cli import cmd_rules

    cmd_rules(["merge", "rule-1", "rule-1"])

    out = capsys.readouterr().out
    assert "❌ cannot merge a rule into itself" in out
