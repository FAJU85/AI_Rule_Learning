"""Reusable skill procedures — saved workflows that apply consistently every time.

Skills are stored as markdown files in ~/.ai-rule-learning/skills/<slug>.md
with a lightweight YAML-style header. When the agent encounters a familiar
task, it loads the relevant skill and follows the procedure exactly.

A skill index is injected into every AI agent config so agents know which
skills exist without loading them all into context.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

_SKILLS_START = "<!-- AI-Rule-Learning:skills:start -->"
_SKILLS_END = "<!-- AI-Rule-Learning:skills:end -->"


def _skills_dir() -> Path:
    from .store import LOCAL_DIR

    d = LOCAL_DIR / "skills"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _slug(name: str) -> str:
    """Convert a skill name to a safe filename slug."""
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    return slug[:60]


def _skill_path(name: str) -> Path:
    return _skills_dir() / f"{_slug(name)}.md"


# ── Skill file format ──────────────────────────────────────────────────────
# A simple header block (no external YAML parser needed) + freeform markdown.
#
# <!-- skill:name --> Create Python Module
# <!-- skill:description --> Steps to create a new Python module with tests
# <!-- skill:triggers --> create module, new module, add module
# <!-- skill:created_at --> 2026-06-21T02:00:00
# <!-- skill:used_count --> 0
#
# ## Steps
# 1. ...

_HEADER_RE = re.compile(r"<!-- skill:(\w+) -->\s*(.+)")


def _build_skill_file(
    name: str,
    description: str,
    steps: str,
    triggers: list[str],
    created_at: str,
    used_count: int = 0,
) -> str:
    triggers_str = ", ".join(triggers) if triggers else ""
    return (
        f"<!-- skill:name --> {name}\n"
        f"<!-- skill:description --> {description}\n"
        f"<!-- skill:triggers --> {triggers_str}\n"
        f"<!-- skill:created_at --> {created_at}\n"
        f"<!-- skill:used_count --> {used_count}\n"
        f"\n"
        f"{steps.strip()}\n"
    )


def _parse_skill_file(path: Path) -> dict | None:
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    meta: dict = {}
    body_lines = []
    in_body = False
    for line in text.splitlines():
        m = _HEADER_RE.match(line)
        if m and not in_body:
            meta[m.group(1)] = m.group(2).strip()
        else:
            in_body = True
            body_lines.append(line)
    if "name" not in meta:
        return None
    triggers_raw = meta.get("triggers", "")
    triggers = [t.strip() for t in triggers_raw.split(",") if t.strip()] if triggers_raw else []
    return {
        "name": meta["name"],
        "slug": path.stem,
        "description": meta.get("description", ""),
        "triggers": triggers,
        "created_at": meta.get("created_at", ""),
        "used_count": int(meta.get("used_count", 0)),
        "steps": "\n".join(body_lines).strip(),
    }


# ── Public API ─────────────────────────────────────────────────────────────

def save_skill(
    name: str,
    description: str,
    steps: str,
    triggers: list[str] | None = None,
) -> dict:
    """Save or update a skill. Returns the skill dict."""
    if not name.strip():
        raise ValueError("skill name cannot be empty")
    if not steps.strip():
        raise ValueError("steps cannot be empty")

    triggers = triggers or []
    path = _skill_path(name)

    # Preserve used_count if updating an existing skill
    used_count = 0
    if path.exists():
        existing = _parse_skill_file(path)
        if existing:
            used_count = existing.get("used_count", 0)

    created_at = datetime.utcnow().isoformat()
    content = _build_skill_file(name, description, steps, triggers, created_at, used_count)
    path.write_text(content, encoding="utf-8")

    return {
        "name": name,
        "slug": _slug(name),
        "description": description,
        "triggers": triggers,
        "created_at": created_at,
        "used_count": used_count,
        "steps": steps,
    }


def get_skill(name: str) -> dict | None:
    """Load a skill by name or slug. Returns None if not found."""
    # Try exact slug first
    path = _skill_path(name)
    if path.exists():
        skill = _parse_skill_file(path)
        if skill:
            # Increment used_count
            skill["used_count"] += 1
            content = _build_skill_file(
                skill["name"], skill["description"], skill["steps"],
                skill["triggers"], skill["created_at"], skill["used_count"],
            )
            path.write_text(content, encoding="utf-8")
        return skill

    # Fuzzy: search by name substring
    for p in _skills_dir().glob("*.md"):
        s = _parse_skill_file(p)
        if s and name.lower() in s["name"].lower():
            return s
    return None


def list_skills() -> list[dict]:
    """Return all saved skills (metadata only, no steps) sorted by name."""
    skills = []
    for p in sorted(_skills_dir().glob("*.md")):
        s = _parse_skill_file(p)
        if s:
            skills.append({k: v for k, v in s.items() if k != "steps"})
    return skills


def delete_skill(name: str) -> bool:
    """Delete a skill by name or slug. Returns True if deleted."""
    path = _skill_path(name)
    if path.exists():
        path.unlink()
        return True
    return False


def build_skills_index(skills: list[dict]) -> str:
    """Render the skills index block for injection into agent configs."""
    if not skills:
        return ""
    lines = [_SKILLS_START, "", "## Saved Skills", ""]
    lines.append("These are reusable procedures. Call `get_skill(name)` to load steps:")
    lines.append("")
    for s in skills:
        name = s["name"]
        desc = s.get("description", "")
        triggers = s.get("triggers", [])
        line = f"- **{name}**"
        if desc:
            line += f": {desc}"
        if triggers:
            line += f" _(triggers: {', '.join(triggers[:3])})_"
        lines.append(line)
    lines += ["", _SKILLS_END]
    return "\n".join(lines)


def format_skills_for_display(skills: list[dict]) -> str:
    """Human-readable skills list for CLI and recall."""
    if not skills:
        return "No skills saved yet. Use the `save_skill` tool to add one."
    lines = [f"## Skills ({len(skills)} saved)\n"]
    for s in skills:
        lines.append(f"**{s['name']}**")
        if s.get("description"):
            lines.append(f"  {s['description']}")
        if s.get("triggers"):
            lines.append(f"  Triggers: {', '.join(s['triggers'])}")
        lines.append(f"  Used: {s.get('used_count', 0)} time(s)")
        lines.append("")
    return "\n".join(lines)


def format_skill_detail(skill: dict) -> str:
    """Full skill detail including steps, for get_skill responses."""
    lines = [
        f"## {skill['name']}",
        "",
        skill.get("description", ""),
        "",
    ]
    if skill.get("triggers"):
        lines.append(f"**Triggers:** {', '.join(skill['triggers'])}")
        lines.append("")
    lines.append(skill.get("steps", ""))
    return "\n".join(lines).strip()
