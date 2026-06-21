"""Tests for DatasetManager using mocked HF dependencies."""

from __future__ import annotations

import uuid
from datetime import datetime
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from src.core.dataset_manager import DatasetManager
from src.models.conversation import Conversation
from src.models.conversation import Turn
from src.models.rules import Rule
from src.models.rules import RuleAction
from src.models.rules import RulePriority
from src.models.rules import RuleTrigger
from src.models.rules import RuleType


@pytest.fixture()
def manager():
    with patch("config.settings.settings") as mock_settings:
        mock_settings.HF_TOKEN = "test-token"
        mock_settings.HF_DATASET_NAME = "test/conversations"
        mock_settings.HF_RULES_DATASET = "test/rules"
        dm = DatasetManager()
        dm._hf_token = "test-token"
        dm._conversations_dataset = "test/conversations"
        dm._rules_dataset = "test/rules"
        yield dm


@pytest.fixture()
def sample_rule():
    return Rule(
        rule_id=str(uuid.uuid4()),
        name="test-rule",
        description="A test rule",
        rule_type=RuleType.GUARDRAIL,
        priority=RulePriority.MEDIUM,
        trigger=RuleTrigger(keywords=["test"]),
        action=RuleAction(type="inject_instruction", instruction="do something"),
    )


@pytest.fixture()
def sample_conversation():
    conv = Conversation(
        conversation_id="conv-001",
        session_id="sess-001",
        user_id="user-001",
        started_at=datetime(2024, 1, 15, 10, 0, 0),
    )
    conv.add_turn(
        Turn(
            turn_number=1,
            user_input="hello",
            agent_response="hi",
            sentiment_before=0.1,
            sentiment_after=0.3,
            timestamp=datetime(2024, 1, 15, 10, 0, 0),
        )
    )
    return conv


class TestGetApi:
    def test_returns_hf_api_instance(self, manager):
        mock_api = MagicMock()
        with patch("src.core.dataset_manager.DatasetManager._get_api") as patched:
            patched.return_value = mock_api
            api = manager._get_api()
            assert api is mock_api

    def test_lazy_loads_api(self, manager):
        mock_api_class = MagicMock()
        with patch.dict("sys.modules", {"huggingface_hub": MagicMock(HfApi=mock_api_class)}):
            manager._api = None
            api = manager._get_api()
            assert api is not None

    def test_raises_on_import_failure(self, manager):
        manager._api = None
        with patch("builtins.__import__", side_effect=ImportError("no hf")):
            with pytest.raises(Exception):
                manager._get_api()


class TestLoadDataset:
    def test_returns_empty_on_load_failure(self, manager):
        with patch("src.core.dataset_manager.DatasetManager._load_dataset") as patched:
            patched.return_value = []
            result = manager._load_dataset("nonexistent/dataset")
            assert result == []

    def test_returns_list_of_dicts(self, manager):
        fake_rows = [{"id": "1", "value": "a"}, {"id": "2", "value": "b"}]
        mock_ds = MagicMock()
        mock_ds.__iter__ = lambda self: iter(fake_rows)
        with patch("src.core.dataset_manager.DatasetManager._load_dataset", return_value=fake_rows):
            rows = manager._load_dataset("test/ds")
            assert len(rows) == 2


class TestSaveConversation:
    def test_calls_push_rows(self, manager, sample_conversation):
        with patch.object(manager, "_push_rows") as mock_push:
            manager.save_conversation(sample_conversation)
            mock_push.assert_called_once()
            args = mock_push.call_args[0]
            assert args[0] == "test/conversations"
            assert isinstance(args[1], list)
            assert len(args[1]) == 1


class TestLoadConversations:
    def test_returns_empty_when_no_rows(self, manager):
        with patch.object(manager, "_load_dataset", return_value=[]):
            result = manager.load_conversations()
            assert result == []

    def test_parses_valid_rows(self, manager, sample_conversation):
        import json

        row = json.loads(sample_conversation.model_dump_json())
        with patch.object(manager, "_load_dataset", return_value=[row]):
            result = manager.load_conversations()
            assert len(result) == 1
            assert result[0].conversation_id == "conv-001"

    def test_skips_malformed_rows(self, manager):
        with patch.object(manager, "_load_dataset", return_value=[{"invalid": "data"}]):
            result = manager.load_conversations()
            assert result == []

    def test_applies_limit(self, manager, sample_conversation):
        import json

        row = json.loads(sample_conversation.model_dump_json())
        with patch.object(manager, "_load_dataset", return_value=[row, row, row]):
            result = manager.load_conversations(limit=2)
            assert len(result) == 2

    def test_filters_by_since(self, manager, sample_conversation):
        import json

        row = json.loads(sample_conversation.model_dump_json())
        row["started_at"] = "2024-01-15T10:00:00"
        with patch.object(manager, "_load_dataset", return_value=[row]):
            future = datetime(2025, 1, 1)
            result = manager.load_conversations(since=future)
            assert result == []


class TestGetConversation:
    def test_returns_none_when_not_found(self, manager):
        with patch.object(manager, "_load_dataset", return_value=[]):
            assert manager.get_conversation("missing-id") is None

    def test_returns_conversation_by_id(self, manager, sample_conversation):
        import json

        row = json.loads(sample_conversation.model_dump_json())
        with patch.object(manager, "_load_dataset", return_value=[row]):
            conv = manager.get_conversation("conv-001")
            assert conv is not None
            assert conv.conversation_id == "conv-001"

    def test_skips_malformed_matching_row(self, manager):
        # Provide a type-invalid value to force a Pydantic error
        with patch.object(
            manager,
            "_load_dataset",
            return_value=[{"conversation_id": "conv-001", "turns": "not-a-list"}],
        ):
            conv = manager.get_conversation("conv-001")
            assert conv is None


class TestSaveRule:
    def test_upserts_rule(self, manager, sample_rule):
        import json

        existing = json.loads(sample_rule.model_dump_json())
        mock_ds_class = MagicMock()
        mock_ds_instance = MagicMock()
        mock_ds_class.from_list.return_value = mock_ds_instance
        with patch.object(manager, "_load_dataset", return_value=[existing]):
            with patch.dict("sys.modules", {"datasets": MagicMock(Dataset=mock_ds_class)}):
                manager.save_rule(sample_rule)
                mock_ds_instance.push_to_hub.assert_called_once()

    def test_raises_on_push_failure(self, manager, sample_rule):
        with patch.object(manager, "_load_dataset", return_value=[]):
            with patch.dict(
                "sys.modules",
                {"datasets": MagicMock(Dataset=MagicMock(from_list=MagicMock(side_effect=RuntimeError("fail"))))},
            ):
                with pytest.raises(RuntimeError):
                    manager.save_rule(sample_rule)


class TestLoadRules:
    def test_returns_empty_when_no_rows(self, manager):
        with patch.object(manager, "_load_dataset", return_value=[]):
            assert manager.load_rules() == []

    def test_filters_inactive_rules_by_default(self, manager, sample_rule):
        import json

        row = json.loads(sample_rule.model_dump_json())
        row["is_active"] = False
        with patch.object(manager, "_load_dataset", return_value=[row]):
            assert manager.load_rules(active_only=True) == []

    def test_includes_inactive_when_requested(self, manager, sample_rule):
        import json

        row = json.loads(sample_rule.model_dump_json())
        row["is_active"] = False
        with patch.object(manager, "_load_dataset", return_value=[row]):
            result = manager.load_rules(active_only=False)
            assert len(result) == 1

    def test_skips_malformed_rows(self, manager):
        with patch.object(manager, "_load_dataset", return_value=[{"bad": "data"}]):
            assert manager.load_rules() == []


class TestGetRule:
    def test_returns_none_when_not_found(self, manager):
        with patch.object(manager, "_load_dataset", return_value=[]):
            assert manager.get_rule("missing") is None

    def test_returns_rule_by_id(self, manager, sample_rule):
        import json

        row = json.loads(sample_rule.model_dump_json())
        with patch.object(manager, "_load_dataset", return_value=[row]):
            result = manager.get_rule(sample_rule.rule_id)
            assert result is not None
            assert result.rule_id == sample_rule.rule_id


class TestDeactivateRule:
    def test_deactivates_existing_rule(self, manager, sample_rule):
        with patch.object(manager, "get_rule", return_value=sample_rule):
            with patch.object(manager, "save_rule") as mock_save:
                manager.deactivate_rule(sample_rule.rule_id)
                mock_save.assert_called_once()
                assert sample_rule.is_active is False

    def test_noop_when_rule_not_found(self, manager):
        with patch.object(manager, "get_rule", return_value=None):
            with patch.object(manager, "save_rule") as mock_save:
                manager.deactivate_rule("nonexistent")
                mock_save.assert_not_called()

    def test_update_rule_delegates_to_save(self, manager, sample_rule):
        with patch.object(manager, "save_rule") as mock_save:
            manager.update_rule(sample_rule)
            mock_save.assert_called_once_with(sample_rule)
