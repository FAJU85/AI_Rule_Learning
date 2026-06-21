"""Tests for providers.py — session format parsers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_rule_learning_mcp.providers import (
    _pair_messages,
    parse_any,
    parse_claude_code_session,
    parse_generic_jsonl,
    parse_openai_export,
)


# ── helpers ────────────────────────────────────────────────────────────────


def _write_jsonl(path: Path, lines: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(l) for l in lines), encoding="utf-8")


def _claude_line(role: str, text: str, session_id: str = "sess123") -> dict:
    return {
        "sessionId": session_id,
        "slug": "test-session",
        "cwd": "/home/user/project",
        "timestamp": "2026-06-21T00:00:00",
        "message": {"role": role, "content": text},
    }


# ── _pair_messages ────────────────────────────────────────────────────────


def test_pair_messages_basic():
    msgs = [
        {"role": "user", "text": "Hello", "ts": ""},
        {"role": "assistant", "text": "Hi", "ts": ""},
        {"role": "user", "text": "How are you?", "ts": ""},
        {"role": "assistant", "text": "Fine!", "ts": ""},
    ]
    turns = _pair_messages(msgs)
    assert len(turns) == 2
    assert turns[0]["user_input"] == "Hello"
    assert turns[0]["agent_response"] == "Hi"
    assert turns[1]["user_input"] == "How are you?"


def test_pair_messages_skips_leading_assistant():
    msgs = [
        {"role": "assistant", "text": "Welcome", "ts": ""},
        {"role": "user", "text": "Hi", "ts": ""},
        {"role": "assistant", "text": "Hello", "ts": ""},
    ]
    turns = _pair_messages(msgs)
    assert len(turns) == 1
    assert turns[0]["user_input"] == "Hi"


def test_pair_messages_empty():
    assert _pair_messages([]) == []


def test_pair_messages_no_assistant():
    msgs = [{"role": "user", "text": "Hello", "ts": ""}]
    assert _pair_messages(msgs) == []


# ── parse_claude_code_session ──────────────────────────────────────────────


def test_parse_claude_code_valid(tmp_path):
    p = tmp_path / "session.jsonl"
    lines = [
        _claude_line("user", "How do I write a test?"),
        _claude_line("assistant", "Use pytest and write test_ functions."),
        _claude_line("user", "What about fixtures?"),
        _claude_line("assistant", "Use @pytest.fixture decorator."),
        _claude_line("user", "Thanks"),
        _claude_line("assistant", "No problem!"),
    ]
    _write_jsonl(p, lines)
    result = parse_claude_code_session(p)
    assert result is not None
    assert result["source"] == "claude_code"
    assert result["session_id"] == "sess123"
    assert len(result["turns"]) >= 2


def test_parse_claude_code_too_short(tmp_path):
    p = tmp_path / "session.jsonl"
    lines = [
        _claude_line("user", "Hi"),
        _claude_line("assistant", "Hello"),
    ]
    _write_jsonl(p, lines)
    result = parse_claude_code_session(p)
    assert result is None


def test_parse_claude_code_skips_system_tags(tmp_path):
    p = tmp_path / "session.jsonl"
    lines = [
        _claude_line("user", "<system-reminder>ignore this</system-reminder>"),
        _claude_line("assistant", "ok"),
        _claude_line("user", "real question here"),
        _claude_line("assistant", "real answer"),
        _claude_line("user", "another"),
        _claude_line("assistant", "response"),
    ]
    _write_jsonl(p, lines)
    result = parse_claude_code_session(p)
    # system-reminder lines are filtered out — only real turns count
    if result:
        for turn in result["turns"]:
            assert "<system-reminder>" not in turn["user_input"]


def test_parse_claude_code_scrubs_pii(tmp_path):
    p = tmp_path / "session.jsonl"
    lines = [
        _claude_line("user", "My email is user@example.com"),
        _claude_line("assistant", "Got it"),
        _claude_line("user", "My token is hf_abc1234567890"),
        _claude_line("assistant", "Noted"),
        _claude_line("user", "Another question"),
        _claude_line("assistant", "Another answer"),
    ]
    _write_jsonl(p, lines)
    result = parse_claude_code_session(p)
    if result:
        all_text = " ".join(
            t["user_input"] + t["agent_response"] for t in result["turns"]
        )
        assert "user@example.com" not in all_text
        assert "hf_abc1234567890" not in all_text


def test_parse_claude_code_list_content(tmp_path):
    p = tmp_path / "session.jsonl"
    lines = [
        {
            "sessionId": "sess999",
            "message": {
                "role": "user",
                "content": [{"type": "text", "text": "Question from list content"}],
            },
        },
        {
            "sessionId": "sess999",
            "message": {"role": "assistant", "content": "Answer"},
        },
        {
            "sessionId": "sess999",
            "message": {"role": "user", "content": "Follow up"},
        },
        {
            "sessionId": "sess999",
            "message": {"role": "assistant", "content": "More"},
        },
        {
            "sessionId": "sess999",
            "message": {"role": "user", "content": "Third"},
        },
        {
            "sessionId": "sess999",
            "message": {"role": "assistant", "content": "Third answer"},
        },
    ]
    _write_jsonl(p, lines)
    result = parse_claude_code_session(p)
    assert result is not None
    assert "Question from list content" in result["turns"][0]["user_input"]


# ── parse_openai_export ────────────────────────────────────────────────────


def test_parse_openai_flat_messages(tmp_path):
    data = [
        {
            "id": "conv1",
            "title": "Test Chat",
            "messages": [
                {"role": "user", "content": "What is Python?"},
                {"role": "assistant", "content": "A programming language."},
                {"role": "user", "content": "How do I install it?"},
                {"role": "assistant", "content": "Use python.org or your package manager."},
            ],
        }
    ]
    p = tmp_path / "conversations.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    result = parse_openai_export(p)
    assert len(result) == 1
    assert result[0]["source"] == "openai"
    assert len(result[0]["turns"]) == 2


def test_parse_openai_empty_file(tmp_path):
    p = tmp_path / "conversations.json"
    p.write_text("[]", encoding="utf-8")
    result = parse_openai_export(p)
    assert result == []


def test_parse_openai_invalid_json(tmp_path):
    p = tmp_path / "conversations.json"
    p.write_text("not json", encoding="utf-8")
    result = parse_openai_export(p)
    assert result == []


def test_parse_openai_multiple_conversations(tmp_path):
    data = [
        {
            "id": f"conv{i}",
            "title": f"Chat {i}",
            "messages": [
                {"role": "user", "content": f"Question {i}"},
                {"role": "assistant", "content": f"Answer {i}"},
                {"role": "user", "content": f"Follow up {i}"},
                {"role": "assistant", "content": f"More {i}"},
            ],
        }
        for i in range(3)
    ]
    p = tmp_path / "conversations.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    result = parse_openai_export(p)
    assert len(result) == 3


# ── parse_generic_jsonl ────────────────────────────────────────────────────


def test_parse_generic_role_content(tmp_path):
    p = tmp_path / "chat.jsonl"
    lines = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there"},
        {"role": "user", "content": "How are you?"},
        {"role": "assistant", "content": "Great!"},
    ]
    _write_jsonl(p, lines)
    result = parse_generic_jsonl(p)
    assert result is not None
    assert len(result["turns"]) == 2


def test_parse_generic_user_assistant_format(tmp_path):
    p = tmp_path / "chat.jsonl"
    lines = [
        {"user": "What is 2+2?", "assistant": "4"},
        {"user": "And 3+3?", "assistant": "6"},
    ]
    _write_jsonl(p, lines)
    result = parse_generic_jsonl(p)
    assert result is not None
    assert len(result["turns"]) == 2
    assert result["turns"][0]["user_input"] == "What is 2+2?"


def test_parse_generic_too_few_turns(tmp_path):
    p = tmp_path / "chat.jsonl"
    lines = [
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello"},
    ]
    _write_jsonl(p, lines)
    result = parse_generic_jsonl(p)
    assert result is None


def test_parse_generic_bad_lines_skipped(tmp_path):
    p = tmp_path / "chat.jsonl"
    p.write_text(
        '{"role": "user", "content": "Q1"}\n'
        "not valid json\n"
        '{"role": "assistant", "content": "A1"}\n'
        '{"role": "user", "content": "Q2"}\n'
        '{"role": "assistant", "content": "A2"}\n',
        encoding="utf-8",
    )
    result = parse_generic_jsonl(p)
    assert result is not None
    assert len(result["turns"]) == 2


# ── parse_any ──────────────────────────────────────────────────────────────


def test_parse_any_conversations_json(tmp_path):
    data = [
        {
            "id": "c1",
            "messages": [
                {"role": "user", "content": "Hi"},
                {"role": "assistant", "content": "Hello"},
                {"role": "user", "content": "Bye"},
                {"role": "assistant", "content": "Goodbye"},
            ],
        }
    ]
    p = tmp_path / "conversations.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    result = parse_any(p)
    assert len(result) == 1
    assert result[0]["source"] == "openai"


def test_parse_any_jsonl_falls_back_to_generic(tmp_path):
    p = tmp_path / "export.jsonl"
    lines = [
        {"role": "user", "content": "Q1"},
        {"role": "assistant", "content": "A1"},
        {"role": "user", "content": "Q2"},
        {"role": "assistant", "content": "A2"},
    ]
    _write_jsonl(p, lines)
    result = parse_any(p)
    assert len(result) == 1
    assert result[0]["source"] == "generic"


def test_parse_any_unknown_extension(tmp_path):
    p = tmp_path / "file.txt"
    p.write_text("hello world", encoding="utf-8")
    result = parse_any(p)
    assert result == []
