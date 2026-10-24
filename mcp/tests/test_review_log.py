"""Tests for the review-decision log (pending_review instrumentation)."""

from __future__ import annotations

from pathlib import Path

import pytest
from ai_rule_learning_mcp import review_log


@pytest.fixture(autouse=True)
def isolated_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr("ai_rule_learning_mcp.store.LOCAL_DIR", tmp_path)
    return tmp_path


def _rule(instruction: str = "Always add type hints to public function signatures.") -> dict:
    return {
        "rule_id": "rul_abc",
        "instruction": instruction,
        "gap_type": "explicit_correction",
        "source_session_id": "sess_hash",
        "extraction_version": "0.3.0",
        "evidence": ["add type hints to the signature"],
        "trigger": {"keywords": ["type", "hints"]},
    }


def test_levenshtein_known_values() -> None:
    assert review_log.levenshtein("kitten", "sitting") == 3
    assert review_log.levenshtein("", "") == 0
    assert review_log.levenshtein("abc", "") == 3
    assert review_log.levenshtein("abc", "abc") == 0


def test_normalized_edit_distance_bounds() -> None:
    assert review_log.normalized_edit_distance("abc", "abc") == 0.0
    assert review_log.normalized_edit_distance("abc", "xyz") == 1.0
    assert review_log.normalized_edit_distance("", "") == 0.0
    assert 0.0 < review_log.normalized_edit_distance("color", "colour") < 1.0


def test_clean_approve_logs_zero_distance() -> None:
    rec = review_log.log_review_decision(_rule(), "approve")
    assert rec["decision"] == "approve"
    assert rec["edit_distance"] == 0
    assert rec["normalized_edit_distance"] == 0.0
    assert rec["approved_instruction"] == _rule()["instruction"]
    assert rec["source_utterance"] == "add type hints to the signature"


def test_approve_with_correction_becomes_edit_and_measures_distance() -> None:
    rule = _rule("Always add tpye hints to funcs.")  # typo-ridden candidate
    corrected = "Always add type hints to public function signatures."
    rec = review_log.log_review_decision(rule, "approve", approved_instruction=corrected)
    assert rec["decision"] == "edit"
    assert rec["edit_distance"] > 0
    assert 0.0 < rec["normalized_edit_distance"] <= 1.0
    # The corrected text is logged for measurement, not asserted to be applied.
    assert rec["approved_instruction"] == corrected
    assert rec["candidate_instruction"] == "Always add tpye hints to funcs."


def test_reject_logs_none_distance() -> None:
    rec = review_log.log_review_decision(_rule(), "reject", note="too generic")
    assert rec["decision"] == "reject"
    assert rec["edit_distance"] is None
    assert rec["normalized_edit_distance"] is None
    assert rec["approved_instruction"] == ""
    assert rec["note"] == "too generic"


def test_invalid_decision_raises() -> None:
    with pytest.raises(ValueError):
        review_log.log_review_decision(_rule(), "maybe")


def test_review_stats_aggregates_and_flags_small_sample() -> None:
    review_log.log_review_decision(_rule(), "approve")
    review_log.log_review_decision(_rule("Use tabs not spces."), "approve", approved_instruction="Use tabs not spaces.")
    review_log.log_review_decision(_rule(), "reject", note="noise")

    stats = review_log.review_stats()
    assert stats["total_decisions"] == 3
    assert stats["counts"] == {"approve": 1, "edit": 1, "reject": 1}
    # 2 of 3 kept (approve + edit), 1 rejected.
    assert stats["approval_rate"] == pytest.approx(2 / 3, abs=1e-3)
    assert stats["reject_rate"] == pytest.approx(1 / 3, abs=1e-3)
    assert stats["n_edited"] == 1
    assert stats["sufficient_sample"] is False  # N < 20


def test_review_stats_empty_log() -> None:
    stats = review_log.review_stats()
    assert stats["total_decisions"] == 0
    assert stats["approval_rate"] is None
    assert "empty" in review_log.format_review_stats(stats).lower()
