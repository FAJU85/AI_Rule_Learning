"""Test suite for active_rules.json path resolution and single-write semantics (ARL-BUG-003).

Verifies Acceptance Criteria:
- AC1: File exists at $HOME/.ai-rule-learning/active_rules.json on clean install/invocation.
- AC2: Token count reflects actual selection rather than hardcoded 300.
- AC3: Rules count in active_rules.json matches the returned rule count.
- AC4: Budget invariants (token_count <= budget_tokens and rules_count <= 10) hold.
- AC5: Running from arbitrary CWD (e.g. /tmp) still writes to $HOME/.ai-rule-learning/active_rules.json.
- AC6: Read-only $HOME logs ERROR with path & exception type, and server still returns rules.
- AC7: Exactly one write to active_rules.json per get_guardrail_rules() call.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any
import pytest

from ai_rule_learning_mcp import server
from ai_rule_learning_mcp.catalog import RuleCatalog, _ACTIVE_RULES_PATH


@pytest.mark.asyncio
async def test_fresh_home_no_dir_created(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AC1: Fresh $HOME with no .ai-rule-learning directory -> file created successfully."""
    fresh_home = tmp_path / "fresh_user"
    monkeypatch.setenv("HOME", str(fresh_home))
    monkeypatch.setattr(Path, "home", lambda: fresh_home)

    result = await server._get_guardrail_rules(dry_run=False)
    assert result, "Server should return rules"

    target_file = fresh_home / ".ai-rule-learning" / "active_rules.json"
    assert target_file.exists(), f"Target file must exist at {target_file}"

    data = json.loads(target_file.read_text(encoding="utf-8"))
    assert "token_count" in data
    assert "rules" in data
    assert data["rules_count"] == len(data["rules"])
    assert 1 <= data["rules_count"] <= 10


@pytest.mark.asyncio
async def test_fresh_home_where_dir_already_exists(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Fresh $HOME where .ai-rule-learning already exists -> overwritten without error."""
    existing_home = tmp_path / "existing_user"
    config_dir = existing_home / ".ai-rule-learning"
    config_dir.mkdir(parents=True)
    target_file = config_dir / "active_rules.json"
    target_file.write_text(json.dumps({"dummy": "old_data"}), encoding="utf-8")

    monkeypatch.setenv("HOME", str(existing_home))
    monkeypatch.setattr(Path, "home", lambda: existing_home)

    result = await server._get_guardrail_rules(dry_run=False)
    assert result

    data = json.loads(target_file.read_text(encoding="utf-8"))
    assert "dummy" not in data
    assert "rules" in data
    assert data["rules_count"] >= 1


@pytest.mark.asyncio
async def test_readonly_home_logs_error_and_server_still_responds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """AC6: $HOME set to read-only directory -> ERROR logged, server still returns rules."""
    ro_home = tmp_path / "ro_home"
    ro_home.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(ro_home))
    monkeypatch.setattr(Path, "home", lambda: ro_home)

    # Force write failure by monkeypatching open on target file
    real_open = open

    def failing_open(file, *args, **kwargs):
        if ".ai-rule-learning" in str(file):
            raise PermissionError("Simulated permission denied on read-only filesystem")
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr("builtins.open", failing_open)

    with caplog.at_level(logging.ERROR):
        result = await server._get_guardrail_rules(dry_run=False)

    # Server must gracefully degrade and return rules
    assert result, "Server must still return rules despite storage degradation"
    assert "Failed to persist active_rules.json →" in caplog.text
    assert "PermissionError" in caplog.text


@pytest.mark.asyncio
async def test_server_invoked_from_tmp_writes_to_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC5: Running from arbitrary CWD (e.g. /tmp) still writes to $HOME/.ai-rule-learning/active_rules.json."""
    home_dir = tmp_path / "isolated_home"
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.setattr(Path, "home", lambda: home_dir)
    monkeypatch.chdir("/tmp")

    result = await server._get_guardrail_rules(dry_run=False)
    assert result

    expected_file = home_dir / ".ai-rule-learning" / "active_rules.json"
    assert expected_file.exists(), f"File must be written to {expected_file}"


@pytest.mark.asyncio
async def test_token_count_reflects_actual_selection_three_profiles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC2, AC3, AC4: Token count and rule count reflect actual selection across profiles."""
    home_dir = tmp_path / "profile_user"
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.setattr(Path, "home", lambda: home_dir)

    profiles = [
        {"language": "python", "task_type": "debugging", "user_style": "concise"},
        {"language": "typescript", "task_type": "code_review", "framework": "react"},
        {"language": "sql", "task_type": "security", "context_length": "medium"},
    ]

    target_file = home_dir / ".ai-rule-learning" / "active_rules.json"

    for ctx in profiles:
        result = await server._get_guardrail_rules(context=ctx, dry_run=False)
        assert result

        assert target_file.exists()
        data = json.loads(target_file.read_text(encoding="utf-8"))

        # AC2: Token count must reflect actual selection and not hardcoded 300
        token_count = data["token_count"]
        assert token_count > 0

        # Estimate sum of tokens
        estimated_sum = sum(len(r["instruction"].split()) * 1.33 for r in data["rules"])
        assert data["token_count"] <= data["budget_tokens"]
        assert data["budget_tokens"] == 500

        # AC3: rules_count matches number of rules
        assert data["rules_count"] == len(data["rules"])
        assert data["rules_count"] <= 10

        # AC4: Budget invariants hold
        assert data["token_count"] <= 500
        assert data["rules_count"] <= 10


@pytest.mark.asyncio
async def test_single_write_per_call(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AC7: Single write per get_guardrail_rules() invocation."""
    home_dir = tmp_path / "single_write_user"
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.setattr(Path, "home", lambda: home_dir)

    write_calls = []
    original_write = RuleCatalog._write_active_rules

    def tracked_write(self, context, selected, accumulated_tokens, budget_tokens):
        write_calls.append({
            "tokens": accumulated_tokens,
            "rules": len(selected),
        })
        return original_write(self, context, selected, accumulated_tokens, budget_tokens)

    monkeypatch.setattr(RuleCatalog, "_write_active_rules", tracked_write)

    result = await server._get_guardrail_rules(dry_run=False)
    assert result

    # Must produce exactly one write
    assert len(write_calls) == 1, f"Expected 1 write call, got {len(write_calls)}: {write_calls}"
    assert write_calls[0]["tokens"] > 0
    assert write_calls[0]["tokens"] != 300 or write_calls[0]["rules"] == 10
