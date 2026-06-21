"""Tests for Rule model, RuleTrigger, RuleAction, and related helpers."""

from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from src.models.rules import Rule
from src.models.rules import RuleAction
from src.models.rules import RulePriority
from src.models.rules import RuleTrigger
from src.models.rules import RuleType

# ---------------------------------------------------------------------------
# Rule model validation
# ---------------------------------------------------------------------------


class TestRuleModelValidation:
    def test_minimal_valid_rule(self):
        rule = Rule(
            rule_id="r-1",
            name="test",
            description="desc",
            rule_type=RuleType.GUARDRAIL,
            priority=RulePriority.MEDIUM,
            trigger=RuleTrigger(),
            action=RuleAction(type="inject_instruction", instruction="do something"),
        )
        assert rule.rule_id == "r-1"
        assert rule.is_active is True
        assert rule.version == 1

    def test_defaults_are_sensible(self):
        rule = Rule(
            rule_id="r-2",
            name="x",
            description="y",
            rule_type=RuleType.SEMGREP,
            priority=RulePriority.CRITICAL,
            trigger=RuleTrigger(),
            action=RuleAction(type="block", instruction="block it"),
        )
        assert rule.effectiveness_score == 0.0
        assert rule.times_triggered == 0
        assert rule.success_count == 0
        assert rule.failure_count == 0
        assert rule.languages == ["python"]
        assert rule.metadata == {}

    def test_rule_type_enum_values(self):
        assert RuleType.SEMGREP == "semgrep"
        assert RuleType.GUARDRAIL == "guardrail"
        assert RuleType.PRE_COMMIT == "pre_commit"

    def test_priority_enum_integer_values(self):
        assert RulePriority.CRITICAL == 5
        assert RulePriority.HIGH == 4
        assert RulePriority.MEDIUM == 3
        assert RulePriority.LOW == 2
        assert RulePriority.INFO == 1

    def test_timestamps_set_automatically(self):
        before = datetime.now()
        rule = Rule(
            rule_id="r-3",
            name="t",
            description="d",
            rule_type=RuleType.GUARDRAIL,
            priority=RulePriority.LOW,
            trigger=RuleTrigger(),
            action=RuleAction(type="x", instruction="y"),
        )
        after = datetime.now()
        assert before <= rule.created_at <= after
        assert before <= rule.updated_at <= after

    def test_optional_fields_accept_none(self):
        rule = Rule(
            rule_id="r-4",
            name="t",
            description="d",
            rule_type=RuleType.GUARDRAIL,
            priority=RulePriority.INFO,
            trigger=RuleTrigger(sentiment_threshold=None, embedding=None),
            action=RuleAction(type="x", instruction="y", template=None),
            source_conversation=None,
        )
        assert rule.source_conversation is None
        assert rule.action.template is None

    def test_rule_serialises_to_json(self):
        rule = Rule(
            rule_id="r-5",
            name="json-test",
            description="check json",
            rule_type=RuleType.GUARDRAIL,
            priority=RulePriority.HIGH,
            trigger=RuleTrigger(keywords=["foo"]),
            action=RuleAction(type="inject_instruction", instruction="be careful"),
        )
        data = rule.model_dump_json()
        assert "json-test" in data
        assert "guardrail" in data


# ---------------------------------------------------------------------------
# success_rate property
# ---------------------------------------------------------------------------


class TestSuccessRate:
    def test_zero_when_never_triggered(self):
        rule = Rule(
            rule_id="r-6",
            name="x",
            description="y",
            rule_type=RuleType.GUARDRAIL,
            priority=RulePriority.MEDIUM,
            trigger=RuleTrigger(),
            action=RuleAction(type="x", instruction="y"),
            times_triggered=0,
            success_count=0,
        )
        assert rule.success_rate == 0.0

    def test_success_rate_calculation(self):
        rule = Rule(
            rule_id="r-7",
            name="x",
            description="y",
            rule_type=RuleType.GUARDRAIL,
            priority=RulePriority.MEDIUM,
            trigger=RuleTrigger(),
            action=RuleAction(type="x", instruction="y"),
            times_triggered=10,
            success_count=7,
        )
        assert abs(rule.success_rate - 0.7) < 1e-9

    def test_full_success(self):
        rule = Rule(
            rule_id="r-8",
            name="x",
            description="y",
            rule_type=RuleType.GUARDRAIL,
            priority=RulePriority.HIGH,
            trigger=RuleTrigger(),
            action=RuleAction(type="x", instruction="y"),
            times_triggered=5,
            success_count=5,
        )
        assert rule.success_rate == 1.0

    def test_zero_successes(self):
        rule = Rule(
            rule_id="r-9",
            name="x",
            description="y",
            rule_type=RuleType.GUARDRAIL,
            priority=RulePriority.HIGH,
            trigger=RuleTrigger(),
            action=RuleAction(type="x", instruction="y"),
            times_triggered=5,
            success_count=0,
        )
        assert rule.success_rate == 0.0


# ---------------------------------------------------------------------------
# RuleTrigger
# ---------------------------------------------------------------------------


class TestRuleTrigger:
    def test_empty_trigger_is_valid(self):
        trigger = RuleTrigger()
        assert trigger.keywords == []
        assert trigger.topics == []
        assert trigger.sentiment_threshold is None
        assert trigger.embedding is None

    def test_trigger_with_all_fields(self):
        trigger = RuleTrigger(
            sentiment_threshold=-0.5,
            keywords=["error", "fail"],
            topics=["debugging"],
            embedding=[0.1, 0.2, 0.3],
            pattern=r"\berror\b",
        )
        assert trigger.sentiment_threshold == -0.5
        assert "error" in trigger.keywords
        assert trigger.embedding == [0.1, 0.2, 0.3]
        assert trigger.pattern == r"\berror\b"


# ---------------------------------------------------------------------------
# RuleAction
# ---------------------------------------------------------------------------


class TestRuleAction:
    def test_minimal_action(self):
        action = RuleAction(type="inject_instruction", instruction="do it")
        assert action.type == "inject_instruction"
        assert action.instruction == "do it"
        assert action.template is None

    def test_action_with_template(self):
        action = RuleAction(
            type="inject_instruction",
            instruction="use template",
            template="When asked about {topic}, always mention {detail}.",
        )
        assert "{topic}" in action.template

    def test_action_type_is_required(self):
        with pytest.raises(ValidationError):
            RuleAction(instruction="missing type field")  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# sample_rule fixture smoke-test
# ---------------------------------------------------------------------------


class TestSampleRuleFixture:
    def test_sample_rule_is_active(self, sample_rule):
        assert sample_rule.is_active is True

    def test_sample_rule_has_correct_type(self, sample_rule):
        assert sample_rule.rule_type == RuleType.GUARDRAIL

    def test_sample_rule_has_keywords(self, sample_rule):
        assert len(sample_rule.trigger.keywords) > 0

    def test_active_rule_with_stats_success_rate(self, active_rule_with_stats):
        assert abs(active_rule_with_stats.success_rate - 0.75) < 1e-9
