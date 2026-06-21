"""Persistent user memory — facts, preferences, and context that compound over time.

Stored in ~/.ai-rule-learning/memory.jsonl and injected into every AI agent
config so the agent knows who the user is before they type a single word.

Memory types:
  preference   - coding/style/format preferences ("always use type hints")
  project      - active project context ("working on AI Rule Learning MCP server")
  never        - hard constraints ("never commit directly to main")
  user_info    - facts about the user ("solo developer", "UK timezone")
  context      - stack/team/environment ("Python 3.10, HuggingFace, MCP")
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

_MEM_START = "<!-- AI-Rule-Learning:memory:start -->"
_MEM_END = "<!-- AI-Rule-Learning:memory:end -->"

_TYPE_LABELS = {
    "preference": "Preferences",
    "project": "Active Projects",
    "never": "Never Do",
    "user_info": "About You",
    "context": "Stack & Context",
}

_VALID_TYPES = set(_TYPE_LABELS)


def _memory_file() -> Path:
    from .store import LOCAL_DIR

    LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    return LOCAL_DIR / "memory.jsonl"


def add_memory(memory_type: str, content: str) -> dict:
    """Append a memory entry. Returns the saved entry."""
    if memory_type not in _VALID_TYPES:
        memory_type = "context"

    content = content.strip()
    if not content:
        raise ValueError("content cannot be empty")

    entry = {
        "type": memory_type,
        "content": content,
        "added_at": datetime.utcnow().isoformat(),
    }

    path = _memory_file()
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    return entry


def load_memory() -> list[dict]:
    """Return all memory entries, oldest first."""
    path = _memory_file()
    if not path.exists():
        return []
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except Exception:
            continue
    return entries


def clear_memory() -> int:
    """Delete all memory entries. Returns count removed."""
    path = _memory_file()
    if not path.exists():
        return 0
    entries = load_memory()
    path.write_text("", encoding="utf-8")
    return len(entries)


def forget(memory_type: str | None = None, content_substr: str = "") -> int:
    """Remove entries matching type and/or content substring. Returns count removed."""
    entries = load_memory()
    kept = []
    removed = 0
    for e in entries:
        match_type = memory_type is None or e.get("type") == memory_type
        match_content = not content_substr or content_substr.lower() in e.get("content", "").lower()
        if match_type and match_content:
            removed += 1
        else:
            kept.append(e)
    if removed:
        path = _memory_file()
        path.write_text(
            "\n".join(json.dumps(e, ensure_ascii=False) for e in kept) + ("\n" if kept else ""),
            encoding="utf-8",
        )
    return removed


def build_memory_block(entries: list[dict]) -> str:
    """Render the memory block for injection into agent configs."""
    if not entries:
        return ""

    lines = [_MEM_START, "", "## About This User", ""]

    by_type: dict[str, list[str]] = {}
    for e in entries:
        t = e.get("type", "context")
        by_type.setdefault(t, []).append(e["content"])

    for type_key, label in _TYPE_LABELS.items():
        items = by_type.get(type_key, [])
        if not items:
            continue
        lines.append(f"**{label}:**")
        for item in items:
            lines.append(f"- {item}")
        lines.append("")

    lines.append(_MEM_END)
    return "\n".join(lines)


def format_memory_for_display(entries: list[dict]) -> str:
    """Human-readable summary for recall tool and CLI."""
    if not entries:
        return "No memory stored yet. Use the `remember` tool to add facts."

    by_type: dict[str, list[str]] = {}
    for e in entries:
        t = e.get("type", "context")
        by_type.setdefault(t, []).append(e["content"])

    lines = [f"## Memory ({len(entries)} entries)\n"]
    for type_key, label in _TYPE_LABELS.items():
        items = by_type.get(type_key, [])
        if not items:
            continue
        lines.append(f"**{label}:**")
        for item in items:
            lines.append(f"  - {item}")
        lines.append("")
    return "\n".join(lines)
