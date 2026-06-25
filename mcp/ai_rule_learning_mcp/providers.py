"""Provider adapters — parse sessions from any AI tool into a common format.

Supported providers:
  claude_code   ~/.claude/projects/**/*.jsonl  (default)
  openai        ChatGPT/OpenAI export conversations.json
  cursor        ~/.cursor/logs/ or exported chats
  generic       Any JSONL with {role, content} or {user, assistant} messages
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from .store import _SKIP_TAGS
from .store import scrub_pii

# ---------------------------------------------------------------------------
# Common turn format
# ---------------------------------------------------------------------------


def _make_turn(n: int, user: str, agent: str, ts: str = "") -> dict:
    return {
        "turn_number": n,
        "user_input": scrub_pii(user[:4000]),
        "agent_response": scrub_pii(agent[:4000]),
        "timestamp": ts,
        "gaps_detected": [],
        "rules_applied": [],
        "sensor_reading": None,
    }


def _make_conv(session_id: str, turns: list[dict], source: str, slug: str = "", project: str = "") -> dict:
    return {
        "conversation_id": f"{source}_{session_id}",
        "session_id": session_id,
        "slug": slug,
        "project_context": project,
        "git_branch": "",
        "source": source,
        "turns": turns,
        "escalation_occurred": False,
        "human_intervention": False,
        "started_at": turns[0]["timestamp"] if turns else datetime.utcnow().isoformat(),
        "ended_at": datetime.utcnow().isoformat(),
        "exported_at": datetime.utcnow().isoformat(),
    }


# ---------------------------------------------------------------------------
# Provider: Claude Code
# ---------------------------------------------------------------------------


def _extract_text(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        return " ".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text").strip()
    return ""


def parse_claude_code_session(path: Path) -> dict | None:
    """Parse a Claude Code ~/.claude/projects/**/*.jsonl session file."""
    messages: list[dict] = []
    meta: dict = {}

    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                msg = obj.get("message", {})
                role = msg.get("role")
                if not meta:
                    meta = {
                        "session_id": obj.get("sessionId", str(uuid.uuid4())),
                        "slug": obj.get("slug", ""),
                        "cwd": obj.get("cwd", ""),
                        "started_at": obj.get("timestamp", datetime.utcnow().isoformat()),
                    }
                if role not in ("user", "assistant"):
                    continue
                text = _extract_text(msg.get("content", ""))
                if not text or (role == "user" and any(t in text for t in _SKIP_TAGS)):
                    continue
                messages.append({"role": role, "text": text, "ts": obj.get("timestamp", "")})
    except Exception:
        return None

    if not meta or len(messages) < 4:
        return None

    turns = _pair_messages(messages)
    if len(turns) < 2:
        return None

    cwd = meta.get("cwd", "")
    try:
        project = str(Path(cwd).relative_to(Path.home()))
    except ValueError:
        project = re.sub(r"(?:/home/[^/\s]+|/Users/[^/\s]+)", "[HOME]", cwd)

    return _make_conv(meta["session_id"], turns, "claude_code", meta["slug"], project)


# ---------------------------------------------------------------------------
# Provider: OpenAI / ChatGPT export
# ---------------------------------------------------------------------------


def parse_openai_export(path: Path) -> list[dict]:
    """Parse a ChatGPT/OpenAI conversations.json export file.

    The export is a list of conversation objects, each with:
      id, title, mapping (node tree) or messages list.
    """
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []

    if not isinstance(data, list):
        data = [data]

    convs = []
    for item in data:
        conv_id = item.get("id", str(uuid.uuid4()))
        title = item.get("title", "")

        # Flatten the mapping tree into ordered messages
        messages: list[dict] = []
        mapping = item.get("mapping", {})
        if mapping:
            # Walk the linked list (each node has parent/children) in order
            # Find root(s) and walk in order
            visited: set = set()

            def _walk(node_id: str):
                if node_id in visited:
                    return
                visited.add(node_id)
                node = mapping.get(node_id, {})
                msg = node.get("message")
                if msg:
                    role = msg.get("author", {}).get("role", "")
                    parts = msg.get("content", {}).get("parts", [])
                    text = " ".join(str(p) for p in parts if isinstance(p, str)).strip()
                    if role in ("user", "assistant") and text:
                        messages.append(
                            {
                                "role": role,
                                "text": text,
                                "ts": str(msg.get("create_time", "")),
                            }
                        )
                for child_id in node.get("children", []):
                    _walk(child_id)

            for node_id in mapping:
                node = mapping[node_id]
                if not node.get("parent"):
                    _walk(node_id)
        else:
            # Flat messages list
            for msg in item.get("messages", []):
                role = msg.get("role", "")
                content = msg.get("content", "")
                if isinstance(content, list):
                    content = " ".join(c.get("text", "") for c in content if isinstance(c, dict))
                if role in ("user", "assistant") and content:
                    messages.append({"role": role, "text": str(content), "ts": ""})

        turns = _pair_messages(messages)
        if len(turns) >= 2:
            convs.append(_make_conv(conv_id, turns, "openai", title))

    return convs


# ---------------------------------------------------------------------------
# Provider: Generic JSONL (Cursor, Windsurf, any tool)
# ---------------------------------------------------------------------------


def parse_generic_jsonl(path: Path) -> dict | None:
    """Parse any JSONL file with {role, content} or {user, assistant} messages."""
    messages: list[dict] = []
    try:
        with open(path, encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]

        # Try line-per-message format
        for line in lines:
            try:
                obj = json.loads(line)
            except Exception:
                continue
            role = obj.get("role", "")
            if not role:
                # {user: ..., assistant: ...} single-object format
                if "user" in obj and "assistant" in obj:
                    messages.append({"role": "user", "text": str(obj["user"]), "ts": ""})
                    messages.append({"role": "assistant", "text": str(obj["assistant"]), "ts": ""})
                    continue
            content = obj.get("content", obj.get("text", obj.get("message", "")))
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "text": str(content), "ts": ""})
    except Exception:
        return None

    turns = _pair_messages(messages)
    if len(turns) < 2:
        return None

    return _make_conv(str(uuid.uuid4()), turns, "generic", path.stem)


# ---------------------------------------------------------------------------
# Shared: pair user→assistant messages into turns
# ---------------------------------------------------------------------------


def _pair_messages(messages: list[dict]) -> list[dict]:
    turns: list[dict] = []
    i = 0
    while i < len(messages):
        if messages[i]["role"] == "user":
            j = i + 1
            while j < len(messages) and messages[j]["role"] != "assistant":
                j += 1
            if j < len(messages):
                turns.append(
                    _make_turn(
                        len(turns) + 1,
                        messages[i]["text"],
                        messages[j]["text"],
                        messages[i].get("ts", ""),
                    )
                )
                i = j + 1
                continue
        i += 1
    return turns


# ---------------------------------------------------------------------------
# Auto-detect and parse any file
# ---------------------------------------------------------------------------


def parse_any(path: Path) -> list[dict]:
    """Parse any session file — returns a list of Conversation dicts."""
    name = path.name.lower()

    # OpenAI/ChatGPT bulk export
    if name == "conversations.json":
        return parse_openai_export(path)

    if path.suffix == ".jsonl":
        # Try Claude Code format first
        conv = parse_claude_code_session(path)
        if conv:
            return [conv]
        # Fall back to generic
        conv = parse_generic_jsonl(path)
        return [conv] if conv else []

    if path.suffix == ".json":
        convs = parse_openai_export(path)
        return convs

    return []
