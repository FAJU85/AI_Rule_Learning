"""Regression tests for the 10-rule / 500-token injection invariant."""

from __future__ import annotations

import asyncio

from ai_rule_learning_mcp import server


class _FakeCatalog:
    """Minimal RuleCatalog stand-in that records the persisted selection."""

    def __init__(self) -> None:
        self.captured: dict[str, object] = {}

    def select(self, context, budget_tokens=500, max_rules=10):  # noqa: ANN001, ANN201
        return []

    def _write_active_rules(self, context, rules, accumulated_tokens, budget_tokens):  # noqa: ANN001
        self.captured = {
            "rules": rules,
            "token_count": accumulated_tokens,
            "budget_tokens": budget_tokens,
        }


def test_combined_local_rules_respect_500_token_budget(monkeypatch):
    """Long local rules must be trimmed even when they are already active."""
    long_instruction = "Validate every untrusted input before use and document the failure mode. " * 20
    local_rules = [
        {
            "rule_id": f"r{i}",
            "name": f"rule-{i}",
            "slot": f"rule-{i}",
            "priority": 5,
            "is_active": True,
            "status": "active",
            "review_status": "approved",
            "instruction": long_instruction,
            "action": {"instruction": long_instruction},
        }
        for i in range(10)
    ]

    fake_catalog = _FakeCatalog()
    monkeypatch.setattr("src.core.catalog.RuleCatalog", lambda: fake_catalog)
    monkeypatch.setattr(server, "load_active_rules", lambda: list(local_rules))
    monkeypatch.setattr(server, "write_rules_all", lambda rules: [])

    result = asyncio.run(server._get_guardrail_rules(dry_run=True))

    assert result
    persisted = fake_catalog.captured
    assert len(persisted["rules"]) < 10, "expected trimming to satisfy the token ceiling"
    assert persisted["token_count"] <= 500
    assert persisted["budget_tokens"] == 500
