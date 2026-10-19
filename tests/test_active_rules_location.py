"""End-to-end location test asserting active_rules.json lands in $HOME and not CWD (ARL-BUG-004).

Verifies Acceptance Criteria:
- AC2: File lands in $HOME/.ai-rule-learning/active_rules.json and does not appear in CWD.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from ai_rule_learning_mcp import server


@pytest.mark.asyncio
async def test_active_rules_written_to_home_not_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify get_guardrail_rules writes to $HOME/.ai-rule-learning/ and never to CWD."""
    fake_home = tmp_path / "custom_home"
    fake_cwd = tmp_path / "custom_cwd"
    fake_home.mkdir(parents=True)
    fake_cwd.mkdir(parents=True)

    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setattr(Path, "home", lambda: fake_home)
    monkeypatch.chdir(fake_cwd)

    result = await server._get_guardrail_rules(dry_run=False)
    assert result, "get_guardrail_rules should return rules"

    expected_audit_file = fake_home / ".ai-rule-learning" / "active_rules.json"
    leak_in_cwd = fake_cwd / "active_rules.json"

    assert expected_audit_file.exists(), f"Audit file must exist at {expected_audit_file}"
    assert not leak_in_cwd.exists(), f"Audit file must NOT leak into CWD ({leak_in_cwd})"
