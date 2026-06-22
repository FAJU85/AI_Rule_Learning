"""Phase 2 tests — 4-layer failure taxonomy tags on all rules."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ai_rule_learning_mcp.gap_detector import (
    _LAYER_LABELS,
    _TEMPLATES,
    generate_rules,
)

_ALL_GAP_TYPES = list(_TEMPLATES.keys())

_VALID_LAYERS = {1, 2, 3, 4}
_VALID_CATEGORIES = {
    "knowledge_factual", "reasoning_logic", "behavioral_alignment",
    "safety_security", "robustness_consistency", "output_quality",
    "tool_agentic", "human_trust",
}


class TestTemplatesTaxonomy:
    def test_all_templates_have_failure_layer(self):
        for gap_type, tpl in _TEMPLATES.items():
            assert "failure_layer" in tpl, f"{gap_type} missing failure_layer"

    def test_all_templates_have_failure_category(self):
        for gap_type, tpl in _TEMPLATES.items():
            assert "failure_category" in tpl, f"{gap_type} missing failure_category"

    def test_all_layers_are_valid(self):
        for gap_type, tpl in _TEMPLATES.items():
            assert tpl["failure_layer"] in _VALID_LAYERS, (
                f"{gap_type} has invalid layer {tpl['failure_layer']}"
            )

    def test_all_categories_are_valid(self):
        for gap_type, tpl in _TEMPLATES.items():
            assert tpl["failure_category"] in _VALID_CATEGORIES, (
                f"{gap_type} has invalid category {tpl['failure_category']}"
            )


class TestGeneratedRulesTaxonomy:
    def _gaps_for(self, gap_type: str) -> dict:
        return {gap_type: [{"turn": 1}]}

    def test_generated_rule_has_failure_layer(self):
        for gap_type in _ALL_GAP_TYPES:
            rules = generate_rules(self._gaps_for(gap_type))
            assert rules, f"no rule generated for {gap_type}"
            assert "failure_layer" in rules[0], f"{gap_type} rule missing failure_layer"

    def test_generated_rule_has_failure_layer_label(self):
        for gap_type in _ALL_GAP_TYPES:
            rules = generate_rules(self._gaps_for(gap_type))
            label = rules[0].get("failure_layer_label", "")
            assert label in _LAYER_LABELS.values(), (
                f"{gap_type} has unknown layer label: {label!r}"
            )

    def test_generated_rule_has_failure_category(self):
        for gap_type in _ALL_GAP_TYPES:
            rules = generate_rules(self._gaps_for(gap_type))
            assert "failure_category" in rules[0], f"{gap_type} rule missing failure_category"

    def test_generated_rule_has_failure_category_label(self):
        for gap_type in _ALL_GAP_TYPES:
            rules = generate_rules(self._gaps_for(gap_type))
            assert "failure_category_label" in rules[0], (
                f"{gap_type} rule missing failure_category_label"
            )
            assert rules[0]["failure_category_label"], (
                f"{gap_type} failure_category_label is empty"
            )

    def test_layer_grouping_counts(self):
        """Each defined layer should have at least one template."""
        layers_used = {tpl["failure_layer"] for tpl in _TEMPLATES.values()}
        assert layers_used == {1, 2, 3, 4}

    def test_security_rules_are_layer_1_or_4(self):
        security_gap_types = ["code_bare_except", "code_eval_usage",
                               "code_hardcoded_secret", "prompt_injection"]
        for gap_type in security_gap_types:
            tpl = _TEMPLATES[gap_type]
            assert tpl["failure_layer"] in (1, 4), (
                f"{gap_type} expected layer 1 or 4, got {tpl['failure_layer']}"
            )

    def test_context_gaps_are_layer_2(self):
        for gap_type in ["repeated_context", "context_rot"]:
            assert _TEMPLATES[gap_type]["failure_layer"] == 2, (
                f"{gap_type} should be layer 2"
            )

    def test_orchestration_gaps_are_layer_3(self):
        for gap_type in ["cascading_retry", "format_failure"]:
            assert _TEMPLATES[gap_type]["failure_layer"] == 3, (
                f"{gap_type} should be layer 3"
            )
