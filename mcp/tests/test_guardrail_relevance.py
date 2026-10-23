"""Phase 1: get_guardrail_rules ranks the user's rules by task relevance.

Before, local rules were capped at 10 by priority only, so a relevant but
lower-priority rule was starved once the corpus exceeded 10 rules. With caller
context, the relevant rule must surface; without context, behaviour is unchanged.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ai_rule_learning_mcp import server


def _mk(i: int, name: str, instruction: str, priority: int) -> dict:
    return {
        "rule_id": f"r{i}",
        "name": name,
        "slot": name,
        "priority": priority,
        "instruction": instruction,
        "action": {"instruction": instruction},
        "is_active": True,
        "status": "active",
    }


def _rules() -> list[dict]:
    # 11 high-priority rules on unrelated topics, then one low-priority rule that
    # is the only one relevant to a pytest task. In priority order the relevant
    # rule is 12th, so a flat top-10 cap drops it.
    generic = [_mk(i, f"generic-rule-{i}", f"handle topic number {i} carefully", 4) for i in range(11)]
    relevant = _mk(99, "pytest-fixtures", "prefer pytest fixtures over unittest setUp", 2)
    return generic + [relevant]


def _text(coro) -> str:
    return "\n".join(c.text for c in asyncio.run(coro))


def test_relevant_rule_surfaces_with_context(monkeypatch):
    monkeypatch.setattr(server, "load_active_rules", _rules)
    ctx = {"language": "python", "task_type": "testing", "recent_patterns": "pytest fixtures unittest"}
    out = _text(server._get_guardrail_rules({"Inject": False}, context=ctx))
    assert "pytest-fixtures" in out


def test_priority_cap_drops_relevant_rule_without_context(monkeypatch):
    monkeypatch.setattr(server, "load_active_rules", _rules)
    out = _text(server._get_guardrail_rules({"Inject": False}))
    # 12th by priority with a cap of 10 -> excluded when there is no context.
    assert "pytest-fixtures" not in out
