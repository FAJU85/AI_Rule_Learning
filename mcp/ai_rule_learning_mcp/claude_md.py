"""Write/update the AI Rule Learning guardrail section in ~/.claude/CLAUDE.md.

Claude Code automatically reads CLAUDE.md at every session start — so writing
rules here is the only way to make them truly automatic with zero tool calls.
"""

from __future__ import annotations

import re
from pathlib import Path

_START = "<!-- AI-Rule-Learning:start -->"
_END = "<!-- AI-Rule-Learning:end -->"
_SECTION_RE = re.compile(
    rf"{re.escape(_START)}.*?{re.escape(_END)}", re.DOTALL
)

_PRIORITY_LABEL = {5: "CRITICAL", 4: "HIGH", 3: "MEDIUM", 2: "LOW", 1: "LOW"}


def claude_md_path() -> Path:
    return Path.home() / ".claude" / "CLAUDE.md"


def write_rules(rules: list[dict]) -> Path:
    """Insert or replace the guardrail block in ~/.claude/CLAUDE.md."""
    path = claude_md_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    section = _build_section(rules)

    if path.exists():
        text = path.read_text(encoding="utf-8")
        if _START in text:
            text = _SECTION_RE.sub(section, text)
        else:
            text = text.rstrip() + "\n\n" + section + "\n"
    else:
        text = section + "\n"

    path.write_text(text, encoding="utf-8")
    return path


def remove_rules() -> bool:
    """Remove the guardrail block. Returns True if anything was removed."""
    path = claude_md_path()
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    if _START not in text:
        return False
    cleaned = _SECTION_RE.sub("", text).strip() + "\n"
    path.write_text(cleaned, encoding="utf-8")
    return True


def read_injected_rules() -> list[str]:
    """Return the lines currently injected (for status display)."""
    path = claude_md_path()
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    m = _SECTION_RE.search(text)
    if not m:
        return []
    return [ln for ln in m.group().splitlines() if ln.startswith("-")]


def _build_section(rules: list[dict]) -> str:
    lines = [_START, ""]
    if not rules:
        lines += ["<!-- no active rules -->", "", _END]
        return "\n".join(lines)

    lines += [
        "## Active AI Guardrails",
        "",
        "These rules were learned from your past sessions."
        " Apply them to every response:",
        "",
    ]
    for rule in rules:
        priority = rule.get("priority", 3)
        if isinstance(priority, str):
            label = priority.upper()
        else:
            label = _PRIORITY_LABEL.get(int(priority), "MEDIUM")
        name = rule.get("name", rule.get("rule_id", "rule"))
        instruction = (
            rule.get("action", {}).get("instruction")
            or rule.get("instruction", "")
        ).strip()
        line = f"- **[{label}] {name}**"
        if instruction:
            line += f": {instruction}"
        lines.append(line)

    lines += ["", _END]
    return "\n".join(lines)
