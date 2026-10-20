"""Structured agent memory — facts the user wants every AI session to know.

Categories/Types:
  preference — coding/formatting/behavior preferences
  project    — tech stack, repo structure, conventions
  never      — hard stops, things never to do
  context    — general context / background
"""

from __future__ import annotations

import json
from datetime import UTC
from datetime import datetime
from pathlib import Path
from typing import Any

from .store import scrub_pii

VALID_MEMORY_TYPES = {"preference", "project", "never", "context", "user", "style", "domain", "avoid"}

MEMORY_LABELS = {
    "project": "Active Projects",
    "preference": "Preferences",
    "never": "Never Do This",
    "avoid": "Never Do This",
    "context": "General Context",
    "user": "About You",
    "style": "Style & Conventions",
    "domain": "Domain Knowledge",
}


def _memory_file() -> Path:
    from . import store

    d = getattr(store, "_effective_local_dir", lambda: getattr(store, "LOCAL_DIR", Path.home() / ".ai-rule-learning"))()
    return Path(d) / "memory.jsonl"


def load_memory(memory_type: str | None = None, category: str | None = None) -> list[dict[str, Any]]:
    mf = _memory_file()
    if not mf.exists():
        return []
    entries: list[dict[str, Any]] = []
    for line in mf.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if isinstance(obj, dict):
                entries.append(obj)
        except Exception:
            continue
    filter_type = memory_type or category
    if filter_type:
        entries = [e for e in entries if e.get("type") == filter_type or e.get("category") == filter_type]
    return entries


def add_memory(
    memory_type: str,
    content: str,
    project: str = "global",
) -> dict[str, Any]:
    content = scrub_pii(content.strip())
    if not content:
        raise ValueError("content cannot be empty")
    mtype = memory_type.strip().lower()
    if mtype not in VALID_MEMORY_TYPES:
        mtype = "context"

    mf = _memory_file()
    entries = load_memory()
    entry: dict[str, Any] = {
        "type": mtype,
        "category": mtype,
        "content": content,
        "fact": content,
        "project": project,
        "added_at": datetime.now(UTC).isoformat(),
        "created_at": datetime.now(UTC).isoformat(),
    }
    entries.append(entry)
    mf.parent.mkdir(parents=True, exist_ok=True)
    with mf.open("w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    return entry


def forget(memory_type: str | None = None, content_substr: str | None = None) -> int:
    mf = _memory_file()
    if not mf.exists():
        return 0
    entries = load_memory()
    kept = []
    removed = 0
    for e in entries:
        matches = False
        if memory_type and (e.get("type") == memory_type or e.get("category") == memory_type):
            matches = True
        if content_substr and (
            content_substr.lower() in (e.get("content") or "").lower()
            or content_substr.lower() in (e.get("fact") or "").lower()
        ):
            matches = True
        if matches:
            removed += 1
        else:
            kept.append(e)
    if removed:
        with mf.open("w", encoding="utf-8") as f:
            for e in kept:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
    return removed


def clear_memory() -> int:
    mf = _memory_file()
    if not mf.exists():
        return 0
    entries = load_memory()
    count = len(entries)
    mf.unlink(missing_ok=True)
    return count


_MEM_START = "<!-- AI-Rule-Learning:memory:start -->"
_MEM_END = "<!-- AI-Rule-Learning:memory:end -->"


def build_memory_block(entries: list[dict[str, Any]], project: str | None = None) -> str:
    if not entries:
        return ""
    lines = [_MEM_START, "## Context & Memory *(managed by ai-rule-learning)*", ""]
    by_type: dict[str, list[str]] = {}
    for e in entries:
        t = e.get("type") or e.get("category", "context")
        c = e.get("content") or e.get("fact", "")
        if c:
            by_type.setdefault(t, []).append(c)

    order = ["project", "preference", "context", "never", "avoid", "user", "style", "domain"]
    for t in order:
        facts = by_type.get(t, [])
        if not facts:
            continue
        label = MEMORY_LABELS.get(t, t.capitalize())
        lines.append(f"### {label}")
        for f in facts:
            lines.append(f"- {f}")
        lines.append("")

    for t, facts in by_type.items():
        if t not in order and facts:
            lines.append(f"### {t.capitalize()}")
            for f in facts:
                lines.append(f"- {f}")
            lines.append("")

    lines.append(_MEM_END)
    return "\n".join(lines).strip()


format_memory_block = build_memory_block


def format_memory_for_display(entries: list[dict[str, Any]]) -> str:
    if not entries:
        return "No memory stored yet. Use `arl remember <type> '<content>'` or the `remember` MCP tool."
    lines = [f"# Stored Memory ({len(entries)} items)", ""]
    by_type: dict[str, list[dict[str, Any]]] = {}
    for e in entries:
        t = e.get("type") or e.get("category", "context")
        by_type.setdefault(t, []).append(e)

    order = ["preference", "project", "never", "avoid", "context", "user", "style", "domain"]
    seen = set()
    for t in order:
        if t in by_type:
            seen.add(t)
            label = "Preferences" if t == "preference" else MEMORY_LABELS.get(t, t.capitalize())
            lines.append(f"## {label}")
            for e in by_type[t]:
                c = e.get("content") or e.get("fact", "")
                lines.append(f"- {c}")
            lines.append("")

    for t, items in by_type.items():
        if t not in seen:
            lines.append(f"## {t.capitalize()}")
            for e in items:
                c = e.get("content") or e.get("fact", "")
                lines.append(f"- {c}")
            lines.append("")

    return "\n".join(lines).strip()
