"""Phase 3 tests — rule effectiveness tracking."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import ai_rule_learning_mcp.store as store_module
from ai_rule_learning_mcp.gap_detector import generate_rules


# ── helpers ───────────────────────────────────────────────────────────────

def _seed_rules(tmp_dir: Path, rules: list[dict]) -> None:
    rules_file = tmp_dir / "rules.jsonl"
    rules_file.write_text(
        "\n".join(json.dumps(r) for r in rules) + "\n", encoding="utf-8"
    )


@pytest.fixture()
def isolated_store(tmp_path, monkeypatch):
    """Redirect store local storage to a temp dir for each test."""
    monkeypatch.setattr(store_module, "LOCAL_DIR", tmp_path)
    monkeypatch.setenv("ARL_DATASET", "")
    monkeypatch.setenv("HF_TOKEN", "")
    return tmp_path


# ── initial rule fields ───────────────────────────────────────────────────

class TestInitialRuleFields:
    def test_new_rule_has_effectiveness_score(self):
        rules = generate_rules({"explicit_correction": [{"turn": 1, "signal": "actually,", "snippet": ""}]})
        assert rules[0]["effectiveness_score"] == 0.5

    def test_new_rule_has_times_triggered(self):
        rules = generate_rules({"repeated_context": [{"turn": 2}]})
        assert rules[0]["times_triggered"] == 0

    def test_new_rule_has_suppression_count(self):
        rules = generate_rules({"sycophancy": [{"turn": 1, "signal": "x"}]})
        assert rules[0]["suppression_count"] == 0

    def test_new_rule_has_last_fired_at_none(self):
        rules = generate_rules({"hallucination_risk": [{"turn": 1, "signal": "x"}]})
        assert rules[0]["last_fired_at"] is None


# ── record_rule_outcome ───────────────────────────────────────────────────

class TestRecordRuleOutcome:
    def _rule(self, rule_id: str = "rul_test123") -> dict:
        return {
            "rule_id": rule_id,
            "name": "test-rule",
            "effectiveness_score": 0.5,
            "times_triggered": 0,
            "suppression_count": 0,
            "last_fired_at": None,
            "is_active": True,
            "status": "active",
        }

    def test_fired_again_increments_times_triggered(self, isolated_store):
        rule = self._rule()
        _seed_rules(isolated_store, [rule])
        updated = store_module.record_rule_outcome(rule["rule_id"], fired_again=True)
        assert updated["times_triggered"] == 1

    def test_fired_again_decreases_effectiveness(self, isolated_store):
        rule = self._rule()
        _seed_rules(isolated_store, [rule])
        updated = store_module.record_rule_outcome(rule["rule_id"], fired_again=True)
        assert updated["effectiveness_score"] == 0.4

    def test_suppressed_increments_suppression_count(self, isolated_store):
        rule = self._rule()
        _seed_rules(isolated_store, [rule])
        updated = store_module.record_rule_outcome(rule["rule_id"], fired_again=False)
        assert updated["suppression_count"] == 1

    def test_suppressed_increases_effectiveness(self, isolated_store):
        rule = self._rule()
        _seed_rules(isolated_store, [rule])
        updated = store_module.record_rule_outcome(rule["rule_id"], fired_again=False)
        assert updated["effectiveness_score"] == 0.6

    def test_effectiveness_capped_at_1(self, isolated_store):
        rule = self._rule()
        rule["effectiveness_score"] = 0.95
        _seed_rules(isolated_store, [rule])
        updated = store_module.record_rule_outcome(rule["rule_id"], fired_again=False)
        assert updated["effectiveness_score"] == 1.0

    def test_effectiveness_floored_at_0(self, isolated_store):
        rule = self._rule()
        rule["effectiveness_score"] = 0.05
        _seed_rules(isolated_store, [rule])
        updated = store_module.record_rule_outcome(rule["rule_id"], fired_again=True)
        assert updated["effectiveness_score"] == 0.0

    def test_last_fired_at_updated(self, isolated_store):
        rule = self._rule()
        _seed_rules(isolated_store, [rule])
        updated = store_module.record_rule_outcome(rule["rule_id"], fired_again=True)
        assert updated["last_fired_at"] is not None

    def test_unknown_rule_id_returns_none(self, isolated_store):
        _seed_rules(isolated_store, [self._rule()])
        result = store_module.record_rule_outcome("rul_nonexistent", fired_again=True)
        assert result is None

    def test_multiple_outcomes_accumulate(self, isolated_store):
        rule = self._rule()
        _seed_rules(isolated_store, [rule])
        store_module.record_rule_outcome(rule["rule_id"], fired_again=False)
        store_module.record_rule_outcome(rule["rule_id"], fired_again=False)
        updated = store_module.record_rule_outcome(rule["rule_id"], fired_again=False)
        assert updated["suppression_count"] == 3
        assert updated["effectiveness_score"] == 0.8

    def test_changes_persisted_to_disk(self, isolated_store):
        rule = self._rule()
        _seed_rules(isolated_store, [rule])
        store_module.record_rule_outcome(rule["rule_id"], fired_again=True)
        # Re-load from disk
        reloaded = store_module._local_load("rules.jsonl")
        assert reloaded[0]["times_triggered"] == 1
