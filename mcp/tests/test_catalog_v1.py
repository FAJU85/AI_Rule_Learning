"""Tests for Maximum-Capacity Rule Catalog in MCP test suite (ARL-REM-2026-005)."""

from pathlib import Path
import pytest

from src.core.catalog import RuleCatalog

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def catalog() -> RuleCatalog:
    cat_path = REPO_ROOT / "data" / "catalog_v1.json"
    schema_path = REPO_ROOT / "data" / "context_schema.json"
    assert cat_path.exists(), "data/catalog_v1.json must exist"
    assert schema_path.exists(), "data/context_schema.json must exist"
    return RuleCatalog(catalog_path=cat_path, schema_path=schema_path)


def test_mcp_catalog_minimum_size(catalog: RuleCatalog) -> None:
    assert catalog.total_rules >= 120
    assert len(catalog.rules) == 130


def test_mcp_catalog_validation_checks(catalog: RuleCatalog) -> None:
    val = catalog.validate()
    assert val["valid"] is True
    assert val["citation_check"]["passed"] is True
    assert val["syntax_check"]["passed"] is True
    assert val["contradiction_check"]["passed"] is True


def test_mcp_synthetic_conversations_activate_all_ten_categories(catalog: RuleCatalog) -> None:
    synthetic_conversations = {
        "hallucination": {"task_type": "code_generation", "language": "python"},
        "verbosity": {"task_type": "code_generation", "user_style": "concise"},
        "sycophancy": {"task_type": "code_review", "user_style": "authoritative"},
        "instruction_drift": {"task_type": "code_generation", "context_length": "long"},
        "reasoning_failure": {"task_type": "architecture", "user_style": "technical"},
        "code_quality": {"task_type": "code_generation", "language": "typescript"},
        "security": {"task_type": "code_generation", "language": "sql"},
        "format_compliance": {"task_type": "code_generation", "language": "agnostic"},
        "task_completeness": {"task_type": "code_generation", "user_style": "technical"},
        "persona_and_tone": {"task_type": "general_chat", "user_style": "casual"},
    }

    activated_categories: set[str] = set()
    for target_category, context in synthetic_conversations.items():
        matched_rules = catalog.activate(context)
        assert len(matched_rules) > 0
        cat_matches = [r for r in matched_rules if r["category"] == target_category]
        assert len(cat_matches) > 0
        activated_categories.add(target_category)

    assert len(activated_categories) == 10
