"""Tests for persistent user memory."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from ai_rule_learning_mcp.memory import (
    add_memory,
    build_memory_block,
    clear_memory,
    forget,
    load_memory,
    format_memory_for_display,
)


def _tmp_store(tmp: Path):
    """Patch LOCAL_DIR to a temp directory."""
    from ai_rule_learning_mcp import store
    from ai_rule_learning_mcp import memory as mem_mod

    class _FakeStore:
        LOCAL_DIR = tmp

    return patch.object(mem_mod, "_memory_file", lambda: tmp / "memory.jsonl")


class TestAddMemory:
    def test_adds_entry(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            with patch("ai_rule_learning_mcp.memory._memory_file", return_value=tmp / "memory.jsonl"):
                entry = add_memory("preference", "Always use type hints")
            assert entry["type"] == "preference"
            assert entry["content"] == "Always use type hints"
            assert "added_at" in entry

    def test_invalid_type_falls_back_to_context(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            with patch("ai_rule_learning_mcp.memory._memory_file", return_value=tmp / "memory.jsonl"):
                entry = add_memory("unknown_type", "some fact")
            assert entry["type"] == "context"

    def test_multiple_entries_persisted(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            mf = tmp / "memory.jsonl"
            with patch("ai_rule_learning_mcp.memory._memory_file", return_value=mf):
                add_memory("preference", "Python 3.10+")
                add_memory("never", "Never use globals")
                entries = load_memory()
            assert len(entries) == 2

    def test_empty_content_raises(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            with patch("ai_rule_learning_mcp.memory._memory_file", return_value=tmp / "memory.jsonl"):
                try:
                    add_memory("preference", "   ")
                    assert False, "Should have raised"
                except ValueError:
                    pass


class TestLoadMemory:
    def test_empty_file_returns_empty(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            with patch("ai_rule_learning_mcp.memory._memory_file", return_value=tmp / "memory.jsonl"):
                assert load_memory() == []

    def test_missing_file_returns_empty(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            mf = tmp / "nonexistent" / "memory.jsonl"
            with patch("ai_rule_learning_mcp.memory._memory_file", return_value=mf):
                assert load_memory() == []

    def test_corrupted_line_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            mf = tmp / "memory.jsonl"
            mf.write_text('{"type":"preference","content":"ok","added_at":"x"}\nNOT_JSON\n')
            with patch("ai_rule_learning_mcp.memory._memory_file", return_value=mf):
                entries = load_memory()
            assert len(entries) == 1
            assert entries[0]["content"] == "ok"


class TestForget:
    def test_forget_by_type(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            mf = tmp / "memory.jsonl"
            with patch("ai_rule_learning_mcp.memory._memory_file", return_value=mf):
                add_memory("preference", "keep this")
                add_memory("never", "remove this")
                removed = forget(memory_type="never")
                entries = load_memory()
            assert removed == 1
            assert len(entries) == 1
            assert entries[0]["type"] == "preference"

    def test_forget_by_content_substr(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            mf = tmp / "memory.jsonl"
            with patch("ai_rule_learning_mcp.memory._memory_file", return_value=mf):
                add_memory("preference", "use type hints")
                add_memory("preference", "use async everywhere")
                removed = forget(content_substr="async")
                entries = load_memory()
            assert removed == 1
            assert "async" not in entries[0]["content"]

    def test_forget_no_match_returns_zero(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            mf = tmp / "memory.jsonl"
            with patch("ai_rule_learning_mcp.memory._memory_file", return_value=mf):
                add_memory("preference", "something")
                removed = forget(memory_type="never")
            assert removed == 0


class TestClearMemory:
    def test_clears_all(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            mf = tmp / "memory.jsonl"
            with patch("ai_rule_learning_mcp.memory._memory_file", return_value=mf):
                add_memory("preference", "a")
                add_memory("never", "b")
                n = clear_memory()
                entries = load_memory()
            assert n == 2
            assert entries == []

    def test_clear_missing_file_returns_zero(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            mf = tmp / "memory.jsonl"
            with patch("ai_rule_learning_mcp.memory._memory_file", return_value=mf):
                assert clear_memory() == 0


class TestBuildMemoryBlock:
    def test_empty_entries_returns_empty_string(self):
        assert build_memory_block([]) == ""

    def test_contains_markers(self):
        entries = [{"type": "preference", "content": "use type hints", "added_at": "x"}]
        block = build_memory_block(entries)
        assert "AI-Rule-Learning:memory:start" in block
        assert "AI-Rule-Learning:memory:end" in block

    def test_preference_appears(self):
        entries = [{"type": "preference", "content": "always use Python 3.10", "added_at": "x"}]
        assert "always use Python 3.10" in build_memory_block(entries)

    def test_never_section_appears(self):
        entries = [{"type": "never", "content": "never commit to main", "added_at": "x"}]
        block = build_memory_block(entries)
        assert "Never Do" in block
        assert "never commit to main" in block

    def test_multiple_types_all_present(self):
        entries = [
            {"type": "preference", "content": "type hints", "added_at": "x"},
            {"type": "project", "content": "AI Rule Learning", "added_at": "x"},
            {"type": "never", "content": "no globals", "added_at": "x"},
        ]
        block = build_memory_block(entries)
        assert "type hints" in block
        assert "AI Rule Learning" in block
        assert "no globals" in block


class TestFormatMemoryForDisplay:
    def test_no_entries_message(self):
        result = format_memory_for_display([])
        assert "No memory" in result

    def test_shows_count(self):
        entries = [
            {"type": "preference", "content": "x", "added_at": "y"},
            {"type": "never", "content": "z", "added_at": "y"},
        ]
        result = format_memory_for_display(entries)
        assert "2" in result
