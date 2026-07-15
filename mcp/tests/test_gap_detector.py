"""Tests for local gap detection and rule generation."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ai_rule_learning_mcp.gap_detector import (
    analyze_conversations,
    detect_gaps,
    generate_rules,
)


def _turn(user: str, agent: str = "OK") -> dict:
    return {"user_input": user, "agent_response": agent, "turn_number": 1}


# ── detect_gaps ────────────────────────────────────────────────────────────

class TestDetectGaps:
    def test_explicit_correction_detected(self):
        turns = [
            _turn("write a function"),
            _turn("actually, that's wrong — no error handling"),
        ]
        gaps = detect_gaps(turns)
        assert "explicit_correction" in gaps
        assert gaps["explicit_correction"][0]["signal"] in ("actually,", "that's wrong")

    def test_no_correction_in_clean_turns(self):
        turns = [
            _turn("write a function", "def f(): pass"),
            _turn("thanks, looks good"),
        ]
        gaps = detect_gaps(turns)
        assert "explicit_correction" not in gaps

    def test_repeated_context_detected(self):
        turns = [
            _turn("I want Python code"),
            _turn("I already told you I need Python not JavaScript"),
        ]
        gaps = detect_gaps(turns)
        assert "repeated_context" in gaps

    def test_incomplete_response_detected(self):
        turns = [
            _turn("add logging and error handling"),
            _turn("you forgot the logging part"),
        ]
        gaps = detect_gaps(turns)
        assert "incomplete_response" in gaps

    def test_code_without_error_handling_detected(self):
        turns = [
            _turn("show me db query", "```python\ndef query(db):\n    return db.execute('SELECT *')\n```"),
        ]
        gaps = detect_gaps(turns)
        assert "code_no_error_handling" in gaps

    def test_code_with_error_handling_not_flagged(self):
        turns = [
            _turn("show me db query",
                  "```python\ndef query(db):\n    try:\n        return db.execute('SELECT *')\n    except Exception as e:\n        raise\n```"),
        ]
        gaps = detect_gaps(turns)
        assert "code_no_error_handling" not in gaps

    def test_repeated_question_detected(self):
        turns = [
            _turn("how do I connect to the database safely"),
            _turn("some unrelated thing", "ok"),
            _turn("how do I connect to the database safely"),
        ]
        gaps = detect_gaps(turns)
        assert "repeated_question" in gaps

    def test_bare_except_detected(self):
        agent = "```python\ndef f():\n    try:\n        pass\n    except:\n        pass\n```"
        turns = [_turn("show me code", agent)]
        gaps = detect_gaps(turns)
        assert "code_bare_except" in gaps
        assert gaps["code_bare_except"][0]["evidence"] == "except:"

    def test_bare_except_not_flagged_when_typed(self):
        agent = "```python\ndef f():\n    try:\n        pass\n    except ValueError:\n        pass\n```"
        turns = [_turn("show me code", agent)]
        gaps = detect_gaps(turns)
        assert "code_bare_except" not in gaps

    def test_eval_usage_detected(self):
        agent = "```python\nresult = eval(user_input)\n```"
        turns = [_turn("run dynamic code", agent)]
        gaps = detect_gaps(turns)
        assert "code_eval_usage" in gaps
        assert gaps["code_eval_usage"][0]["evidence"] == "eval("

    def test_eval_not_flagged_when_absent(self):
        agent = "```python\nimport ast\nresult = ast.literal_eval(user_input)\n```"
        turns = [_turn("parse safely", agent)]
        gaps = detect_gaps(turns)
        assert "code_eval_usage" not in gaps

    def test_hardcoded_secret_detected(self):
        agent = '```python\napi_key = "sk-abc123def456"\n```'
        turns = [_turn("connect to api", agent)]
        gaps = detect_gaps(turns)
        assert "code_hardcoded_secret" in gaps
        assert gaps["code_hardcoded_secret"][0]["evidence"] == "hardcoded credential"

    def test_hardcoded_secret_not_flagged_for_env_var(self):
        agent = "```python\nimport os\napi_key = os.environ.get('API_KEY')\n```"
        turns = [_turn("connect to api", agent)]
        gaps = detect_gaps(turns)
        assert "code_hardcoded_secret" not in gaps

    def test_empty_turns_no_crash(self):
        assert detect_gaps([]) == {}


# ── generate_rules ─────────────────────────────────────────────────────────

class TestGenerateRules:
    def test_correction_gap_generates_rule(self):
        gaps = {"explicit_correction": [{"turn": 2, "signal": "actually,", "snippet": "..."}]}
        rules = generate_rules(gaps)
        assert len(rules) == 1
        assert rules[0]["name"] == "acknowledge-and-correct-immediately"
        assert rules[0]["priority"] == 4
        assert rules[0]["is_active"] is True

    def test_unknown_gap_type_skipped(self):
        gaps = {"unknown_gap_xyz": [{"turn": 1}]}
        rules = generate_rules(gaps)
        assert rules == []

    def test_multiple_gaps_sorted_by_priority(self):
        gaps = {
            "repeated_context": [{"turn": 2}],
            "explicit_correction": [{"turn": 3}],
        }
        rules = generate_rules(gaps)
        priorities = [r["priority"] for r in rules]
        assert priorities == sorted(priorities, reverse=True)

    def test_rule_ids_are_stable(self):
        gaps = {"explicit_correction": [{"turn": 2, "signal": "actually,", "snippet": ""}]}
        r1 = generate_rules(gaps)
        r2 = generate_rules(gaps)
        assert r1[0]["rule_id"] == r2[0]["rule_id"]

    def test_instance_count_recorded(self):
        gaps = {"repeated_context": [{"turn": 2}, {"turn": 5}, {"turn": 7}]}
        rules = generate_rules(gaps)
        assert rules[0]["instance_count"] == 3


# ── analyze_conversations ──────────────────────────────────────────────────

class TestAnalyzeConversations:
    def test_empty_list_returns_empty(self):
        assert analyze_conversations([]) == []

    def test_conversation_without_turns(self):
        assert analyze_conversations([{"conversation_id": "x", "turns": []}]) == []

    def test_end_to_end_with_friction(self):
        convs = [
            {
                "conversation_id": "c1",
                "turns": [
                    _turn("write function"),
                    _turn("actually that's wrong", "fixed"),
                    _turn("I already said I need Python"),
                ],
            }
        ]
        rules = analyze_conversations(convs)
        assert len(rules) >= 1
        names = [r["name"] for r in rules]
        assert "acknowledge-and-correct-immediately" in names

    def test_deduplication_across_conversations(self):
        conv = {
            "conversation_id": "c1",
            "turns": [_turn("actually wrong"), _turn("I already told you")],
        }
        rules = analyze_conversations([conv, conv])
        # Same gap type should produce same rule regardless of how many convs
        names = [r["name"] for r in rules]
        assert len(names) == len(set(names))


def test_single_session_with_four_friction_patterns_generates_rules():
    convs = [
        {
            "conversation_id": "single",
            "turns": [
                _turn("actually, that's wrong — do not use direct service access use Repository Pattern"),
                _turn("I already told you to use the Repository Pattern"),
                _turn("you forgot the repository abstraction"),
                _turn("what about the rejected direct service access approach"),
            ],
        }
    ]

    rules = analyze_conversations(convs)

    assert rules
    assert any(rule["evidence_count"] >= 1 for rule in rules)
    assert all("confidence" in rule for rule in rules)
    assert all("last_observed" in rule for rule in rules)


def test_rule_instruction_keeps_domain_specific_avoid_and_prefer_terms():
    gaps = {
        "explicit_correction": [
            {
                "turn": 2,
                "signal": "actually,",
                "snippet": "Actually, do not use direct service access use Repository Pattern.",
            }
        ]
    }

    rule = generate_rules(gaps)[0]

    assert "direct service access" in rule["instruction"]
    assert "Repository Pattern" in rule["instruction"]
    assert rule["evidence_count"] == 1
    assert 0.0 <= rule["confidence"] <= 1.0
