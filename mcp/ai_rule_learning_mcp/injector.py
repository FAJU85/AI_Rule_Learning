"""Universal rule + memory + skills injector — writes to all detected AI agent configs.

Supported agents (auto-detected by presence of their config dirs):
  - Claude Code    → ~/.claude/CLAUDE.md
  - Cursor         → ~/.cursor/rules/ai-guardrails.md
  - Windsurf       → ~/.windsurf/rules/ai-guardrails.md
  - GitHub Copilot → ~/.config/github-copilot/instructions.md

Each config file receives up to three sections (order: memory, skills, rules):
  1. Memory block  — who the user is, their preferences, active projects
  2. Skills index  — names + descriptions of saved reusable procedures
  3. Rules block   — guardrail rules learned from past sessions

All sections use HTML comment markers and are updated idempotently.
Agents without a persistent config file get rules inline via get_guardrail_rules.
"""

from __future__ import annotations

import re
from pathlib import Path

# ── Rules section markers ──────────────────────────────────────────────────
_START = "<!-- AI-Rule-Learning:start -->"
_END = "<!-- AI-Rule-Learning:end -->"
_SECTION_RE = re.compile(rf"{re.escape(_START)}.*?{re.escape(_END)}", re.DOTALL)

# ── Memory section markers ─────────────────────────────────────────────────
_MEM_START = "<!-- AI-Rule-Learning:memory:start -->"
_MEM_END = "<!-- AI-Rule-Learning:memory:end -->"
_MEM_RE = re.compile(rf"{re.escape(_MEM_START)}.*?{re.escape(_MEM_END)}", re.DOTALL)

# ── Skills section markers ─────────────────────────────────────────────────
_SKILLS_START = "<!-- AI-Rule-Learning:skills:start -->"
_SKILLS_END = "<!-- AI-Rule-Learning:skills:end -->"
_SKILLS_RE = re.compile(rf"{re.escape(_SKILLS_START)}.*?{re.escape(_SKILLS_END)}", re.DOTALL)

_PRIORITY_LABEL = {5: "CRITICAL", 4: "HIGH", 3: "MEDIUM", 2: "LOW", 1: "LOW"}


# ── Section builders ───────────────────────────────────────────────────────

def _build_section(rules: list[dict]) -> str:
    lines = [_START, ""]
    if not rules:
        lines += ["<!-- no active rules -->", "", _END]
        return "\n".join(lines)
    lines += [
        "## Active AI Guardrails",
        "",
        "These rules were learned from past sessions. Apply them to every response:",
        "",
    ]
    for rule in rules:
        priority = rule.get("priority", 3)
        label = (
            priority.upper()
            if isinstance(priority, str)
            else _PRIORITY_LABEL.get(int(priority), "MEDIUM")
        )
        name = rule.get("name", rule.get("rule_id", "rule"))
        instruction = (
            rule.get("action", {}).get("instruction") or rule.get("instruction", "")
        ).strip()
        line = f"- **[{label}] {name}**"
        evidence_count = rule.get("evidence_count", rule.get("instance_count"))
        confidence = rule.get("confidence")
        indicators = []
        if evidence_count is not None:
            indicators.append(f"evidence={evidence_count}")
        if confidence is not None:
            indicators.append(f"confidence={float(confidence):.0%}")
        if indicators:
            line += " (" + ", ".join(indicators) + ")"
        if instruction:
            line += f": {instruction}"
        lines.append(line)
    lines += ["", _END]
    return "\n".join(lines)


# ── Generic upsert / remove helpers ───────────────────────────────────────

def _upsert(path: Path, content: str, pattern: re.Pattern, marker_start: str) -> None:
    """Insert or replace a fenced block identified by pattern in a markdown file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        text = path.read_text(encoding="utf-8")
        if marker_start in text:
            text = pattern.sub(content, text)
        else:
            text = text.rstrip() + "\n\n" + content + "\n"
    else:
        text = content + "\n"
    path.write_text(text, encoding="utf-8")


def _remove(path: Path, pattern: re.Pattern, marker_start: str) -> bool:
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    if marker_start not in text:
        return False
    cleaned = pattern.sub("", text).strip() + "\n"
    path.write_text(cleaned, encoding="utf-8")
    return True


def _read_bullets(path: Path, pattern: re.Pattern) -> list[str]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    m = pattern.search(text)
    if not m:
        return []
    return [ln for ln in m.group().splitlines() if ln.startswith("-")]


# ── Target registry ────────────────────────────────────────────────────────

class _Target:
    name: str

    def config_path(self) -> Path:
        raise NotImplementedError

    def is_detected(self) -> bool:
        return self.config_path().parent.exists()

    def write(
        self,
        rules: list[dict],
        memory_block: str = "",
        skills_block: str = "",
    ) -> Path:
        p = self.config_path()
        if memory_block:
            _upsert(p, memory_block, _MEM_RE, _MEM_START)
        if skills_block:
            _upsert(p, skills_block, _SKILLS_RE, _SKILLS_START)
        _upsert(p, _build_section(rules), _SECTION_RE, _START)
        return p

    def write_memory(self, memory_block: str) -> Path:
        p = self.config_path()
        _upsert(p, memory_block, _MEM_RE, _MEM_START)
        return p

    def write_skills(self, skills_block: str) -> Path:
        p = self.config_path()
        _upsert(p, skills_block, _SKILLS_RE, _SKILLS_START)
        return p

    def remove(self) -> bool:
        p = self.config_path()
        r1 = _remove(p, _SECTION_RE, _START)
        r2 = _remove(p, _MEM_RE, _MEM_START)
        r3 = _remove(p, _SKILLS_RE, _SKILLS_START)
        return r1 or r2 or r3

    def read_injected(self) -> list[str]:
        return _read_bullets(self.config_path(), _SECTION_RE)


class _ClaudeCodeTarget(_Target):
    name = "Claude Code"

    def config_path(self) -> Path:
        return Path.home() / ".claude" / "CLAUDE.md"

    def is_detected(self) -> bool:
        return (Path.home() / ".claude").exists()


class _CursorTarget(_Target):
    name = "Cursor"

    def config_path(self) -> Path:
        return Path.home() / ".cursor" / "rules" / "ai-guardrails.md"

    def is_detected(self) -> bool:
        return (Path.home() / ".cursor").exists()


class _WindsurfTarget(_Target):
    name = "Windsurf"

    def config_path(self) -> Path:
        return Path.home() / ".windsurf" / "rules" / "ai-guardrails.md"

    def is_detected(self) -> bool:
        return (Path.home() / ".windsurf").exists()


class _CopilotTarget(_Target):
    name = "GitHub Copilot"

    def config_path(self) -> Path:
        return Path.home() / ".config" / "github-copilot" / "instructions.md"

    def is_detected(self) -> bool:
        vscode_hints = [
            Path.home() / ".vscode",
            Path.home() / ".config" / "Code",
            Path.home() / "Library" / "Application Support" / "Code",
        ]
        copilot_dir = Path.home() / ".config" / "github-copilot"
        return copilot_dir.exists() or any(d.exists() for d in vscode_hints)


_ALL_TARGETS: list[_Target] = [
    _ClaudeCodeTarget(),
    _CursorTarget(),
    _WindsurfTarget(),
    _CopilotTarget(),
]


# ── Public API ─────────────────────────────────────────────────────────────

def detected_targets() -> list[_Target]:
    """Return targets for agents that appear to be installed on this machine."""
    return [t for t in _ALL_TARGETS if t.is_detected()]


def write_rules_all(
    rules: list[dict],
    memory_entries: list[dict] | None = None,
    skill_list: list[dict] | None = None,
) -> list[tuple[str, Path]]:
    """Write rules (and optionally memory + skills) to every detected agent config."""
    from .memory import build_memory_block
    from .skills import build_skills_index

    memory_block = build_memory_block(memory_entries) if memory_entries else ""
    skills_block = build_skills_index(skill_list) if skill_list else ""

    results: list[tuple[str, Path]] = []
    for target in detected_targets():
        try:
            path = target.write(rules, memory_block=memory_block, skills_block=skills_block)
            results.append((target.name, path))
        except Exception:
            pass
    return results


def write_memory_all(memory_entries: list[dict]) -> list[tuple[str, Path]]:
    """Write only the memory block to every detected agent config."""
    from .memory import build_memory_block

    block = build_memory_block(memory_entries)
    if not block:
        return []

    results: list[tuple[str, Path]] = []
    for target in detected_targets():
        try:
            path = target.write_memory(block)
            results.append((target.name, path))
        except Exception:
            pass
    return results


def write_skills_all(skill_list: list[dict]) -> list[tuple[str, Path]]:
    """Write only the skills index block to every detected agent config."""
    from .skills import build_skills_index

    block = build_skills_index(skill_list)
    if not block:
        return []

    results: list[tuple[str, Path]] = []
    for target in detected_targets():
        try:
            path = target.write_skills(block)
            results.append((target.name, path))
        except Exception:
            pass
    return results


def remove_rules_all() -> list[str]:
    """Remove both rules and memory sections from all targets."""
    removed: list[str] = []
    for target in _ALL_TARGETS:
        try:
            if target.remove():
                removed.append(target.name)
        except Exception:
            pass
    return removed


def read_injected_rules() -> list[str]:
    """Return injected rule lines from the first target that has them."""
    for target in _ALL_TARGETS:
        lines = target.read_injected()
        if lines:
            return lines
    return []


def format_rules_block(rules: list[dict]) -> str:
    """Plain-text block for inline injection (e.g. Codex system prompt)."""
    if not rules:
        return "No active guardrail rules yet."
    lines = ["## Your Active Guardrail Rules", ""]
    for i, rule in enumerate(rules, 1):
        priority = rule.get("priority", 3)
        label = (
            priority.upper()
            if isinstance(priority, str)
            else _PRIORITY_LABEL.get(int(priority), "MEDIUM")
        )
        name = rule.get("name", rule.get("rule_id", f"Rule {i}"))
        instruction = (
            rule.get("action", {}).get("instruction") or rule.get("instruction", "")
        ).strip()
        lines.append(f"**Rule {i}: {name}** [{label}]")
        if instruction:
            lines.append(f"→ {instruction}")
        evidence_count = rule.get("evidence_count", rule.get("instance_count"))
        confidence = rule.get("confidence")
        last_observed = rule.get("last_observed")
        indicators = []
        if evidence_count is not None:
            indicators.append(f"evidence={evidence_count}")
        if confidence is not None:
            indicators.append(f"confidence={float(confidence):.0%}")
        if last_observed:
            indicators.append(f"last_observed={last_observed}")
        if indicators:
            lines.append("↳ " + "; ".join(indicators))
        lines.append("")
    return "\n".join(lines)
