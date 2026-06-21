"""Tests for AnalysisService."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from src.models.conversation import Conversation
from src.models.conversation import Turn
from src.models.rules import RulePriority
from src.services.analysis_service import AnalysisService


def _make_conv(num_turns=3, conv_id=None):
    conv = Conversation(
        conversation_id=conv_id or str(uuid.uuid4()),
        session_id="s1",
        user_id="u1",
        started_at=datetime.now(),
    )
    for i in range(1, num_turns + 1):
        conv.add_turn(
            Turn(
                turn_number=i,
                user_input=f"input {i}",
                agent_response=f"response {i}",
                timestamp=datetime.now(),
            )
        )
    return conv


@pytest.fixture()
def mock_dm():
    dm = MagicMock()
    dm.load_conversations.return_value = []
    dm.save_rule.return_value = None
    return dm


@pytest.fixture()
def mock_adapter():
    adapter = MagicMock()
    adapter.generate_response.return_value = json.dumps(
        {
            "name": "auto-test-rule",
            "description": "prevents test gaps",
            "keywords": ["test"],
            "topics": ["testing"],
            "sentiment_threshold": None,
            "instruction": "be careful",
            "template": None,
        }
    )
    return adapter


@pytest.fixture()
def service(mock_dm, mock_adapter):
    with patch("src.services.analysis_service.settings") as mock_settings:
        mock_settings.MIN_SESSION_LENGTH = 2
        mock_settings.MIN_GAPS_FOR_RULE = 2
        yield AnalysisService(mock_dm, mock_adapter), mock_dm, mock_adapter, mock_settings


class TestAnalyzeRecent:
    def test_returns_empty_when_no_conversations(self, service):
        svc, dm, *_ = service
        dm.load_conversations.return_value = []
        result = svc.analyze_recent()
        assert result == []

    def test_skips_short_conversations(self, service):
        svc, dm, _, settings = service
        settings.MIN_SESSION_LENGTH = 3
        short_conv = _make_conv(num_turns=1)
        dm.load_conversations.return_value = [short_conv]
        result = svc.analyze_recent()
        assert result == []

    def test_generates_rule_for_recurring_gap(self, service):
        svc, dm, adapter, settings = service
        settings.MIN_SESSION_LENGTH = 2
        settings.MIN_GAPS_FOR_RULE = 2

        conv1 = _make_conv(num_turns=3)
        conv2 = _make_conv(num_turns=3)
        dm.load_conversations.return_value = [conv1, conv2]

        fake_gap = {
            "type": "repetition",
            "severity": 3,
            "evidence": "repeated question",
            "turn_number": 2,
        }
        with patch("src.services.analysis_service.GapDetector") as MockGapDetector:
            mock_gd = MagicMock()
            mock_gd.detect.return_value = [fake_gap]
            MockGapDetector.return_value = mock_gd
            svc2 = AnalysisService(dm, adapter)
            with patch("src.services.analysis_service.settings") as ms:
                ms.MIN_SESSION_LENGTH = 2
                ms.MIN_GAPS_FOR_RULE = 2
                result = svc2.analyze_recent()
        assert len(result) == 1
        dm.save_rule.assert_called_once()

    def test_does_not_generate_rule_below_min_occurrences(self, service):
        svc, dm, adapter, settings = service
        settings.MIN_GAPS_FOR_RULE = 5

        conv = _make_conv(num_turns=3)
        dm.load_conversations.return_value = [conv]

        fake_gap = {"type": "single_gap", "severity": 2, "evidence": "x", "turn_number": 1}
        with patch.object(svc._gap_detector, "detect", return_value=[fake_gap]):
            result = svc.analyze_recent()
        assert result == []


class TestGenerateRule:
    def test_returns_rule_from_valid_ai_response(self, service):
        svc, _, adapter, _ = service
        adapter.generate_response.return_value = json.dumps(
            {
                "name": "no-repetition",
                "description": "avoid repeating yourself",
                "keywords": ["again", "repeat"],
                "topics": ["repetition"],
                "sentiment_threshold": -0.3,
                "instruction": "don't repeat the same content",
                "template": None,
            }
        )
        occurrences = [{"severity": 3, "evidence": "repeated text", "source_conversation": "c1"}]
        rule = svc._generate_rule("repetition", occurrences)
        assert rule is not None
        assert rule.name == "no-repetition"
        assert rule.trigger.keywords == ["again", "repeat"]

    def test_falls_back_on_invalid_json(self, service):
        svc, _, adapter, _ = service
        adapter.generate_response.return_value = "not valid json {"
        occurrences = [
            {"severity": 2, "evidence": "test evidence", "description": "gap desc", "source_conversation": "c1"}
        ]
        rule = svc._generate_rule("test_gap", occurrences)
        assert rule is not None
        assert "test_gap" in rule.name

    def test_returns_none_on_unexpected_error(self, service):
        svc, _, adapter, _ = service
        adapter.generate_response.side_effect = RuntimeError("adapter crashed")
        occurrences = [{"severity": 3, "evidence": "x", "source_conversation": "c1"}]
        rule = svc._generate_rule("crash_gap", occurrences)
        assert rule is None


class TestSeverityToPriority:
    def test_critical_threshold(self):
        assert AnalysisService._severity_to_priority(4.5) == RulePriority.CRITICAL
        assert AnalysisService._severity_to_priority(5.0) == RulePriority.CRITICAL

    def test_high_threshold(self):
        assert AnalysisService._severity_to_priority(3.5) == RulePriority.HIGH
        assert AnalysisService._severity_to_priority(4.4) == RulePriority.HIGH

    def test_medium_threshold(self):
        assert AnalysisService._severity_to_priority(2.5) == RulePriority.MEDIUM

    def test_low_threshold(self):
        assert AnalysisService._severity_to_priority(1.5) == RulePriority.LOW

    def test_info_threshold(self):
        assert AnalysisService._severity_to_priority(1.0) == RulePriority.INFO
        assert AnalysisService._severity_to_priority(0.0) == RulePriority.INFO


class TestBuildRuleGenerationPrompt:
    def test_prompt_contains_gap_type(self):
        gaps = [{"turn_number": 1, "evidence": "some evidence"}]
        prompt = AnalysisService._build_rule_generation_prompt("test_gap", gaps, 3.0)
        assert "test_gap" in prompt
        assert "3.0" in prompt
        assert "some evidence" in prompt

    def test_prompt_caps_evidence_at_120_chars(self):
        long_evidence = "x" * 200
        gaps = [{"turn_number": 1, "evidence": long_evidence}]
        prompt = AnalysisService._build_rule_generation_prompt("g", gaps, 1.0)
        assert "x" * 120 in prompt
        assert "x" * 200 not in prompt


class TestParseRuleFromAi:
    def test_parses_all_fields(self, service):
        svc, *_ = service
        data = {
            "name": "my-rule",
            "description": "desc",
            "keywords": ["a", "b"],
            "topics": ["t1"],
            "sentiment_threshold": -0.5,
            "instruction": "do this",
            "template": "tmpl",
        }
        rule = svc._parse_rule_from_ai(data, "gap_x", "conv-123", 3.7)
        assert rule.name == "my-rule"
        assert rule.trigger.keywords == ["a", "b"]
        assert rule.trigger.sentiment_threshold == pytest.approx(-0.5)
        assert rule.action.template == "tmpl"
        assert rule.metadata["gap_type"] == "gap_x"

    def test_handles_missing_fields_with_defaults(self, service):
        svc, *_ = service
        rule = svc._parse_rule_from_ai({}, "gap_y", "conv-456", 2.0)
        assert "gap_y" in rule.name
        assert rule.trigger.keywords == []
