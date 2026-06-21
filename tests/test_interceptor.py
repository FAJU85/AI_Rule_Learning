"""Tests for ConversationInterceptor."""

from __future__ import annotations

from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from src.core.interceptor import ConversationInterceptor
from src.core.rule_engine import RuleEngine
from src.models.conversation import Conversation

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_interceptor(mock_adapter, mock_dataset_manager=None):
    rule_engine = MagicMock(spec=RuleEngine)
    rule_engine.load_rules.return_value = None
    rule_engine.match_rules.return_value = []
    rule_engine.build_system_prompt.return_value = ""
    return ConversationInterceptor(
        adapter=mock_adapter,
        rule_engine=rule_engine,
        dataset_manager=mock_dataset_manager,
    )


# ---------------------------------------------------------------------------
# start_session
# ---------------------------------------------------------------------------


class TestStartSession:
    def test_returns_conversation_object(self, mock_adapter):
        interceptor = _make_interceptor(mock_adapter)
        conv = interceptor.start_session(user_id="u1", project_context="test ctx")
        assert isinstance(conv, Conversation)
        assert conv.user_id == "u1"
        assert conv.project_context == "test ctx"

    def test_conversation_registered_in_active(self, mock_adapter):
        interceptor = _make_interceptor(mock_adapter)
        conv = interceptor.start_session()
        assert conv.conversation_id in interceptor._active_conversations

    def test_unique_ids_per_session(self, mock_adapter):
        interceptor = _make_interceptor(mock_adapter)
        conv1 = interceptor.start_session()
        conv2 = interceptor.start_session()
        assert conv1.conversation_id != conv2.conversation_id

    def test_session_id_auto_generated_when_omitted(self, mock_adapter):
        interceptor = _make_interceptor(mock_adapter)
        conv = interceptor.start_session()
        assert conv.session_id is not None


# ---------------------------------------------------------------------------
# process_turn
# ---------------------------------------------------------------------------


class TestProcessTurn:
    def test_returns_ai_response_string(self, mock_adapter):
        mock_adapter.generate_response.return_value = "Hello from AI."
        interceptor = _make_interceptor(mock_adapter)
        conv = interceptor.start_session()

        with patch("src.core.interceptor.sentiment_util.analyze", return_value=0.5):
            response = interceptor.process_turn(
                conversation_id=conv.conversation_id,
                user_input="Hello",
            )

        assert response == "Hello from AI."

    def test_turn_appended_to_conversation(self, mock_adapter):
        mock_adapter.generate_response.return_value = "Turn response."
        interceptor = _make_interceptor(mock_adapter)
        conv = interceptor.start_session()

        with patch("src.core.interceptor.sentiment_util.analyze", return_value=0.0):
            interceptor.process_turn(conv.conversation_id, "User says hi")

        assert len(conv.turns) == 1
        assert conv.turns[0].user_input == "User says hi"

    def test_raises_for_unknown_conversation_id(self, mock_adapter):
        interceptor = _make_interceptor(mock_adapter)
        with pytest.raises(ValueError, match="Unknown conversation_id"):
            interceptor.process_turn("nonexistent-id", "Hello")

    def test_gap_detection_runs_post_hook(self, mock_adapter):
        """Post-hook should detect anti-patterns in AI response."""
        mock_adapter.generate_response.return_value = "Use eval(input()) here."
        interceptor = _make_interceptor(mock_adapter)
        conv = interceptor.start_session()

        with patch("src.core.interceptor.sentiment_util.analyze", return_value=0.0):
            interceptor.process_turn(conv.conversation_id, "How to parse input?")

        turn = conv.turns[0]
        # eval usage is a code anti-pattern — root_cause should be set
        assert turn.root_cause is not None

    def test_rules_applied_field_populated(self, mock_adapter):
        """Matched rules should appear in the turn's rules_applied list."""
        from src.models.rules import Rule
        from src.models.rules import RuleAction
        from src.models.rules import RulePriority
        from src.models.rules import RuleTrigger
        from src.models.rules import RuleType

        rule = Rule(
            rule_id="r-001",
            name="test-rule",
            description="test",
            rule_type=RuleType.GUARDRAIL,
            priority=RulePriority.LOW,
            trigger=RuleTrigger(keywords=["hello"]),
            action=RuleAction(type="inject_instruction", instruction="Say hi nicely."),
        )

        rule_engine = MagicMock(spec=RuleEngine)
        rule_engine.load_rules.return_value = None
        rule_engine.match_rules.return_value = [rule]
        rule_engine.build_system_prompt.return_value = "Say hi nicely."
        rule_engine.record_triggered = MagicMock()

        mock_adapter.generate_response.return_value = "Hi there!"
        interceptor = ConversationInterceptor(
            adapter=mock_adapter,
            rule_engine=rule_engine,
        )
        conv = interceptor.start_session()

        with patch("src.core.interceptor.sentiment_util.analyze", return_value=0.5):
            interceptor.process_turn(conv.conversation_id, "Hello")

        assert "r-001" in conv.turns[0].rules_applied
        rule_engine.record_triggered.assert_called_once_with("r-001")


# ---------------------------------------------------------------------------
# end_session
# ---------------------------------------------------------------------------


class TestEndSession:
    def test_end_session_saves_long_enough_conversation(self, mock_adapter, mock_dataset_manager):
        mock_adapter.generate_response.return_value = "ok"
        interceptor = _make_interceptor(mock_adapter, mock_dataset_manager)
        conv = interceptor.start_session()

        with patch("src.core.interceptor.sentiment_util.analyze", return_value=0.0):
            for _ in range(3):  # MIN_SESSION_LENGTH = 3
                interceptor.process_turn(conv.conversation_id, "question")

        interceptor.end_session(conv.conversation_id)
        mock_dataset_manager.save_conversation.assert_called_once()

    def test_end_session_skips_short_conversations(self, mock_adapter, mock_dataset_manager):
        mock_adapter.generate_response.return_value = "ok"
        interceptor = _make_interceptor(mock_adapter, mock_dataset_manager)
        conv = interceptor.start_session()

        # Only 1 turn — below MIN_SESSION_LENGTH
        with patch("src.core.interceptor.sentiment_util.analyze", return_value=0.0):
            interceptor.process_turn(conv.conversation_id, "question")

        interceptor.end_session(conv.conversation_id)
        mock_dataset_manager.save_conversation.assert_not_called()

    def test_end_session_removes_from_active(self, mock_adapter):
        interceptor = _make_interceptor(mock_adapter)
        conv = interceptor.start_session()
        interceptor.end_session(conv.conversation_id)
        assert conv.conversation_id not in interceptor._active_conversations

    def test_end_session_unknown_id_returns_none(self, mock_adapter):
        interceptor = _make_interceptor(mock_adapter)
        result = interceptor.end_session("unknown-conv-id")
        assert result is None
