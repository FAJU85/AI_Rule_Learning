"""Tests for Maximum-Capacity Rule Catalog (ARL-REM-2026-005).

Verifies:
1. Catalog size >= 120 rules.
2. 10 complete categories covered.
3. Three independent validation checks (Citation, Syntax, Contradiction).
4. Automated activation of at least one rule from each of the 10 categories on synthetic conversations.
"""

from pathlib import Path

import pytest

from src.core.catalog import RuleCatalog

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def catalog() -> RuleCatalog:
    cat_path = REPO_ROOT / "data" / "catalog_v1.json"
    schema_path = REPO_ROOT / "data" / "context_schema.json"
    assert cat_path.exists(), "data/catalog_v1.json must exist"
    assert schema_path.exists(), "data/context_schema.json must exist"
    return RuleCatalog(catalog_path=cat_path, schema_path=schema_path)


def test_catalog_minimum_size(catalog: RuleCatalog) -> None:
    """Requirement: catalog must contain at least 120 rules."""
    assert catalog.total_rules >= 120
    assert len(catalog.rules) == 130


def test_catalog_ten_categories(catalog: RuleCatalog) -> None:
    """Requirement: 10 distinct categories with at least 10 rules each."""
    expected_categories = [
        "code_quality",
        "format_compliance",
        "hallucination",
        "instruction_drift",
        "persona_and_tone",
        "reasoning_failure",
        "security",
        "sycophancy",
        "task_completeness",
        "verbosity",
    ]
    assert sorted(catalog.categories) == sorted(expected_categories)
    for cat in expected_categories:
        cat_rules = catalog.get_category_rules(cat)
        assert len(cat_rules) >= 12, f"Category '{cat}' has fewer than 12 rules: {len(cat_rules)}"


def test_citation_check(catalog: RuleCatalog) -> None:
    """Validation Check 1: Citation check."""
    result = catalog.check_citations()
    assert result["passed"] is True, f"Citation failures: {result['failures']}"
    assert result["checked_count"] == catalog.total_rules


def test_syntax_check(catalog: RuleCatalog) -> None:
    """Validation Check 2: Syntax and schema check."""
    result = catalog.check_syntax()
    assert result["passed"] is True, f"Syntax failures: {result['failures']}"
    assert result["checked_count"] == catalog.total_rules


def test_contradiction_check(catalog: RuleCatalog) -> None:
    """Validation Check 3: Contradiction check within trigger envelopes."""
    result = catalog.check_contradictions()
    assert result["passed"] is True, f"Contradictions detected: {result['contradictions']}"


def test_full_validation_suite(catalog: RuleCatalog) -> None:
    """Combined validation suite reports valid=True."""
    val = catalog.validate()
    assert val["valid"] is True


def test_synthetic_conversations_activate_all_ten_categories(catalog: RuleCatalog) -> None:
    """Requirement: automated test confirms that at least one rule from each

    of the ten categories activates on a synthetic conversation designed to trigger it.
    """
    synthetic_conversations = {
        "hallucination": {
            "task_type": "code_generation",
            "language": "python",
        },
        "verbosity": {
            "task_type": "code_generation",
            "user_style": "concise",
        },
        "sycophancy": {
            "task_type": "code_review",
            "user_style": "authoritative",
        },
        "instruction_drift": {
            "task_type": "code_generation",
            "context_length": "long",
        },
        "reasoning_failure": {
            "task_type": "architecture",
            "user_style": "technical",
        },
        "code_quality": {
            "task_type": "code_generation",
            "language": "typescript",
        },
        "security": {
            "task_type": "code_generation",
            "language": "sql",
        },
        "format_compliance": {
            "task_type": "code_generation",
            "language": "agnostic",
        },
        "task_completeness": {
            "task_type": "code_generation",
            "user_style": "technical",
        },
        "persona_and_tone": {
            "task_type": "general_chat",
            "user_style": "casual",
        },
    }

    activated_categories: set[str] = set()

    for target_category, context in synthetic_conversations.items():
        matched_rules = catalog.activate(context)
        assert len(matched_rules) > 0, f"No rules activated for context targeting {target_category}"

        # Find rules matching the target category in the activated list
        cat_matches = [r for r in matched_rules if r["category"] == target_category]
        assert len(cat_matches) > 0, (
            f"Expected category '{target_category}' to activate on context {context}, but got {[r['category'] for r in matched_rules]}"
        )

        activated_categories.add(target_category)

    # Confirm all 10 categories were successfully activated
    assert len(activated_categories) == 10
