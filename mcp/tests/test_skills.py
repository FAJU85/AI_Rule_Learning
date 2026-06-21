"""Tests for skills.py — save/get/list/delete and index builder."""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import patch

import pytest

from ai_rule_learning_mcp.skills import (
    _slug,
    _skill_path,
    build_skills_index,
    delete_skill,
    format_skill_detail,
    format_skills_for_display,
    get_skill,
    list_skills,
    save_skill,
)

_SKILLS_START = "<!-- AI-Rule-Learning:skills:start -->"
_SKILLS_END = "<!-- AI-Rule-Learning:skills:end -->"


@pytest.fixture(autouse=True)
def isolated_skills_dir(tmp_path, monkeypatch):
    """Redirect the skills store to a temp directory for every test."""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()

    def fake_skills_dir():
        return skills_dir

    monkeypatch.setattr("ai_rule_learning_mcp.skills._skills_dir", fake_skills_dir)
    return skills_dir


# ── _slug ──────────────────────────────────────────────────────────────────


def test_slug_basic():
    assert _slug("Create Python Module") == "create-python-module"


def test_slug_special_chars():
    assert _slug("Deploy to HF!") == "deploy-to-hf"


def test_slug_truncates():
    long_name = "a" * 100
    assert len(_slug(long_name)) <= 60


def test_slug_underscores_become_dashes():
    assert _slug("my_skill_name") == "my-skill-name"


# ── save_skill ─────────────────────────────────────────────────────────────


def test_save_skill_returns_dict():
    skill = save_skill("Test Skill", "A test skill", "## Steps\n1. Do it")
    assert skill["name"] == "Test Skill"
    assert skill["slug"] == "test-skill"
    assert skill["description"] == "A test skill"
    assert skill["steps"] == "## Steps\n1. Do it"
    assert skill["used_count"] == 0
    assert "created_at" in skill


def test_save_skill_writes_file(isolated_skills_dir):
    save_skill("Deploy App", "Deploy to production", "1. Build\n2. Push")
    path = isolated_skills_dir / "deploy-app.md"
    assert path.exists()
    content = path.read_text()
    assert "Deploy App" in content
    assert "Deploy to production" in content
    assert "1. Build" in content


def test_save_skill_with_triggers():
    skill = save_skill(
        "Create API",
        "Create a REST API",
        "1. Define routes",
        triggers=["new api", "create api", "rest endpoint"],
    )
    assert skill["triggers"] == ["new api", "create api", "rest endpoint"]


def test_save_skill_empty_name_raises():
    with pytest.raises(ValueError, match="skill name cannot be empty"):
        save_skill("", "desc", "steps")


def test_save_skill_empty_steps_raises():
    with pytest.raises(ValueError, match="steps cannot be empty"):
        save_skill("My Skill", "desc", "")


def test_save_skill_preserves_used_count_on_update(isolated_skills_dir):
    save_skill("Update Me", "desc", "steps v1")
    # Manually set used_count to 5
    path = isolated_skills_dir / "update-me.md"
    content = path.read_text()
    content = content.replace("<!-- skill:used_count --> 0", "<!-- skill:used_count --> 5")
    path.write_text(content)

    # Re-save — should preserve count
    skill = save_skill("Update Me", "desc updated", "steps v2")
    assert skill["used_count"] == 5


# ── get_skill ──────────────────────────────────────────────────────────────


def test_get_skill_returns_skill():
    save_skill("Get Me", "desc", "## Steps\n1. First")
    skill = get_skill("Get Me")
    assert skill is not None
    assert skill["name"] == "Get Me"
    assert "## Steps" in skill["steps"]


def test_get_skill_increments_used_count(isolated_skills_dir):
    save_skill("Count Me", "desc", "steps")
    get_skill("Count Me")
    get_skill("Count Me")
    path = isolated_skills_dir / "count-me.md"
    content = path.read_text()
    assert "<!-- skill:used_count --> 2" in content


def test_get_skill_not_found_returns_none():
    result = get_skill("Nonexistent Skill")
    assert result is None


def test_get_skill_fuzzy_search():
    save_skill("Deploy to AWS", "AWS deployment", "1. Configure\n2. Deploy")
    skill = get_skill("aws")
    assert skill is not None
    assert "Deploy to AWS" in skill["name"]


def test_get_skill_by_slug():
    save_skill("Build Docker Image", "Build and tag", "1. docker build")
    skill = get_skill("build-docker-image")
    assert skill is not None
    assert skill["name"] == "Build Docker Image"


# ── list_skills ────────────────────────────────────────────────────────────


def test_list_skills_empty():
    result = list_skills()
    assert result == []


def test_list_skills_returns_metadata_only():
    save_skill("Alpha", "First skill", "## Steps\n1. A\n2. B\n3. C")
    save_skill("Beta", "Second skill", "## Steps\n1. X")
    skills = list_skills()
    assert len(skills) == 2
    for s in skills:
        assert "steps" not in s
        assert "name" in s
        assert "description" in s


def test_list_skills_sorted_by_name():
    save_skill("Zebra Skill", "Z", "steps")
    save_skill("Alpha Skill", "A", "steps")
    save_skill("Mango Skill", "M", "steps")
    skills = list_skills()
    names = [s["name"] for s in skills]
    assert names == sorted(names)


# ── delete_skill ───────────────────────────────────────────────────────────


def test_delete_skill_removes_file(isolated_skills_dir):
    save_skill("Delete Me", "desc", "steps")
    assert (isolated_skills_dir / "delete-me.md").exists()
    result = delete_skill("Delete Me")
    assert result is True
    assert not (isolated_skills_dir / "delete-me.md").exists()


def test_delete_skill_not_found_returns_false():
    result = delete_skill("Does Not Exist")
    assert result is False


def test_delete_skill_then_list_is_empty():
    save_skill("Temp Skill", "desc", "steps")
    delete_skill("Temp Skill")
    assert list_skills() == []


# ── build_skills_index ─────────────────────────────────────────────────────


def test_build_skills_index_empty_returns_empty_string():
    result = build_skills_index([])
    assert result == ""


def test_build_skills_index_contains_markers():
    skills = [{"name": "My Skill", "description": "does things", "triggers": []}]
    result = build_skills_index(skills)
    assert _SKILLS_START in result
    assert _SKILLS_END in result


def test_build_skills_index_lists_skills():
    skills = [
        {"name": "Alpha", "description": "first", "triggers": ["a", "alpha"]},
        {"name": "Beta", "description": "second", "triggers": []},
    ]
    result = build_skills_index(skills)
    assert "**Alpha**" in result
    assert "first" in result
    assert "a, alpha" in result
    assert "**Beta**" in result
    assert "second" in result


def test_build_skills_index_limits_triggers_to_three():
    skills = [
        {
            "name": "Skill",
            "description": "desc",
            "triggers": ["a", "b", "c", "d", "e"],
        }
    ]
    result = build_skills_index(skills)
    assert "a, b, c" in result
    # Triggers d and e are beyond the 3-item limit and should not appear as triggers
    assert ", d," not in result
    assert ", e)" not in result


# ── format helpers ─────────────────────────────────────────────────────────


def test_format_skills_for_display_empty():
    result = format_skills_for_display([])
    assert "No skills saved yet" in result


def test_format_skills_for_display_with_skills():
    skills = [
        {
            "name": "Deploy",
            "description": "Deploy to prod",
            "triggers": ["deploy", "push"],
            "used_count": 3,
        }
    ]
    result = format_skills_for_display(skills)
    assert "Deploy" in result
    assert "Deploy to prod" in result
    assert "3 time(s)" in result


def test_format_skill_detail_includes_steps():
    skill = {
        "name": "My Skill",
        "description": "does things",
        "triggers": ["foo"],
        "steps": "## Steps\n1. First\n2. Second",
    }
    result = format_skill_detail(skill)
    assert "My Skill" in result
    assert "## Steps" in result
    assert "First" in result
    assert "foo" in result
