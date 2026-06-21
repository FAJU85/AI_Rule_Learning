"""Tests for the universal multi-agent rule injector."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from ai_rule_learning_mcp.injector import (
    _ALL_TARGETS,
    _ClaudeCodeTarget,
    _CursorTarget,
    _WindsurfTarget,
    _build_section,
    format_rules_block,
    read_injected_rules,
    remove_rules_all,
    write_rules_all,
)

_RULE = {
    "rule_id": "rul_test",
    "name": "test-rule",
    "priority": 4,
    "priority_label": "HIGH",
    "action": {"instruction": "Do the right thing."},
    "is_active": True,
}


def _patched_targets(tmp: Path) -> list:
    """Return target instances all pointing into a temp directory."""

    class _FakeClaudeCode(_ClaudeCodeTarget):
        def config_path(self):
            return tmp / ".claude" / "CLAUDE.md"

        def is_detected(self):
            return True

    class _FakeCursor(_CursorTarget):
        def config_path(self):
            return tmp / ".cursor" / "rules" / "ai-guardrails.md"

        def is_detected(self):
            return True

    class _FakeWindsurf(_WindsurfTarget):
        def config_path(self):
            return tmp / ".windsurf" / "rules" / "ai-guardrails.md"

        def is_detected(self):
            return True

    return [_FakeClaudeCode(), _FakeCursor(), _FakeWindsurf()]


class TestBuildSection:
    def test_has_markers(self):
        s = _build_section([_RULE])
        assert "<!-- AI-Rule-Learning:start -->" in s
        assert "<!-- AI-Rule-Learning:end -->" in s

    def test_rule_name_appears(self):
        assert "test-rule" in _build_section([_RULE])

    def test_instruction_appears(self):
        assert "Do the right thing" in _build_section([_RULE])

    def test_empty_rules_still_has_markers(self):
        s = _build_section([])
        assert "start" in s and "end" in s


class TestWriteRulesAll:
    def test_writes_to_all_detected_targets(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            targets = _patched_targets(tmp)
            with patch("ai_rule_learning_mcp.injector._ALL_TARGETS", targets):
                results = write_rules_all([_RULE])
            assert len(results) == 3
            for name, path in results:
                assert path.exists()
                assert "test-rule" in path.read_text()

    def test_creates_parent_dirs(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            targets = _patched_targets(tmp)
            cursor_path = tmp / ".cursor" / "rules" / "ai-guardrails.md"
            assert not cursor_path.exists()
            with patch("ai_rule_learning_mcp.injector._ALL_TARGETS", targets):
                write_rules_all([_RULE])
            assert cursor_path.exists()

    def test_replaces_existing_section(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            targets = _patched_targets(tmp)
            with patch("ai_rule_learning_mcp.injector._ALL_TARGETS", targets):
                write_rules_all([_RULE])
                old_rule = {**_RULE, "name": "old-rule"}
                write_rules_all([old_rule])
            text = (tmp / ".claude" / "CLAUDE.md").read_text()
            assert "old-rule" in text
            assert "test-rule" not in text
            assert text.count("AI-Rule-Learning:start") == 1

    def test_skips_undetected_targets(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)

            class _NeverDetected(_ClaudeCodeTarget):
                def config_path(self):
                    return tmp / ".claude" / "CLAUDE.md"

                def is_detected(self):
                    return False

            with patch("ai_rule_learning_mcp.injector._ALL_TARGETS", [_NeverDetected()]):
                results = write_rules_all([_RULE])
            assert results == []


class TestRemoveRulesAll:
    def test_removes_from_all_targets(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            targets = _patched_targets(tmp)
            with patch("ai_rule_learning_mcp.injector._ALL_TARGETS", targets):
                write_rules_all([_RULE])
                removed = remove_rules_all()
            assert len(removed) == 3

    def test_returns_empty_if_no_sections(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            targets = _patched_targets(tmp)
            with patch("ai_rule_learning_mcp.injector._ALL_TARGETS", targets):
                removed = remove_rules_all()
            assert removed == []


class TestReadInjectedRules:
    def test_reads_from_first_target_with_content(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            targets = _patched_targets(tmp)
            with patch("ai_rule_learning_mcp.injector._ALL_TARGETS", targets):
                write_rules_all([_RULE])
                lines = read_injected_rules()
            assert len(lines) == 1
            assert "test-rule" in lines[0]

    def test_empty_when_no_targets_have_rules(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            targets = _patched_targets(tmp)
            with patch("ai_rule_learning_mcp.injector._ALL_TARGETS", targets):
                assert read_injected_rules() == []


class TestFormatRulesBlock:
    def test_returns_string(self):
        block = format_rules_block([_RULE])
        assert "test-rule" in block
        assert "HIGH" in block

    def test_empty_rules_message(self):
        assert "No active" in format_rules_block([])
