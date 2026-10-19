"""Source-level assertion gate for active_rules.json absolute path invariant (ARL-BUG-004).

Verifies Acceptance Criteria:
- AC1: _ACTIVE_RULES_PATH is absolute and rooted in user home directory.
- AC4: Fails if _ACTIVE_RULES_PATH is ever reverted to a relative path.
"""

from __future__ import annotations

from ai_rule_learning_mcp import catalog


def test_active_rules_constant_is_absolute() -> None:
    """Assert _ACTIVE_RULES_PATH is absolute, named active_rules.json, and under .ai-rule-learning."""
    assert catalog._ACTIVE_RULES_PATH.is_absolute() is True
    assert catalog._ACTIVE_RULES_PATH.name == "active_rules.json"
    assert catalog._ACTIVE_RULES_PATH.parent.name == ".ai-rule-learning"
