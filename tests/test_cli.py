"""Tests for CLI entry point — argument parsing, command dispatch, and adapter building."""

from __future__ import annotations

from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from src.cli.main import _build_adapter
from src.cli.main import build_parser
from src.cli.main import cmd_analyze
from src.cli.main import cmd_list_rules
from src.cli.main import cmd_validate
from src.cli.main import main

# Patch targets — CLI uses lazy imports inside function bodies so we patch at source
_DM = "src.core.dataset_manager.DatasetManager"
_ANALYSIS = "src.services.analysis_service.AnalysisService"
_VALIDATION = "src.services.validation_service.ValidationService"


# ---------------------------------------------------------------------------
# build_parser — argument parsing correctness
# ---------------------------------------------------------------------------


class TestBuildParser:
    def setup_method(self):
        self.parser = build_parser()

    def test_chat_command_parses(self):
        args = self.parser.parse_args(["chat"])
        assert args.command == "chat"
        assert args.provider is None
        assert args.user_id is None
        assert args.context is None
        assert args.system_prompt is None

    def test_chat_accepts_all_options(self):
        args = self.parser.parse_args(
            ["chat", "--provider", "claude", "--user-id", "u1", "--context", "ctx", "--system-prompt", "be kind"]
        )
        assert args.provider == "claude"
        assert args.user_id == "u1"
        assert args.context == "ctx"
        assert args.system_prompt == "be kind"

    def test_analyze_default_hours(self):
        args = self.parser.parse_args(["analyze"])
        assert args.command == "analyze"
        assert args.hours == 24

    def test_analyze_custom_hours(self):
        args = self.parser.parse_args(["analyze", "--hours", "48"])
        assert args.hours == 48

    def test_validate_command_parses(self):
        args = self.parser.parse_args(["validate"])
        assert args.command == "validate"

    def test_list_rules_default_active_only(self):
        args = self.parser.parse_args(["list-rules"])
        assert args.command == "list-rules"
        assert args.all is False

    def test_list_rules_all_flag(self):
        args = self.parser.parse_args(["list-rules", "--all"])
        assert args.all is True

    def test_no_command_sets_command_none(self):
        args = self.parser.parse_args([])
        assert args.command is None


# ---------------------------------------------------------------------------
# _build_adapter
# ---------------------------------------------------------------------------


class TestBuildAdapter:
    def test_openai_returns_openai_adapter(self):
        with patch("src.adapters.openai_adapter.settings") as ms:
            ms.OPENAI_API_KEY = "k"
            ms.OPENAI_MODEL = "gpt-4o-mini"
            adapter = _build_adapter("openai")
        from src.adapters.openai_adapter import OpenAIAdapter

        assert isinstance(adapter, OpenAIAdapter)

    def test_claude_alias_accepted(self):
        with patch("src.adapters.claude_adapter.settings") as ms:
            ms.ANTHROPIC_API_KEY = "k"
            ms.ANTHROPIC_MODEL = "claude-3"
            adapter = _build_adapter("claude")
        from src.adapters.claude_adapter import ClaudeAdapter

        assert isinstance(adapter, ClaudeAdapter)

    def test_anthropic_alias_accepted(self):
        with patch("src.adapters.claude_adapter.settings") as ms:
            ms.ANTHROPIC_API_KEY = "k"
            ms.ANTHROPIC_MODEL = "claude-3"
            adapter = _build_adapter("anthropic")
        from src.adapters.claude_adapter import ClaudeAdapter

        assert isinstance(adapter, ClaudeAdapter)

    def test_unknown_provider_raises_value_error(self):
        with pytest.raises(ValueError, match="Unknown AI provider"):
            _build_adapter("gemini")


# ---------------------------------------------------------------------------
# cmd_analyze
# ---------------------------------------------------------------------------


class TestCmdAnalyze:
    def test_prints_zero_new_rules(self, capsys):
        args = MagicMock()
        args.hours = 24
        mock_service = MagicMock()
        mock_service.analyze_recent.return_value = []
        with patch(_DM):
            with patch("src.cli.main._build_adapter"):
                with patch(_ANALYSIS, return_value=mock_service):
                    with patch("src.cli.main.settings") as ms:
                        ms.DEFAULT_AI_PROVIDER = "openai"
                        cmd_analyze(args)
        out = capsys.readouterr().out
        assert "0" in out

    def test_prints_each_generated_rule(self, capsys):
        args = MagicMock()
        args.hours = 12
        rule = MagicMock()
        rule.rule_id = "rule-abc"
        rule.name = "no-repetition"
        rule.priority.name = "HIGH"
        mock_service = MagicMock()
        mock_service.analyze_recent.return_value = [rule]
        with patch(_DM):
            with patch("src.cli.main._build_adapter"):
                with patch(_ANALYSIS, return_value=mock_service):
                    with patch("src.cli.main.settings") as ms:
                        ms.DEFAULT_AI_PROVIDER = "openai"
                        cmd_analyze(args)
        out = capsys.readouterr().out
        assert "rule-abc" in out
        assert "no-repetition" in out
        assert "HIGH" in out

    def test_passes_lookback_hours_to_service(self):
        args = MagicMock()
        args.hours = 72
        mock_service = MagicMock()
        mock_service.analyze_recent.return_value = []
        with patch(_DM):
            with patch("src.cli.main._build_adapter"):
                with patch(_ANALYSIS, return_value=mock_service):
                    with patch("src.cli.main.settings") as ms:
                        ms.DEFAULT_AI_PROVIDER = "openai"
                        cmd_analyze(args)
        mock_service.analyze_recent.assert_called_once_with(lookback_hours=72)


# ---------------------------------------------------------------------------
# cmd_validate
# ---------------------------------------------------------------------------


class TestCmdValidate:
    def test_prints_zero_deactivated(self, capsys):
        args = MagicMock()
        mock_service = MagicMock()
        mock_service.validate_all_rules.return_value = []
        with patch(_DM):
            with patch(_VALIDATION, return_value=mock_service):
                cmd_validate(args)
        out = capsys.readouterr().out
        assert "0" in out

    def test_prints_each_deactivated_rule_id(self, capsys):
        args = MagicMock()
        mock_service = MagicMock()
        mock_service.validate_all_rules.return_value = ["rule-001", "rule-002"]
        with patch(_DM):
            with patch(_VALIDATION, return_value=mock_service):
                cmd_validate(args)
        out = capsys.readouterr().out
        assert "rule-001" in out
        assert "rule-002" in out


# ---------------------------------------------------------------------------
# cmd_list_rules
# ---------------------------------------------------------------------------


class TestCmdListRules:
    def test_prints_no_rules_message_when_empty(self, capsys):
        args = MagicMock()
        args.all = False
        mock_dm = MagicMock()
        mock_dm.load_rules.return_value = []
        with patch(_DM, return_value=mock_dm):
            cmd_list_rules(args)
        out = capsys.readouterr().out
        assert "No rules found" in out

    def test_prints_rule_table(self, capsys):
        args = MagicMock()
        args.all = False
        rule = MagicMock()
        rule.rule_id = "abc-123"
        rule.name = "test-rule"
        rule.priority.name = "HIGH"
        rule.effectiveness_score = 0.85
        rule.is_active = True
        mock_dm = MagicMock()
        mock_dm.load_rules.return_value = [rule]
        with patch(_DM, return_value=mock_dm):
            cmd_list_rules(args)
        out = capsys.readouterr().out
        assert "abc-123" in out
        assert "test-rule" in out
        assert "HIGH" in out
        assert "0.85" in out

    def test_inactive_rule_shows_flag(self, capsys):
        args = MagicMock()
        args.all = True
        rule = MagicMock()
        rule.rule_id = "xyz-999"
        rule.name = "inactive-rule"
        rule.priority.name = "LOW"
        rule.effectiveness_score = 0.1
        rule.is_active = False
        mock_dm = MagicMock()
        mock_dm.load_rules.return_value = [rule]
        with patch(_DM, return_value=mock_dm):
            cmd_list_rules(args)
        out = capsys.readouterr().out
        assert "[inactive]" in out

    def test_all_flag_passes_active_only_false(self):
        args = MagicMock()
        args.all = True
        mock_dm = MagicMock()
        mock_dm.load_rules.return_value = []
        with patch(_DM, return_value=mock_dm):
            cmd_list_rules(args)
        mock_dm.load_rules.assert_called_once_with(active_only=False)

    def test_default_passes_active_only_true(self):
        args = MagicMock()
        args.all = False
        mock_dm = MagicMock()
        mock_dm.load_rules.return_value = []
        with patch(_DM, return_value=mock_dm):
            cmd_list_rules(args)
        mock_dm.load_rules.assert_called_once_with(active_only=True)


# ---------------------------------------------------------------------------
# main() — top-level dispatch
# ---------------------------------------------------------------------------


class TestMain:
    def test_no_args_prints_help_and_exits_zero(self):
        with pytest.raises(SystemExit) as exc_info:
            main([])
        assert exc_info.value.code == 0

    def test_dispatches_to_analyze(self):
        mock_service = MagicMock()
        mock_service.analyze_recent.return_value = []
        with patch(_DM):
            with patch("src.cli.main._build_adapter"):
                with patch(_ANALYSIS, return_value=mock_service):
                    with patch("src.cli.main.settings") as ms:
                        ms.DEFAULT_AI_PROVIDER = "openai"
                        main(["analyze", "--hours", "6"])
        mock_service.analyze_recent.assert_called_once_with(lookback_hours=6)

    def test_dispatches_to_validate(self):
        mock_service = MagicMock()
        mock_service.validate_all_rules.return_value = []
        with patch(_DM):
            with patch(_VALIDATION, return_value=mock_service):
                main(["validate"])
        mock_service.validate_all_rules.assert_called_once()

    def test_dispatches_to_list_rules(self):
        mock_dm = MagicMock()
        mock_dm.load_rules.return_value = []
        with patch(_DM, return_value=mock_dm):
            main(["list-rules"])
        mock_dm.load_rules.assert_called_once()

    def test_keyboard_interrupt_exits_zero(self):
        mock_service = MagicMock()
        mock_service.validate_all_rules.side_effect = KeyboardInterrupt()
        with patch(_DM):
            with patch(_VALIDATION, return_value=mock_service):
                with pytest.raises(SystemExit) as exc_info:
                    main(["validate"])
        assert exc_info.value.code == 0

    def test_unhandled_exception_exits_one(self):
        mock_service = MagicMock()
        mock_service.validate_all_rules.side_effect = RuntimeError("crash")
        with patch(_DM):
            with patch(_VALIDATION, return_value=mock_service):
                with pytest.raises(SystemExit) as exc_info:
                    main(["validate"])
        assert exc_info.value.code == 1
