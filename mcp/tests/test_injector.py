"""Tests for the universal multi-agent rule injector."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from ai_rule_learning_mcp.injector import (
    _ALL_TARGETS,
    _AgentsmdTarget,
    _ClaudeCodeTarget,
    _CodexTarget,
    _CopilotTarget,
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


class TestHomeFlatFileInjection:
    """M02: ~/.cursorrules and ~/.windsurfrules must be detected and updated even
    when the server's working directory is a different, unrelated folder. Before
    the fix the flat files were only ever looked for in Path.cwd(), so they were
    silently skipped while the home-based configs (CLAUDE.md, copilot) updated —
    the "injected across 2/4 environments" failure.
    """

    def test_cursor_home_flat_file_detected_and_written(self, tmp_path, monkeypatch):
        home = tmp_path / "home"
        work = tmp_path / "work"
        home.mkdir()
        work.mkdir()
        (home / ".cursorrules").write_text("my cursor rules\n")
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
        monkeypatch.chdir(work)

        target = _CursorTarget()
        assert target.is_detected()
        assert (home / ".cursorrules") in target._all_paths()

        target.write([_RULE])
        assert "test-rule" in (home / ".cursorrules").read_text()

    def test_windsurf_home_flat_file_detected_and_written(self, tmp_path, monkeypatch):
        home = tmp_path / "home"
        work = tmp_path / "work"
        home.mkdir()
        work.mkdir()
        (home / ".windsurfrules").write_text("my windsurf rules\n")
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
        monkeypatch.chdir(work)

        target = _WindsurfTarget()
        assert target.is_detected()
        assert (home / ".windsurfrules") in target._all_paths()

        target.write([_RULE])
        assert "test-rule" in (home / ".windsurfrules").read_text()


class TestAgentsmdTarget:
    """Phase 2: AGENTS.md (the cross-tool standard) is a first-class target —
    honored when present at the project root or in the home directory."""

    def test_project_root_agents_md_detected_and_written(self, tmp_path, monkeypatch):
        home = tmp_path / "home"
        proj = tmp_path / "proj"
        home.mkdir()
        proj.mkdir()
        (proj / "AGENTS.md").write_text("# Project agent instructions\n")
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
        monkeypatch.chdir(proj)

        target = _AgentsmdTarget()
        assert target.is_detected()
        assert (proj / "AGENTS.md") in target._all_paths()

        target.write([_RULE])
        text = (proj / "AGENTS.md").read_text()
        assert "test-rule" in text
        # User content is preserved.
        assert "Project agent instructions" in text

    def test_home_agents_md_detected_from_foreign_cwd(self, tmp_path, monkeypatch):
        home = tmp_path / "home"
        work = tmp_path / "work"
        home.mkdir()
        work.mkdir()
        (home / "AGENTS.md").write_text("# Global agent instructions\n")
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
        monkeypatch.chdir(work)

        target = _AgentsmdTarget()
        assert target.is_detected()
        assert (home / "AGENTS.md") in target._all_paths()

        target.write([_RULE])
        assert "test-rule" in (home / "AGENTS.md").read_text()

    def test_not_detected_when_absent(self, tmp_path, monkeypatch):
        home = tmp_path / "home"
        work = tmp_path / "work"
        home.mkdir()
        work.mkdir()
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
        monkeypatch.chdir(work)

        # No AGENTS.md anywhere -> not detected, so nothing is created unprompted.
        assert not _AgentsmdTarget().is_detected()


# Minimal home-side artifact that should make each target detect + write under
# $HOME regardless of the current working directory. This is the regression
# guard for the M02 class of bug (config present in HOME, server cwd elsewhere).
_HOME_SETUPS = [
    ("claude", _ClaudeCodeTarget, lambda h: (h / ".claude").mkdir()),
    ("cursor", _CursorTarget, lambda h: (h / ".cursorrules").write_text("x\n")),
    ("windsurf", _WindsurfTarget, lambda h: (h / ".windsurfrules").write_text("x\n")),
    ("copilot", _CopilotTarget, lambda h: (h / ".github").mkdir()),
    ("codex", _CodexTarget, lambda h: (h / ".codex").mkdir()),
    ("agents", _AgentsmdTarget, lambda h: (h / "AGENTS.md").write_text("x\n")),
]


class TestHomeCoverageAudit:
    """Phase 2 audit guard: every target must reach a HOME config even when the
    server runs from an unrelated working directory. Locks in the home/cwd
    coverage so the M02 class of bug cannot silently return for any target.
    """

    @pytest.mark.parametrize(
        "label,target_cls,setup",
        _HOME_SETUPS,
        ids=[s[0] for s in _HOME_SETUPS],
    )
    def test_target_reaches_home_from_foreign_cwd(self, label, target_cls, setup, tmp_path, monkeypatch):
        home = tmp_path / "home"
        work = tmp_path / "work"
        home.mkdir()
        work.mkdir()
        setup(home)
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
        monkeypatch.chdir(work)

        target = target_cls()
        assert target.is_detected(), f"{label}: not detected from a foreign cwd"
        target.write([_RULE])

        hits = [p for p in home.rglob("*") if p.is_file() and "test-rule" in p.read_text(encoding="utf-8")]
        assert hits, f"{label}: no HOME file received the rule"
