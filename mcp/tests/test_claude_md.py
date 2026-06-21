"""Tests for ~/.claude/CLAUDE.md write/update/remove logic."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from ai_rule_learning_mcp.claude_md import (
    _START,
    _END,
    _build_section,
    remove_rules,
    write_rules,
    read_injected_rules,
)

_RULE = {
    "rule_id": "rul_abc",
    "name": "test-rule",
    "priority": 4,
    "priority_label": "HIGH",
    "action": {"instruction": "Do the right thing always."},
    "is_active": True,
}


def _tmp_md(content: str = "") -> Path:
    d = tempfile.mkdtemp()
    p = Path(d) / ".claude" / "CLAUDE.md"
    p.parent.mkdir(parents=True)
    if content:
        p.write_text(content)
    return p


class TestBuildSection:
    def test_contains_start_and_end_markers(self):
        section = _build_section([_RULE])
        assert _START in section
        assert _END in section

    def test_rule_name_appears(self):
        section = _build_section([_RULE])
        assert "test-rule" in section

    def test_instruction_appears(self):
        section = _build_section([_RULE])
        assert "Do the right thing" in section

    def test_priority_label_appears(self):
        section = _build_section([_RULE])
        assert "HIGH" in section

    def test_empty_rules_still_has_markers(self):
        section = _build_section([])
        assert _START in section
        assert _END in section

    def test_integer_priority_maps_to_label(self):
        rule = {**_RULE, "priority": 5, "priority_label": None}
        section = _build_section([rule])
        assert "CRITICAL" in section


class TestWriteRules:
    def test_creates_file_if_missing(self):
        with tempfile.TemporaryDirectory() as d:
            md_path = Path(d) / ".claude" / "CLAUDE.md"
            with patch("ai_rule_learning_mcp.claude_md.claude_md_path", return_value=md_path):
                result = write_rules([_RULE])
            assert result == md_path
            assert md_path.exists()
            text = md_path.read_text()
            assert _START in text
            assert "test-rule" in text

    def test_replaces_existing_section(self):
        existing = f"# My notes\n\n{_START}\n- old rule\n{_END}\n\nMore notes."
        with tempfile.TemporaryDirectory() as d:
            md_path = Path(d) / ".claude" / "CLAUDE.md"
            md_path.parent.mkdir(parents=True)
            md_path.write_text(existing)
            with patch("ai_rule_learning_mcp.claude_md.claude_md_path", return_value=md_path):
                write_rules([_RULE])
            text = md_path.read_text()
            assert "old rule" not in text
            assert "test-rule" in text
            assert "My notes" in text
            assert "More notes." in text

    def test_appends_section_to_existing_file_without_section(self):
        with tempfile.TemporaryDirectory() as d:
            md_path = Path(d) / ".claude" / "CLAUDE.md"
            md_path.parent.mkdir(parents=True)
            md_path.write_text("# Existing content\n")
            with patch("ai_rule_learning_mcp.claude_md.claude_md_path", return_value=md_path):
                write_rules([_RULE])
            text = md_path.read_text()
            assert "# Existing content" in text
            assert _START in text

    def test_section_appears_exactly_once(self):
        with tempfile.TemporaryDirectory() as d:
            md_path = Path(d) / ".claude" / "CLAUDE.md"
            md_path.parent.mkdir(parents=True)
            with patch("ai_rule_learning_mcp.claude_md.claude_md_path", return_value=md_path):
                write_rules([_RULE])
                write_rules([_RULE])  # second write
            text = md_path.read_text()
            assert text.count(_START) == 1


class TestRemoveRules:
    def test_removes_section(self):
        section = _build_section([_RULE])
        with tempfile.TemporaryDirectory() as d:
            md_path = Path(d) / ".claude" / "CLAUDE.md"
            md_path.parent.mkdir(parents=True)
            md_path.write_text(f"# Notes\n\n{section}\n\nMore.\n")
            with patch("ai_rule_learning_mcp.claude_md.claude_md_path", return_value=md_path):
                removed = remove_rules()
            assert removed is True
            text = md_path.read_text()
            assert _START not in text
            assert "# Notes" in text

    def test_returns_false_if_no_section(self):
        with tempfile.TemporaryDirectory() as d:
            md_path = Path(d) / ".claude" / "CLAUDE.md"
            md_path.parent.mkdir(parents=True)
            md_path.write_text("# Notes\n")
            with patch("ai_rule_learning_mcp.claude_md.claude_md_path", return_value=md_path):
                assert remove_rules() is False

    def test_returns_false_if_file_missing(self):
        with tempfile.TemporaryDirectory() as d:
            md_path = Path(d) / ".claude" / "MISSING.md"
            with patch("ai_rule_learning_mcp.claude_md.claude_md_path", return_value=md_path):
                assert remove_rules() is False


class TestReadInjectedRules:
    def test_reads_injected_bullet_lines(self):
        section = _build_section([_RULE])
        with tempfile.TemporaryDirectory() as d:
            md_path = Path(d) / ".claude" / "CLAUDE.md"
            md_path.parent.mkdir(parents=True)
            md_path.write_text(section)
            with patch("ai_rule_learning_mcp.claude_md.claude_md_path", return_value=md_path):
                lines = read_injected_rules()
        assert len(lines) == 1
        assert "test-rule" in lines[0]

    def test_empty_if_no_section(self):
        with tempfile.TemporaryDirectory() as d:
            md_path = Path(d) / ".claude" / "CLAUDE.md"
            md_path.parent.mkdir(parents=True)
            md_path.write_text("# Notes\n")
            with patch("ai_rule_learning_mcp.claude_md.claude_md_path", return_value=md_path):
                assert read_injected_rules() == []
