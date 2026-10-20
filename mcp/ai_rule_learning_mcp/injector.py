"""Universal rule + memory + skills injector — writes to all detected AI agent configs.

Supported agents (auto-detected by presence of their config dirs):
  - Claude Code    → ~/.claude/CLAUDE.md
  - Cursor         → ~/.cursor/rules/ai-guardrails.md (and workspace .cursor/rules/)
  - Windsurf       → ~/.windsurf/rules/ai-guardrails.md (and workspace .windsurf/rules/)
  - GitHub Copilot → .github/copilot-instructions.md & ~/.config/github-copilot/instructions.md
  - OpenAI Codex   → ~/.codex/instructions.md & .codex/instructions.md

Each config file receives up to three sections (order: memory, skills, rules):
  1. Memory block  — who the user is, their preferences, active projects
  2. Skills index  — names + descriptions of saved reusable procedures
  3. Rules block   — guardrail rules learned from past sessions

All sections use HTML comment markers and are updated idempotently.
Agents without a persistent config file get rules inline via get_guardrail_rules.
"""

from __future__ import annotations

import os
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
        label = priority.upper() if isinstance(priority, str) else _PRIORITY_LABEL.get(int(priority), "MEDIUM")
        name = rule.get("name", rule.get("rule_id", "rule"))
        instruction = (rule.get("action", {}).get("instruction") or rule.get("instruction", "")).strip()
        line = f"- **[{label}] {name}**"
        if instruction:
            line += f": {instruction}"
        lines.append(line)
    lines += ["", _END]
    return "\n".join(lines)


# ── Generic upsert / remove helpers ───────────────────────────────────────


def _upsert(path: Path, content: str, pattern: re.Pattern, marker_start: str) -> None:
    """Insert or replace a fenced block identified by pattern in a markdown file, preserving user content."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        text = path.read_text(encoding="utf-8")
        if marker_start in text:
            text = pattern.sub(content, text)
        else:
            stripped = text.rstrip()
            text = (stripped + "\n\n" + content + "\n") if stripped else (content + "\n")
    else:
        text = content + "\n"
    path.write_text(text, encoding="utf-8")


def _remove(path: Path, pattern: re.Pattern, marker_start: str) -> bool:
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    if marker_start not in text:
        return False
    cleaned = pattern.sub("", text).strip()
    path.write_text((cleaned + "\n") if cleaned else "", encoding="utf-8")
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

    def _all_paths(self) -> list[Path]:
        return [self.config_path()]

    def is_detected(self) -> bool:
        return self.config_path().parent.exists()

    def write(
        self,
        rules: list[dict],
        memory_block: str = "",
        skills_block: str = "",
    ) -> Path:
        last_path = self.config_path()
        section = _build_section(rules)
        for p in self._all_paths():
            if memory_block:
                _upsert(p, memory_block, _MEM_RE, _MEM_START)
            if skills_block:
                _upsert(p, skills_block, _SKILLS_RE, _SKILLS_START)
            _upsert(p, section, _SECTION_RE, _START)
            last_path = p
        return last_path

    def write_memory(self, memory_block: str) -> Path:
        last_path = self.config_path()
        for p in self._all_paths():
            _upsert(p, memory_block, _MEM_RE, _MEM_START)
            last_path = p
        return last_path

    def write_skills(self, skills_block: str) -> Path:
        last_path = self.config_path()
        for p in self._all_paths():
            _upsert(p, skills_block, _SKILLS_RE, _SKILLS_START)
            last_path = p
        return last_path

    def remove(self) -> bool:
        removed_any = False
        for p in self._all_paths():
            r1 = _remove(p, _SECTION_RE, _START)
            r2 = _remove(p, _MEM_RE, _MEM_START)
            r3 = _remove(p, _SKILLS_RE, _SKILLS_START)
            removed_any = removed_any or r1 or r2 or r3
        return removed_any

    def read_injected(self) -> list[str]:
        for p in self._all_paths():
            bullets = _read_bullets(p, _SECTION_RE)
            if bullets:
                return bullets
        return []


class _ClaudeCodeTarget(_Target):
    name = "Claude Code"

    def config_path(self) -> Path:
        if (Path.cwd() / "CLAUDE.md").exists():
            return Path.cwd() / "CLAUDE.md"
        return Path.home() / ".claude" / "CLAUDE.md"

    def _all_paths(self) -> list[Path]:
        if type(self).config_path is not _ClaudeCodeTarget.config_path:
            return [self.config_path()]
        paths: list[Path] = []
        if (Path.home() / ".claude").exists():
            paths.append(Path.home() / ".claude" / "CLAUDE.md")
        if (Path.cwd() / "CLAUDE.md").exists():
            paths.append(Path.cwd() / "CLAUDE.md")
        return paths or [self.config_path()]

    def is_detected(self) -> bool:
        return (Path.home() / ".claude").exists() or (Path.cwd() / "CLAUDE.md").exists()


class _CursorTarget(_Target):
    name = "Cursor"

    def config_path(self) -> Path:
        if (Path.cwd() / ".cursorrules").exists():
            return Path.cwd() / ".cursorrules"
        cwd_cursor = Path.cwd() / ".cursor"
        if cwd_cursor.exists():
            return cwd_cursor / "rules" / "ai-rule-learning.mdc"
        return Path.home() / ".cursor" / "rules" / "ai-rule-learning.mdc"

    def _all_paths(self) -> list[Path]:
        paths: list[Path] = []
        if type(self).config_path is not _CursorTarget.config_path:
            return [self.config_path()]
        if (Path.home() / ".cursor").exists():
            paths.append(Path.home() / ".cursor" / "rules" / "ai-guardrails.md")
            paths.append(Path.home() / ".cursor" / "rules" / "ai-rule-learning.mdc")
        cwd_cursor = Path.cwd() / ".cursor"
        if cwd_cursor.exists() and cwd_cursor != (Path.home() / ".cursor"):
            paths.append(cwd_cursor / "rules" / "ai-guardrails.md")
            paths.append(cwd_cursor / "rules" / "ai-rule-learning.mdc")
        if (Path.cwd() / ".cursorrules").exists():
            paths.append(Path.cwd() / ".cursorrules")
        return paths or [self.config_path()]

    def is_detected(self) -> bool:
        return (
            (Path.home() / ".cursor").exists()
            or (Path.cwd() / ".cursor").exists()
            or (Path.cwd() / ".cursorrules").exists()
        )


class _WindsurfTarget(_Target):
    name = "Windsurf"

    def config_path(self) -> Path:
        if (Path.cwd() / ".windsurfrules").exists():
            return Path.cwd() / ".windsurfrules"
        cwd_ws = Path.cwd() / ".windsurf"
        if cwd_ws.exists():
            return cwd_ws / "rules" / "ai-rule-learning.md"
        return Path.home() / ".windsurf" / "rules" / "ai-rule-learning.md"

    def _all_paths(self) -> list[Path]:
        paths: list[Path] = []
        if type(self).config_path is not _WindsurfTarget.config_path:
            return [self.config_path()]
        if (Path.home() / ".windsurf").exists():
            paths.append(Path.home() / ".windsurf" / "rules" / "ai-guardrails.md")
            paths.append(Path.home() / ".windsurf" / "rules" / "ai-rule-learning.md")
            paths.append(Path.home() / ".windsurf" / "ai-guardrails.md")
        cwd_ws = Path.cwd() / ".windsurf"
        if cwd_ws.exists() and cwd_ws != (Path.home() / ".windsurf"):
            paths.append(cwd_ws / "rules" / "ai-guardrails.md")
            paths.append(cwd_ws / "rules" / "ai-rule-learning.md")
            paths.append(cwd_ws / "ai-guardrails.md")
        if (Path.cwd() / ".windsurfrules").exists():
            paths.append(Path.cwd() / ".windsurfrules")
        return paths or [self.config_path()]

    def is_detected(self) -> bool:
        return (
            (Path.home() / ".windsurf").exists()
            or (Path.cwd() / ".windsurf").exists()
            or (Path.cwd() / ".windsurfrules").exists()
        )


class _CopilotTarget(_Target):
    name = "GitHub Copilot"

    def config_path(self) -> Path:
        if (Path.home() / ".github").exists():
            return Path.home() / ".github" / "copilot-instructions.md"
        if (Path.cwd() / ".github").exists():
            return Path.cwd() / ".github" / "copilot-instructions.md"
        return Path.home() / ".config" / "github-copilot" / "instructions.md"

    def _all_paths(self) -> list[Path]:
        if type(self).config_path is not _CopilotTarget.config_path:
            return [self.config_path()]
        paths: list[Path] = []
        home_gh = Path.home() / ".github"
        if home_gh.exists():
            paths.append(home_gh / "copilot-instructions.md")
        cwd_gh = Path.cwd() / ".github"
        if cwd_gh.exists() and cwd_gh != home_gh:
            paths.append(cwd_gh / "copilot-instructions.md")
        vscode_hints = [
            Path.home() / ".vscode",
            Path.home() / ".config" / "Code",
            Path.home() / "Library" / "Application Support" / "Code",
        ]
        copilot_dir = Path.home() / ".config" / "github-copilot"
        if copilot_dir.exists() or any(d.exists() for d in vscode_hints):
            paths.append(copilot_dir / "instructions.md")
            paths.append(copilot_dir / "copilot-instructions.md")
        return paths or [self.config_path()]

    def is_detected(self) -> bool:
        vscode_hints = [
            Path.home() / ".vscode",
            Path.home() / ".config" / "Code",
            Path.home() / "Library" / "Application Support" / "Code",
        ]
        copilot_dir = Path.home() / ".config" / "github-copilot"
        return (
            (Path.home() / ".github").exists()
            or (Path.cwd() / ".github").exists()
            or copilot_dir.exists()
            or any(d.exists() for d in vscode_hints)
        )


class _CodexTarget(_Target):
    name = "OpenAI Codex"

    def config_path(self) -> Path:
        if (Path.home() / ".codex").exists():
            return Path.home() / ".codex" / "instructions.md"
        if (Path.cwd() / ".codex").exists():
            return Path.cwd() / ".codex" / "instructions.md"
        return Path.home() / ".codex" / "instructions.md"

    def _all_paths(self) -> list[Path]:
        if type(self).config_path is not _CodexTarget.config_path:
            return [self.config_path()]
        paths: list[Path] = []
        home_codex = Path.home() / ".codex"
        if home_codex.exists():
            paths.extend(
                [
                    home_codex / "instructions.md",
                    home_codex / "AGENTS.md",
                    home_codex / "ai-guardrails.md",
                    home_codex / "rules" / "ai-guardrails.md",
                ]
            )
        cwd_codex = Path.cwd() / ".codex"
        if cwd_codex.exists() and cwd_codex != home_codex:
            paths.extend(
                [
                    cwd_codex / "instructions.md",
                    cwd_codex / "AGENTS.md",
                    cwd_codex / "ai-guardrails.md",
                    cwd_codex / "rules" / "ai-guardrails.md",
                ]
            )
        return paths or [self.config_path()]

    def is_detected(self) -> bool:
        return (Path.home() / ".codex").exists() or (Path.cwd() / ".codex").exists()


_ALL_TARGETS: list[_Target] = [
    _ClaudeCodeTarget(),
    _CursorTarget(),
    _WindsurfTarget(),
    _CopilotTarget(),
    _CodexTarget(),
]


# ── Public API ─────────────────────────────────────────────────────────────


def detected_targets() -> list[_Target]:
    """Return targets for agents that appear to be installed on this machine."""
    return [t for t in _ALL_TARGETS if t.is_detected()]


def write_rules_all(
    rules: list[dict],
    memory_entries: list[dict] | None = None,
    skill_list: list[dict] | None = None,
    project_dir: Path | str | None = None,
    cwd: Path | str | None = None,
) -> list[tuple[str, Path]]:
    """Write rules (and optionally memory + skills) to every detected agent config."""
    from .memory import build_memory_block
    from .skills import build_skills_index

    target_dir = Path(project_dir) if project_dir else (Path(cwd) if cwd else None)
    orig_cwd = os.getcwd()

    try:
        if target_dir:
            os.chdir(target_dir)

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
    finally:
        if target_dir:
            os.chdir(orig_cwd)


def write_memory_all(
    memory_entries: list[dict],
    project_dir: Path | str | None = None,
    cwd: Path | str | None = None,
) -> list[tuple[str, Path]]:
    """Write only the memory block to every detected agent config."""
    from .memory import build_memory_block

    target_dir = Path(project_dir) if project_dir else (Path(cwd) if cwd else None)
    orig_cwd = os.getcwd()

    try:
        if target_dir:
            os.chdir(target_dir)

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
    finally:
        if target_dir:
            os.chdir(orig_cwd)


def write_skills_all(
    skill_list: list[dict],
    project_dir: Path | str | None = None,
    cwd: Path | str | None = None,
) -> list[tuple[str, Path]]:
    """Write only the skills index block to every detected agent config."""
    from .skills import build_skills_index

    target_dir = Path(project_dir) if project_dir else (Path(cwd) if cwd else None)
    orig_cwd = os.getcwd()

    try:
        if target_dir:
            os.chdir(target_dir)

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
    finally:
        if target_dir:
            os.chdir(orig_cwd)


def remove_rules_all(
    project_dir: Path | str | None = None,
    cwd: Path | str | None = None,
) -> list[str]:
    """Remove both rules and memory sections from all targets."""
    target_dir = Path(project_dir) if project_dir else (Path(cwd) if cwd else None)
    orig_cwd = os.getcwd()

    try:
        if target_dir:
            os.chdir(target_dir)

        removed: list[str] = []
        for target in _ALL_TARGETS:
            try:
                if target.remove():
                    removed.append(target.name)
            except Exception:
                pass
        return removed
    finally:
        if target_dir:
            os.chdir(orig_cwd)


clear_all = remove_rules_all


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
        label = priority.upper() if isinstance(priority, str) else _PRIORITY_LABEL.get(int(priority), "MEDIUM")
        name = rule.get("name", rule.get("rule_id", f"Rule {i}"))
        instruction = (rule.get("action", {}).get("instruction") or rule.get("instruction", "")).strip()
        lines.append(f"**Rule {i}: {name}** [{label}]")
        if instruction:
            lines.append(f"→ {instruction}")
        lines.append("")
    return "\n".join(lines)
