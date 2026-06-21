"""Tests for RuleEngine."""

from __future__ import annotations

import json
import uuid
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from src.core.rule_engine import RuleEngine
from src.models.rules import Rule
from src.models.rules import RuleAction
from src.models.rules import RulePriority
from src.models.rules import RuleTrigger
from src.models.rules import RuleType


def _make_rule(
    rule_id=None,
    keywords=None,
    topics=None,
    sentiment_threshold=None,
    embedding=None,
    priority=RulePriority.MEDIUM,
    is_active=True,
):
    return Rule(
        rule_id=rule_id or str(uuid.uuid4()),
        name="test-rule",
        description="desc",
        rule_type=RuleType.GUARDRAIL,
        priority=priority,
        trigger=RuleTrigger(
            keywords=keywords or [],
            topics=topics or [],
            sentiment_threshold=sentiment_threshold,
            embedding=embedding or [],
        ),
        action=RuleAction(type="inject_instruction", instruction="follow the rule"),
        is_active=is_active,
    )


@pytest.fixture()
def engine():
    dm = MagicMock()
    dm.load_rules.return_value = []
    dm.update_rule.return_value = None
    return RuleEngine(dataset_manager=dm)


@pytest.fixture()
def engine_with_rule(engine):
    rule = _make_rule(keywords=["password", "secret"])
    engine._rules = [rule]
    return engine, rule


class TestLoadRules:
    def test_loads_from_dataset_manager(self, engine):
        rule = _make_rule(keywords=["test"])
        engine._dataset_manager.load_rules.return_value = [rule]
        engine.load_rules()
        assert len(engine._rules) == 1

    def test_no_dataset_manager_keeps_empty_rules(self):
        e = RuleEngine()
        e.load_rules()
        assert e._rules == []

    def test_handles_load_failure_gracefully(self, engine):
        engine._dataset_manager.load_rules.side_effect = RuntimeError("hf down")
        engine.load_rules()
        assert engine._rules == []

    def test_loads_from_redis_when_available(self):
        rule = _make_rule(keywords=["kw"])
        serialised = json.dumps([json.loads(rule.model_dump_json())])
        mock_redis = MagicMock()
        mock_redis.get.return_value = serialised.encode()
        e = RuleEngine(redis_client=mock_redis)
        e.load_rules()
        assert len(e._rules) == 1

    def test_redis_miss_falls_back_to_dm(self):
        rule = _make_rule(keywords=["kw"])
        mock_redis = MagicMock()
        mock_redis.get.return_value = None
        dm = MagicMock()
        dm.load_rules.return_value = [rule]
        e = RuleEngine(dataset_manager=dm, redis_client=mock_redis)
        e.load_rules()
        assert len(e._rules) == 1

    def test_redis_error_falls_back_to_dm(self):
        rule = _make_rule(keywords=["kw"])
        mock_redis = MagicMock()
        mock_redis.get.side_effect = RuntimeError("redis down")
        dm = MagicMock()
        dm.load_rules.return_value = [rule]
        e = RuleEngine(dataset_manager=dm, redis_client=mock_redis)
        e.load_rules()
        assert len(e._rules) == 1

    def test_caches_rules_in_redis_after_dm_load(self):
        rule = _make_rule(keywords=["kw"])
        mock_redis = MagicMock()
        mock_redis.get.return_value = None
        dm = MagicMock()
        dm.load_rules.return_value = [rule]
        with patch("src.core.rule_engine.settings") as ms:
            ms.REDIS_RULE_TTL = 60
            e = RuleEngine(dataset_manager=dm, redis_client=mock_redis)
            e.load_rules()
        mock_redis.setex.assert_called_once()

    def test_cache_redis_failure_is_silent(self):
        rule = _make_rule(keywords=["kw"])
        mock_redis = MagicMock()
        mock_redis.get.return_value = None
        mock_redis.setex.side_effect = RuntimeError("redis full")
        dm = MagicMock()
        dm.load_rules.return_value = [rule]
        with patch("src.core.rule_engine.settings") as ms:
            ms.REDIS_RULE_TTL = 60
            e = RuleEngine(dataset_manager=dm, redis_client=mock_redis)
            e.load_rules()
        assert len(e._rules) == 1


class TestMatchRules:
    def test_matches_by_keyword(self, engine_with_rule):
        e, rule = engine_with_rule
        with patch("src.core.rule_engine.embed", return_value=[]):
            matches = e.match_rules("I need to reset my password")
        assert any(r.rule_id == rule.rule_id for r in matches)

    def test_no_match_returns_empty(self, engine_with_rule):
        e, _ = engine_with_rule
        with patch("src.core.rule_engine.embed", return_value=[]):
            matches = e.match_rules("hello world how are you")
        assert matches == []

    def test_skips_inactive_rules(self, engine):
        rule = _make_rule(keywords=["password"], is_active=False)
        engine._rules = [rule]
        with patch("src.core.rule_engine.embed", return_value=[]):
            matches = engine.match_rules("password reset")
        assert matches == []

    def test_matches_by_topic(self, engine):
        rule = _make_rule(topics=["security"])
        engine._rules = [rule]
        with patch("src.core.rule_engine.embed", return_value=[]):
            matches = engine.match_rules("this is a security concern")
        assert len(matches) == 1

    def test_matches_by_sentiment_threshold(self, engine):
        rule = _make_rule(sentiment_threshold=-0.5)
        engine._rules = [rule]
        with patch("src.core.rule_engine.embed", return_value=[]):
            matches = engine.match_rules("neutral text", sentiment=-0.8)
        assert len(matches) == 1

    def test_no_sentiment_match_above_threshold(self, engine):
        rule = _make_rule(sentiment_threshold=-0.5)
        engine._rules = [rule]
        with patch("src.core.rule_engine.embed", return_value=[]):
            matches = engine.match_rules("neutral text", sentiment=0.5)
        assert matches == []

    def test_matches_by_embedding_similarity(self, engine):
        embedding = [1.0, 0.0, 0.0]
        rule = _make_rule(embedding=embedding)
        engine._rules = [rule]
        with patch("src.core.rule_engine.embed", return_value=[1.0, 0.0, 0.0]):
            with patch("src.core.rule_engine.settings") as ms:
                ms.GAP_THRESHOLD = 0.5
                matches = engine.match_rules("some text")
        assert len(matches) == 1

    def test_sorted_by_priority(self, engine):
        low = _make_rule(keywords=["x"], priority=RulePriority.LOW)
        high = _make_rule(keywords=["x"], priority=RulePriority.HIGH)
        engine._rules = [low, high]
        with patch("src.core.rule_engine.embed", return_value=[]):
            matches = engine.match_rules("x")
        assert matches[0].priority == RulePriority.HIGH

    def test_respects_top_k(self, engine):
        rules = [_make_rule(keywords=["x"]) for _ in range(10)]
        engine._rules = rules
        with patch("src.core.rule_engine.embed", return_value=[]):
            matches = engine.match_rules("x", top_k=3)
        assert len(matches) == 3

    def test_loads_rules_when_empty(self, engine):
        rule = _make_rule(keywords=["kw"])
        engine._dataset_manager.load_rules.return_value = [rule]
        engine._rules = []
        with patch("src.core.rule_engine.embed", return_value=[]):
            matches = engine.match_rules("kw")
        assert len(matches) == 1

    def test_empty_context_skips_embedding(self, engine):
        rule = _make_rule(keywords=["kw"])
        engine._rules = [rule]
        with patch("src.core.rule_engine.embed") as mock_embed:
            engine.match_rules("   ")
            mock_embed.assert_not_called()


class TestBuildSystemPrompt:
    def test_empty_rules_returns_base_prompt(self, engine):
        result = engine.build_system_prompt([], base_prompt="be helpful")
        assert result == "be helpful"

    def test_builds_prompt_with_rules(self, engine):
        rule = _make_rule(keywords=["x"], priority=RulePriority.HIGH)
        rule.action.instruction = "never do Y"
        result = engine.build_system_prompt([rule])
        assert "HIGH" in result
        assert "never do Y" in result
        assert "Active Rules" in result

    def test_appends_to_base_prompt(self, engine):
        rule = _make_rule(keywords=["x"])
        rule.action.instruction = "do Z"
        result = engine.build_system_prompt([rule], base_prompt="base")
        assert result.startswith("base")
        assert "do Z" in result

    def test_includes_template_when_present(self, engine):
        rule = _make_rule(keywords=["x"])
        rule.action.template = "My template"
        result = engine.build_system_prompt([rule])
        assert "My template" in result


class TestRecordCounters:
    def test_record_triggered_increments_counter(self, engine_with_rule):
        e, rule = engine_with_rule
        before = rule.times_triggered
        e.record_triggered(rule.rule_id)
        assert rule.times_triggered == before + 1

    def test_record_success_increments_counter(self, engine_with_rule):
        e, rule = engine_with_rule
        before = rule.success_count
        e.record_success(rule.rule_id)
        assert rule.success_count == before + 1

    def test_record_failure_increments_counter(self, engine_with_rule):
        e, rule = engine_with_rule
        before = rule.failure_count
        e.record_failure(rule.rule_id)
        assert rule.failure_count == before + 1

    def test_persists_update_to_dataset_manager(self, engine_with_rule):
        e, rule = engine_with_rule
        e.record_triggered(rule.rule_id)
        e._dataset_manager.update_rule.assert_called_once_with(rule)

    def test_missing_rule_logs_warning(self, engine):
        engine.record_triggered("nonexistent-id")
        engine._dataset_manager.update_rule.assert_not_called()

    def test_dm_failure_is_silent(self, engine_with_rule):
        e, rule = engine_with_rule
        e._dataset_manager.update_rule.side_effect = RuntimeError("db error")
        e.record_triggered(rule.rule_id)
        assert rule.times_triggered == 1


class TestInvalidateCache:
    def test_clears_in_memory_rules(self, engine_with_rule):
        e, _ = engine_with_rule
        e.invalidate_cache()
        assert e._rules == []

    def test_clears_redis_key(self):
        mock_redis = MagicMock()
        e = RuleEngine(redis_client=mock_redis)
        e.invalidate_cache()
        mock_redis.delete.assert_called_once()

    def test_redis_error_on_invalidate_is_silent(self):
        mock_redis = MagicMock()
        mock_redis.delete.side_effect = RuntimeError("redis down")
        e = RuleEngine(redis_client=mock_redis)
        e.invalidate_cache()
        assert e._rules == []
