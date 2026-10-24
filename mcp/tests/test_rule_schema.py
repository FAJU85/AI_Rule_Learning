"""Tests for the Tier-A structural-hygiene schema."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from ai_rule_learning_mcp import rule_schema as rs
from ai_rule_learning_mcp.gap_detector import distill_directive

_CATALOG = Path(__file__).resolve().parent.parent / "ai_rule_learning_mcp" / "data" / "catalog_v1.json"


def _catalog_rules() -> list[dict]:
    return json.loads(_CATALOG.read_text(encoding="utf-8"))["rules"]


def test_catalog_passes_tier_a_100_percent() -> None:
    """Zero tolerance: every curated, verified rule must pass Tier-A."""
    rules = _catalog_rules()
    assert len(rules) == 130
    failures = {i: rs.check_rule(r) for i, r in enumerate(rules) if rs.check_rule(r)}
    assert failures == {}, f"catalog rules failing Tier-A: {failures}"


def test_directive_heads_cover_the_catalog() -> None:
    """The directive-head set stays calibrated to the verified corpus."""
    missing = {
        rs._first_head(r["instruction"])
        for r in _catalog_rules()
        if rs._first_head(r["instruction"]) not in rs._DIRECTIVE_HEADS
    }
    assert missing == set(), f"catalog heads not in _DIRECTIVE_HEADS: {missing}"


def test_grammatical_distill_outputs_pass() -> None:
    """Well-formed distilled directives clear Tier-A."""
    corrections = [
        "you forgot to handle the empty-list case",
        "I prefer pytest fixtures over unittest setUp",
        "use absolute imports, not relative ones",
    ]
    for c in corrections:
        directive = distill_directive(c)
        rule = {"instruction": directive, "gap_type": "explicit_correction", "source_session_id": "s1"}
        assert rs.check_rule(rule) == [], f"{directive!r} should pass Tier-A"


def test_trivial_instruction_rejected() -> None:
    assert rs.check_rule({"instruction": "be careful", "gap_type": "x", "source_session_id": "s"})
    assert rs.check_rule({"instruction": "Thanks.", "gap_type": "x", "source_session_id": "s"})


def test_non_directive_instruction_rejected() -> None:
    bad = {"instruction": "The code currently uses tabs for indentation", "gap_type": "x", "source_session_id": "s"}
    problems = rs.check_rule(bad)
    assert any("directive" in p for p in problems)


def test_untraceable_rule_rejected() -> None:
    bad = {"instruction": "Always add type hints to public functions", "gap_type": "x"}
    problems = rs.check_rule(bad)
    assert any("traceable" in p for p in problems)


def test_citation_source_satisfies_traceability() -> None:
    ok = {
        "instruction": "Always validate user input before persisting it to the database",
        "gap_type": "security",
        "source": "OWASP ASVS v4 §5.1",
    }
    assert rs.check_rule(ok) == []


def test_validate_injected_rules_zero_tolerance() -> None:
    good = {"instruction": "Always add type hints", "gap_type": "style", "source_session_id": "s", "rule_id": "g1"}
    bad = {"instruction": "ok", "gap_type": "", "rule_id": "b1"}
    ok, failures = rs.validate_injected_rules([good])
    assert ok is True and failures == {}
    ok2, failures2 = rs.validate_injected_rules([good, bad])
    assert ok2 is False
    assert "b1" in failures2 and failures2["b1"]


def test_validate_rule_raises_on_violation() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        rs.validate_rule({"instruction": "ok", "gap_type": "", "source_session_id": ""})


def test_find_conflicts_detects_opposite_polarity() -> None:
    rules = [
        {"rule_id": "a", "gap_type": "style", "instruction": "Always use tabs for indentation in python code"},
        {"rule_id": "b", "gap_type": "style", "instruction": "Never use tabs for indentation in python code"},
    ]
    conflicts = rs.find_conflicts(rules)
    assert conflicts
    ids = {frozenset((c[0], c[1])) for c in conflicts}
    assert frozenset(("a", "b")) in ids


def test_find_conflicts_ignores_unrelated_rules() -> None:
    rules = [
        {"rule_id": "a", "gap_type": "style", "instruction": "Always use tabs for indentation"},
        {"rule_id": "b", "gap_type": "security", "instruction": "Never log secrets to stdout"},
    ]
    assert rs.find_conflicts(rules) == []


def test_skill_unit_is_schema_in_waiting() -> None:
    """verification_step is nullable and unpopulated by default (boundary (b))."""
    unit = rs.SkillUnit(rule_id="r1", instruction="Always add type hints", gap_type="style")
    assert unit.verification_step is None
    populated = rs.SkillUnit(
        rule_id="r2", instruction="Run the linter", gap_type="style", verification_step="ruff check ."
    )
    assert populated.verification_step == "ruff check ."
