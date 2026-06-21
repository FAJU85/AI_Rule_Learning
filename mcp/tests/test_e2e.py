"""End-to-end tests — full user journeys, real files, no mocked internals.

Each test exercises a complete pipeline from input to observable output:

  1. Sync journey       session file → gap detection → rules → agent config
  2. Feedback journey   record_feedback → rule → agent config (real-time)
  3. Memory journey     remember → agent config → recall
  4. Skills journey     save_skill → agent config index → get_skill
  5. Full combined      all pillars written to a single config in the right order
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# ── fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture()
def store_dir(tmp_path, monkeypatch):
    """Redirect all local storage to a temp dir."""
    d = tmp_path / "store"
    d.mkdir()
    monkeypatch.setattr("ai_rule_learning_mcp.store.LOCAL_DIR", d)
    monkeypatch.setenv("HF_TOKEN", "")
    monkeypatch.setenv("ARL_DATASET", "")
    return d


@pytest.fixture()
def skills_dir(tmp_path, monkeypatch):
    """Redirect skills storage to a temp dir."""
    d = tmp_path / "skills"
    d.mkdir()
    monkeypatch.setattr("ai_rule_learning_mcp.skills._skills_dir", lambda: d)
    return d


@pytest.fixture()
def agent_config(tmp_path):
    """Return a fake Claude Code config path (no pre-existing content)."""
    return tmp_path / "CLAUDE.md"


@pytest.fixture()
def session_file(tmp_path):
    """Write a realistic Claude Code session JSONL with friction patterns."""
    lines = []
    # Turn 1 — user corrects the agent
    lines.append(json.dumps({
        "sessionId": "e2e-session-1",
        "slug": "e2e-test",
        "cwd": "/home/user/project",
        "timestamp": "2026-06-21T10:00:00",
        "message": {"role": "user", "content": "Write a function to parse dates"},
    }))
    lines.append(json.dumps({
        "sessionId": "e2e-session-1",
        "message": {
            "role": "assistant",
            "content": "Here is a date parser: def parse(s): return s",
        },
    }))
    # Turn 2 — explicit correction
    lines.append(json.dumps({
        "sessionId": "e2e-session-1",
        "message": {
            "role": "user",
            "content": "No that's wrong, actually I need it to handle ISO format",
        },
    }))
    lines.append(json.dumps({
        "sessionId": "e2e-session-1",
        "message": {
            "role": "assistant",
            "content": "from datetime import datetime; def parse(s): return datetime.fromisoformat(s)",
        },
    }))
    # Turn 3 — repeated context
    lines.append(json.dumps({
        "sessionId": "e2e-session-1",
        "message": {
            "role": "user",
            "content": "As I mentioned before, I'm using Python 3.10",
        },
    }))
    lines.append(json.dumps({
        "sessionId": "e2e-session-1",
        "message": {"role": "assistant", "content": "Got it, Python 3.10 compatible solution:"},
    }))
    # Turn 4 — more turns to meet minimum
    lines.append(json.dumps({
        "sessionId": "e2e-session-1",
        "message": {"role": "user", "content": "Add error handling please"},
    }))
    lines.append(json.dumps({
        "sessionId": "e2e-session-1",
        "message": {"role": "assistant", "content": "def parse(s):\n    try:\n        return datetime.fromisoformat(s)\n    except ValueError:\n        return None"},
    }))

    p = tmp_path / "e2e-session-1.jsonl"
    p.write_text("\n".join(lines), encoding="utf-8")
    return p


# ── 1. Sync journey ────────────────────────────────────────────────────────


def test_sync_journey_end_to_end(session_file, store_dir, agent_config, monkeypatch):
    """
    Full sync: parse session → detect gaps → generate rules → write to config.
    The config file must contain an active guardrails block with at least one rule.
    """
    from ai_rule_learning_mcp.gap_detector import analyze_conversations
    from ai_rule_learning_mcp.injector import _START, _END, _build_section
    from ai_rule_learning_mcp.providers import parse_any
    from ai_rule_learning_mcp.store import _local_load, _local_save, load_active_rules

    # Step 1: parse the session
    conversations = parse_any(session_file)
    assert len(conversations) == 1
    assert len(conversations[0]["turns"]) >= 2

    # Step 2: detect gaps and generate rules
    rules = analyze_conversations(conversations)
    assert len(rules) >= 1, "at least one rule should be generated from explicit correction"

    # Step 3: persist rules locally
    _local_save("rules.jsonl", rules)
    active = load_active_rules()
    assert len(active) >= 1

    # Step 4: write to the agent config
    section = _build_section(active)
    agent_config.write_text(section + "\n", encoding="utf-8")

    content = agent_config.read_text()
    assert _START in content
    assert _END in content
    # At least one rule bullet should be present
    assert "- **[" in content


def test_sync_deduplicates_processed_files(session_file, store_dir, monkeypatch):
    """A session file processed once should not be counted again on re-run."""
    from ai_rule_learning_mcp.store import is_already_processed, mark_processed

    assert not is_already_processed(session_file)
    mark_processed(session_file)
    assert is_already_processed(session_file)

    # Marking again must not create duplicate entries
    mark_processed(session_file)
    from ai_rule_learning_mcp.store import _local_load
    processed = _local_load("processed.jsonl")
    assert len([r for r in processed if r["path"] == str(session_file.resolve())]) == 1


def test_sync_rules_are_idempotent(store_dir, agent_config):
    """Writing the same rules twice must not duplicate the guardrails block."""
    from ai_rule_learning_mcp.injector import _START, _upsert, _build_section, _SECTION_RE

    rules = [{"rule_id": "r1", "name": "Use type hints", "priority": 3, "is_active": True}]
    section = _build_section(rules)

    _upsert(agent_config, section, _SECTION_RE, _START)
    _upsert(agent_config, section, _SECTION_RE, _START)

    content = agent_config.read_text()
    assert content.count(_START) == 1


# ── 2. Feedback journey ────────────────────────────────────────────────────


def test_feedback_journey_creates_rule_in_config(store_dir, agent_config, monkeypatch):
    """
    record_feedback equivalent: gap + rule generation → write to config.
    Simulates what the MCP tool does in real time.
    """
    from ai_rule_learning_mcp.gap_detector import generate_rules
    from ai_rule_learning_mcp.injector import _START, write_rules_all
    from ai_rule_learning_mcp.store import _local_load, _local_save, load_active_rules

    # Patch detected_targets to use our temp config
    from ai_rule_learning_mcp import injector

    class _FakeTarget:
        name = "Claude Code"
        def config_path(self): return agent_config
        def is_detected(self): return True
        def write(self, rules, memory_block="", skills_block=""):
            from ai_rule_learning_mcp.injector import _upsert, _build_section, _SECTION_RE
            _upsert(agent_config, _build_section(rules), _SECTION_RE, _START)
            return agent_config

    monkeypatch.setattr(injector, "_ALL_TARGETS", [_FakeTarget()])

    # Simulate a correction feedback
    gaps = {"explicit_correction": [{"turn": 1, "signal": "correction", "snippet": "No, that's wrong"}]}
    rules = generate_rules(gaps)
    assert rules

    existing = _local_load("rules.jsonl")
    _local_save("rules.jsonl", existing + rules)
    active = load_active_rules()
    written = write_rules_all(active)

    assert len(written) == 1
    content = agent_config.read_text()
    assert _START in content
    assert "- **[" in content


# ── 3. Memory journey ─────────────────────────────────────────────────────


def test_memory_journey_remember_recall(store_dir, agent_config, monkeypatch):
    """
    remember: add entries → write block to config.
    recall: load entries → formatted display.
    """
    from ai_rule_learning_mcp.memory import (
        add_memory,
        build_memory_block,
        format_memory_for_display,
        load_memory,
    )
    from ai_rule_learning_mcp.injector import _MEM_START, _MEM_END, _upsert, _MEM_RE

    # Remember two facts
    add_memory("preference", "Always use type hints in Python")
    add_memory("context", "Project uses FastAPI + PostgreSQL")
    add_memory("never", "Never use bare except clauses")

    entries = load_memory()
    assert len(entries) == 3

    # Write memory block to agent config
    block = build_memory_block(entries)
    assert _MEM_START in block
    assert _MEM_END in block
    assert "type hints" in block
    assert "FastAPI" in block
    assert "bare except" in block

    _upsert(agent_config, block, _MEM_RE, _MEM_START)
    content = agent_config.read_text()
    assert _MEM_START in content
    assert "type hints" in content

    # Recall: formatted display
    display = format_memory_for_display(entries)
    assert "Preferences" in display
    assert "type hints" in display
    assert "Never Do" in display


def test_memory_is_grouped_by_type(store_dir):
    """Memory entries should be grouped by type in the display output."""
    from ai_rule_learning_mcp.memory import add_memory, format_memory_for_display, load_memory

    add_memory("preference", "Dark mode")
    add_memory("preference", "Tabs not spaces")
    add_memory("project", "Building a CLI tool")

    entries = load_memory()
    display = format_memory_for_display(entries)

    assert "Preferences" in display
    assert "Dark mode" in display
    assert "Tabs not spaces" in display
    assert "Active Projects" in display
    assert "CLI tool" in display


def test_memory_block_updates_idempotently(store_dir, agent_config):
    """Writing memory twice must not duplicate the memory block."""
    from ai_rule_learning_mcp.memory import add_memory, build_memory_block, load_memory
    from ai_rule_learning_mcp.injector import _MEM_START, _upsert, _MEM_RE

    add_memory("preference", "Use black for formatting")
    entries = load_memory()
    block = build_memory_block(entries)

    _upsert(agent_config, block, _MEM_RE, _MEM_START)
    _upsert(agent_config, block, _MEM_RE, _MEM_START)

    content = agent_config.read_text()
    assert content.count(_MEM_START) == 1


# ── 4. Skills journey ────────────────────────────────────────────────────


def test_skills_journey_save_index_retrieve(skills_dir, agent_config):
    """
    save_skill → build index → write to config → get_skill returns steps.
    """
    from ai_rule_learning_mcp.skills import (
        build_skills_index,
        get_skill,
        list_skills,
        save_skill,
    )
    from ai_rule_learning_mcp.injector import _SKILLS_START, _SKILLS_END, _upsert, _SKILLS_RE

    # Save two skills
    save_skill(
        "Deploy to HuggingFace",
        "Deploy a Gradio Space to HF",
        "## Steps\n1. `git add .`\n2. `git commit -m 'update'`\n3. `git push`",
        triggers=["deploy", "push to hf"],
    )
    save_skill(
        "Create FastAPI Endpoint",
        "Add a new REST endpoint",
        "## Steps\n1. Define route in `router.py`\n2. Add schema\n3. Write tests",
        triggers=["new endpoint", "add route"],
    )

    skills = list_skills()
    assert len(skills) == 2

    # Build and write index to config
    index = build_skills_index(skills)
    assert _SKILLS_START in index
    assert _SKILLS_END in index
    assert "Deploy to HuggingFace" in index
    assert "Create FastAPI Endpoint" in index

    _upsert(agent_config, index, _SKILLS_RE, _SKILLS_START)
    content = agent_config.read_text()
    assert "Deploy to HuggingFace" in content
    assert "deploy, push to hf" in content

    # Retrieve full steps
    skill = get_skill("Deploy to HuggingFace")
    assert skill is not None
    assert "git push" in skill["steps"]
    assert skill["used_count"] == 1

    # Fuzzy retrieval
    skill2 = get_skill("fastapi")
    assert skill2 is not None
    assert "FastAPI" in skill2["name"]


def test_skills_index_updates_idempotently(skills_dir, agent_config):
    """Writing skills index twice must not duplicate the block."""
    from ai_rule_learning_mcp.skills import build_skills_index, list_skills, save_skill
    from ai_rule_learning_mcp.injector import _SKILLS_START, _upsert, _SKILLS_RE

    save_skill("Skill A", "desc", "steps")
    skills = list_skills()
    index = build_skills_index(skills)

    _upsert(agent_config, index, _SKILLS_RE, _SKILLS_START)
    _upsert(agent_config, index, _SKILLS_RE, _SKILLS_START)

    content = agent_config.read_text()
    assert content.count(_SKILLS_START) == 1


# ── 5. Full combined journey ───────────────────────────────────────────────


def test_all_pillars_write_to_single_config(store_dir, skills_dir, agent_config, monkeypatch):
    """
    All three sections (memory, skills, rules) written to one config file
    in the correct order: memory → skills → rules.
    """
    from ai_rule_learning_mcp.memory import add_memory, build_memory_block, load_memory
    from ai_rule_learning_mcp.skills import build_skills_index, list_skills, save_skill
    from ai_rule_learning_mcp.store import _local_save
    from ai_rule_learning_mcp.injector import (
        _MEM_START, _MEM_END,
        _SKILLS_START, _SKILLS_END,
        _START, _END,
        _upsert, _MEM_RE, _SKILLS_RE, _SECTION_RE,
        _build_section,
    )

    # Memory
    add_memory("preference", "Use ruff for linting")
    mem_block = build_memory_block(load_memory())
    _upsert(agent_config, mem_block, _MEM_RE, _MEM_START)

    # Skills
    save_skill("Run Tests", "Run the full test suite", "pytest -v")
    skills_block = build_skills_index(list_skills())
    _upsert(agent_config, skills_block, _SKILLS_RE, _SKILLS_START)

    # Rules
    rules = [{"rule_id": "r1", "name": "Always use ruff", "priority": 4, "is_active": True,
               "instruction": "Run ruff check before committing"}]
    _local_save("rules.jsonl", rules)
    _upsert(agent_config, _build_section(rules), _SECTION_RE, _START)

    content = agent_config.read_text()

    # All three sections present
    assert _MEM_START in content
    assert _MEM_END in content
    assert _SKILLS_START in content
    assert _SKILLS_END in content
    assert _START in content
    assert _END in content

    # Content is correct
    assert "ruff" in content
    assert "Run Tests" in content
    assert "Always use ruff" in content

    # Memory appears before skills, skills before rules
    mem_pos = content.index(_MEM_START)
    skills_pos = content.index(_SKILLS_START)
    rules_pos = content.index(_START)
    assert mem_pos < skills_pos < rules_pos


def test_e2e_remove_clears_all_sections(store_dir, skills_dir, agent_config):
    """After writing all sections, remove() must leave the file clean."""
    from ai_rule_learning_mcp.memory import add_memory, build_memory_block, load_memory
    from ai_rule_learning_mcp.skills import build_skills_index, list_skills, save_skill
    from ai_rule_learning_mcp.injector import (
        _MEM_START, _SKILLS_START, _START,
        _upsert, _remove,
        _MEM_RE, _SKILLS_RE, _SECTION_RE,
        _build_section,
    )

    # Write all three sections
    add_memory("preference", "Use black")
    _upsert(agent_config, build_memory_block(load_memory()), _MEM_RE, _MEM_START)

    save_skill("Test Skill", "desc", "steps")
    _upsert(agent_config, build_skills_index(list_skills()), _SKILLS_RE, _SKILLS_START)

    rules = [{"rule_id": "r1", "name": "Rule A", "priority": 3, "is_active": True}]
    _upsert(agent_config, _build_section(rules), _SECTION_RE, _START)

    # All present
    content = agent_config.read_text()
    assert _MEM_START in content
    assert _SKILLS_START in content
    assert _START in content

    # Remove all
    _remove(agent_config, _SECTION_RE, _START)
    _remove(agent_config, _MEM_RE, _MEM_START)
    _remove(agent_config, _SKILLS_RE, _SKILLS_START)

    content = agent_config.read_text().strip()
    assert _MEM_START not in content
    assert _SKILLS_START not in content
    assert _START not in content
