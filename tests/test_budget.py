"""Budget audit test suite (AC5 / ARL-MAINT-002).

Validates:
1. Token count per rule in catalog_v1.json.
2. The 10 largest rules combined do not exceed the 500-token cap.
3. Context selector greedy packing strictly enforces the 500-token cap and 10-rule ceiling under adversarial multi-trigger contexts.
"""

from pathlib import Path

import pytest

from src.core.catalog import RuleCatalog


def estimate_tokens(text: str) -> int:
    """Estimates token count for rule text (using whitespace/punct tokenization baseline ~1.3 multiplier)."""
    return int(len(text.split()) * 1.3) + 2


@pytest.fixture
def catalog() -> RuleCatalog:
    cat_path = Path("data/catalog_v1.json")
    schema_path = Path("data/context_schema.json")
    return RuleCatalog(catalog_path=cat_path, schema_path=schema_path)


def test_top_ten_largest_rules_under_500_token_cap(catalog: RuleCatalog):
    """AC5: The ten largest rules combined must not exceed 500 tokens."""
    rule_token_map = []
    for r in catalog.rules:
        gid = r.get("gap_type") or r.get("id", "unknown")
        rule_text = f"{gid}: {r['instruction']}"
        tokens = estimate_tokens(rule_text)
        rule_token_map.append((gid, tokens, r["instruction"]))

    rule_token_map.sort(key=lambda x: x[1], reverse=True)
    top_10 = rule_token_map[:10]

    combined_tokens = sum(t[1] for t in top_10)
    assert len(top_10) == 10
    assert combined_tokens <= 500, f"Top 10 rules exceeded 500-token cap: {combined_tokens} tokens"


def test_selector_enforces_budget_cap_under_adversarial_context(catalog: RuleCatalog):
    """AC5: Under an adversarial context where many rules match, selector greedy packing enforces cap."""
    # Adversarial context designed to trigger max rules
    adversarial_context = {
        "task_type": "code_generation",
        "language": "python",
        "user_style": "authoritative",
        "context_length": "long",
        "has_sql": True,
        "has_filepaths": True,
        "has_deserialization": True,
        "has_commands": True,
        "has_http_requests": True,
    }

    selected_rules = catalog.select(adversarial_context, budget_tokens=500, max_rules=10)

    # 1. Must respect 10 rule maximum
    assert len(selected_rules) <= 10, f"Selector returned {len(selected_rules)} rules, exceeding max 10"

    # 2. Combined tokens must respect 500-token cap
    total_tokens = sum(estimate_tokens(f"{r['gap_type']}: {r['instruction']}") for r in selected_rules)
    assert total_tokens <= 500, f"Selected rules total {total_tokens} tokens, exceeding 500-token budget"
