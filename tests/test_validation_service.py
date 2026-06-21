"""Tests for ValidationService."""

from __future__ import annotations

import uuid
from datetime import datetime
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from src.models.conversation import Conversation
from src.models.conversation import Turn
from src.models.rules import Rule
from src.models.rules import RuleAction
from src.models.rules import RulePriority
from src.models.rules import RuleTrigger
from src.models.rules import RuleType
from src.services.validation_service import ValidationService


@pytest.fixture()
def mock_dm():
    dm = MagicMock()
    dm.load_rules.return_value = []
    dm.load_conversations.return_value = []
    dm.get_rule.return_value = None
    dm.update_rule.return_value = None
    dm.deactivate_rule.return_value = None
    return dm


@pytest.fixture()
def service(mock_dm):
    with patch("src.services.validation_service.settings") as mock_settings:
        mock_settings.EFFECTIVENESS_THRESHOLD = 0.5
        mock_settings.VALIDATION_SAMPLE_SIZE = 100
        svc = ValidationService(mock_dm)
        yield svc, mock_dm, mock_settings


def _make_rule(times_triggered=5, success_rate=0.7):
    return Rule(
        rule_id=str(uuid.uuid4()),
        name="test-rule",
        description="desc",
        rule_type=RuleType.GUARDRAIL,
        priority=RulePriority.MEDIUM,
        trigger=RuleTrigger(keywords=["test"]),
        action=RuleAction(type="inject_instruction", instruction="do x"),
        times_triggered=times_triggered,
        success_count=int(times_triggered * success_rate),
    )


def _make_conv_with_rule(rule_id: str, sentiment_before=0.2, sentiment_after=0.8):
    conv = Conversation(
        conversation_id=str(uuid.uuid4()),
        session_id="s1",
        user_id="u1",
        started_at=datetime.now(),
    )
    turn = Turn(
        turn_number=1,
        user_input="input",
        agent_response="output",
        rules_applied=[rule_id],
        sentiment_before=sentiment_before,
        sentiment_after=sentiment_after,
        timestamp=datetime.now(),
    )
    conv.add_turn(turn)
    return conv


class TestValidateAllRules:
    def test_empty_rules_returns_empty_list(self, service):
        svc, dm, settings = service
        dm.load_rules.return_value = []
        result = svc.validate_all_rules()
        assert result == []

    def test_deactivates_rule_below_threshold_with_enough_triggers(self, service):
        svc, dm, settings = service
        settings.EFFECTIVENESS_THRESHOLD = 0.5
        rule = _make_rule(times_triggered=15, success_rate=0.2)
        dm.load_rules.return_value = [rule]
        dm.load_conversations.return_value = []
        result = svc.validate_all_rules()
        assert rule.rule_id in result
        dm.deactivate_rule.assert_called_once_with(rule.rule_id)

    def test_does_not_deactivate_rule_with_few_triggers(self, service):
        svc, dm, settings = service
        settings.EFFECTIVENESS_THRESHOLD = 0.5
        rule = _make_rule(times_triggered=5, success_rate=0.2)
        dm.load_rules.return_value = [rule]
        dm.load_conversations.return_value = []
        result = svc.validate_all_rules()
        assert result == []
        dm.deactivate_rule.assert_not_called()

    def test_updates_rule_effectiveness_score(self, service):
        svc, dm, settings = service
        rule = _make_rule(times_triggered=5, success_rate=0.8)
        dm.load_rules.return_value = [rule]
        dm.load_conversations.return_value = []
        svc.validate_all_rules()
        dm.update_rule.assert_called_once()


class TestValidateRule:
    def test_returns_none_for_missing_rule(self, service):
        svc, dm, _ = service
        dm.get_rule.return_value = None
        result = svc.validate_rule("nonexistent")
        assert result is None

    def test_returns_effectiveness_score(self, service):
        svc, dm, _ = service
        rule = _make_rule(times_triggered=5, success_rate=0.9)
        dm.get_rule.return_value = rule
        dm.load_conversations.return_value = []
        result = svc.validate_rule(rule.rule_id)
        assert result is not None
        assert 0.0 <= result <= 1.0

    def test_deactivates_low_score_rule(self, service):
        svc, dm, settings = service
        settings.EFFECTIVENESS_THRESHOLD = 0.5
        rule = _make_rule(times_triggered=15, success_rate=0.1)
        dm.get_rule.return_value = rule
        dm.load_conversations.return_value = []
        svc.validate_rule(rule.rule_id)
        dm.deactivate_rule.assert_called_once_with(rule.rule_id)


class TestComputeEffectiveness:
    def test_falls_back_to_success_rate_when_no_conversations(self, service):
        svc, dm, _ = service
        rule = _make_rule(times_triggered=5, success_rate=0.75)
        dm.load_conversations.return_value = []
        score = svc._compute_effectiveness(rule)
        assert score == pytest.approx(rule.success_rate)

    def test_computes_from_conversation_sentiment(self, service):
        svc, dm, _ = service
        rule = _make_rule()
        conv = _make_conv_with_rule(rule.rule_id, sentiment_before=0.2, sentiment_after=0.9)
        dm.load_conversations.return_value = [conv]
        score = svc._compute_effectiveness(rule)
        assert score == pytest.approx(1.0)

    def test_negative_delta_gives_zero_score(self, service):
        svc, dm, _ = service
        rule = _make_rule()
        conv = _make_conv_with_rule(rule.rule_id, sentiment_before=0.9, sentiment_after=0.1)
        dm.load_conversations.return_value = [conv]
        score = svc._compute_effectiveness(rule)
        assert score == pytest.approx(0.0)

    def test_skips_turns_without_sentiment(self, service):
        svc, dm, _ = service
        rule = _make_rule(success_rate=0.6)
        conv = Conversation(conversation_id="c1", session_id="s1", user_id="u1", started_at=datetime.now())
        turn = Turn(
            turn_number=1,
            user_input="x",
            agent_response="y",
            rules_applied=[rule.rule_id],
            sentiment_before=None,
            sentiment_after=None,
            timestamp=datetime.now(),
        )
        conv.add_turn(turn)
        dm.load_conversations.return_value = [conv]
        score = svc._compute_effectiveness(rule)
        assert score == pytest.approx(rule.success_rate)

    def test_samples_within_size_limit(self, service):
        svc, dm, settings = service
        settings.VALIDATION_SAMPLE_SIZE = 2
        rule = _make_rule()
        convs = [_make_conv_with_rule(rule.rule_id) for _ in range(10)]
        dm.load_conversations.return_value = convs
        score = svc._compute_effectiveness(rule)
        assert 0.0 <= score <= 1.0

    def test_handles_load_failure_gracefully(self, service):
        svc, dm, _ = service
        rule = _make_rule(success_rate=0.5)
        dm.load_conversations.side_effect = RuntimeError("db down")
        score = svc._compute_effectiveness(rule)
        assert score == pytest.approx(rule.success_rate)
