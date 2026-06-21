"""Universal rule injector — writes guardrail rules to all detected AI agent configs.

Supported agents (auto-detected by presence of their config dirs):
  - Claude Code   → ~/.claude/CLAUDE.md
  - Cursor        → ~/.cursor/rules/ai-guardrails.md
  - Windsurf      → ~/.windsurf/rules/ai-guardrails.md
  - GitHub Copilot → ~/.config/github-copilot/instructions.md

Rules are always available inline via get_guardrail_rules for agents that
support MCP (Codex, custom agents, etc.) but don't have a persistent config file.
"""

from __future__ import annotations

import re
from pathlib import Path

_START = "<!-- AI-Rule-Learning:start -->"
_END = "<!-- AI-Rule-Learning:end -->"
_SECTION_RE = re.compile(rf"{re.escape(_START)}.*?{re.escape(_END)}", re.DOTALL)
_PRIORITY_LABEL = {5: "CRITICAL", 4: "HIGH", 3: "MEDIUM", 2: "LOW", 1: "LOW"}


# ── Shared section builder ─────────────────────────────────────────────────

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
        if instruction:
            line += f": {instruction}"
        lines.append(line)
    lines += ["", _END]
    return "\n".join(lines)


def _upsert_section(path: Path, section: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        text = path.read_text(encoding="utf-8")
        if _START in text:
            text = _SECTION_RE.sub(section, text)
        else:
            text = text.rstrip() + "\n\n" + section + "\n"
    else:
        text = section + "\n"
    path.write_text(text, encoding="utf-8")


def _remove_section(path: Path) -> bool:
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    if _START not in text:
        return False
    cleaned = _SECTION_RE.sub("", text).strip() + "\n"
    path.write_text(cleaned, encoding="utf-8")
    return True


def _read_injected(path: Path) -> list[str]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    m = _SECTION_RE.search(text)
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

    def write(self, rules: list[dict]) -> Path:
        p = self.config_path()
        _upsert_section(p, _build_section(rules))
        return p

    def remove(self) -> bool:
        return _remove_section(self.config_path())

    def read_injected(self) -> list[str]:
        return _read_injected(self.config_path())


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


def write_rules_all(rules: list[dict]) -> list[tuple[str, Path]]:
    """Write rules to every detected agent config. Returns (agent_name, path) pairs."""
    results: list[tuple[str, Path]] = []
    for target in detected_targets():
        try:
            path = target.write(rules)
            results.append((target.name, path))
        except Exception:
            pass
    return results


def remove_rules_all() -> list[str]:
    """Remove AI Rule Learning section from all targets. Returns names where removed."""
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
    """Return a plain-text block for inline injection (e.g. Codex system prompt)."""
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
        lines.append("")
    return "\n".join(lines)
