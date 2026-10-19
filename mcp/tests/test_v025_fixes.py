import asyncio
import json
from pathlib import Path
import pytest

from ai_rule_learning_mcp import server, store


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture
def test_env(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    arl_dir = tmp_path / ".ai-rule-learning"
    arl_dir.mkdir(parents=True, exist_ok=True)
    rules_file = arl_dir / "rules.jsonl"
    monkeypatch.setattr(store, "LOCAL_DIR", arl_dir)
    monkeypatch.setattr(store, "RULES_FILE", rules_file)
    return arl_dir


def test_v1_schema_exposes_rule_id():
    """V1: schema exposes rule_id in record_feedback properties."""
    tools = _run(server.list_tools())
    rf_tool = next((t for t in tools if t.name == "record_feedback"), None)
    assert rf_tool is not None
    props = rf_tool.inputSchema.get("properties", {})
    assert "rule_id" in props, f"rule_id missing from record_feedback schema: {props.keys()}"


def test_v2_explicit_rule_id_updates_in_place(test_env):
    """V2: explicit rule_id updates existing rule in place."""
    # Create initial rule
    res1 = _run(
        server._record_feedback(
            {
                "feedback_type": "correction",
                "description": "Initial correction description",
                "rule_hint": "Initial instruction text ABC",
            }
        )
    )
    assert "Created" in res1[0].text
    active1 = store.load_active_rules()
    assert len(active1) == 1
    target_id = active1[0]["rule_id"]

    # Update via explicit rule_id
    res2 = _run(
        server._record_feedback(
            {
                "feedback_type": "correction",
                "description": "Updated correction description",
                "rule_hint": "Updated instruction text XYZ",
                "rule_id": target_id,
            }
        )
    )
    assert "Updated" in res2[0].text
    active2 = store.load_active_rules()
    assert len(active2) == 1
    assert active2[0]["rule_id"] == target_id
    assert active2[0]["instruction"] == "Updated instruction text XYZ"


def test_v4_v5_v12_v13_repeating_same_hint_is_idempotent(test_env, tmp_path):
    """V4, V5, V12, V13: repeating identical hint causes no growth or duplicate bullets."""
    claude_md = tmp_path / "CLAUDE.md"
    claude_md.write_text("# Project Guidelines\n\nExisting text.\n")

    # Seed 3 distinct rules
    hints = [
        ("correction", "first error", "Verify flags before running commands"),
        ("preference", "style pref", "Prefer pytest fixtures over unittest"),
        ("incomplete_response", "missed part 2", "Answer all parts of multi-part prompts"),
    ]
    for fb_type, desc, hint in hints:
        _run(server._record_feedback({"feedback_type": fb_type, "description": desc, "rule_hint": hint}))

    active_seed = store.load_active_rules()
    assert len(active_seed) == 3

    # Repeat exact same hints 3 times
    for _ in range(3):
        for fb_type, desc, hint in hints:
            _run(server._record_feedback({"feedback_type": fb_type, "description": desc, "rule_hint": hint}))

    active_repeat = store.load_active_rules()
    assert len(active_repeat) == 3, f"Expected count to stay 3, got {len(active_repeat)}"

    # Check rule_id uniqueness (V12)
    ids = [r["rule_id"] for r in active_repeat]
    assert len(ids) == len(set(ids)), f"Duplicate rule_ids found: {ids}"

    # Verify no duplicated bullets injected into CLAUDE.md (V13)
    _run(server._sync_sessions(paths=[], dry_run=False))
    if claude_md.exists():
        content = claude_md.read_text()
        bullets = [line.strip() for line in content.splitlines() if line.strip().startswith("- ")]
        assert len(bullets) == len(set(bullets)), f"Duplicate bullets in CLAUDE.md: {bullets}"


def test_v9_whitespace_only_description_rejected(test_env):
    """V9: whitespace-only description is rejected."""
    res = _run(
        server._record_feedback(
            {
                "feedback_type": "correction",
                "description": "   \n\t  ",
                "rule_hint": "HINT FROM BLANK",
            }
        )
    )
    assert "Rejected" in res[0].text or "❌" in res[0].text
    active = store.load_active_rules()
    assert len(active) == 0, f"Expected 0 rules saved from blank description, got {len(active)}"


def test_v10_unknown_tool_returns_is_error():
    """V10: unknown tool sets isError=True."""
    result = _run(server.call_tool("unknown_bogus_tool", {}))
    assert isinstance(result, tuple)
    items, is_error = result
    assert is_error is True
    assert "Unknown tool" in items[0].text


def test_v11_no_args_install_scheduler_does_not_write_cron(test_env, tmp_path):
    """V11: no-args install does not write scheduler.cron."""
    cron_file = test_env / "scheduler.cron"
    if cron_file.exists():
        cron_file.unlink()

    res = _run(server._install_scheduler(action="", dry_run=False))
    assert not cron_file.exists(), "scheduler.cron should NOT be created when no action is passed"
