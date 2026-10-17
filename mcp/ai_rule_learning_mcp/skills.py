"""Personal skills library — reusable workflows, prompt templates, and checklists.

Stored as individual markdown files in ~/.ai-rule-learning/skills/<slug>.md
Injected into agent instruction files via build_skills_index.
"""

from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import re
from typing import Any

from .store import scrub_pii

_SKILLS_START = "<!-- AI-Rule-Learning:skills:start -->"
_SKILLS_END = "<!-- AI-Rule-Learning:skills:end -->"


def _skills_dir() -> Path:
    from . import store

    d = getattr(store, "_effective_local_dir", lambda: getattr(store, "LOCAL_DIR", Path.home() / ".ai-rule-learning"))()
    p = Path(d) / "skills"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _slug(name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9-]", "-", name.strip().replace("_", "-")).lower()
    cleaned = re.sub(r"-+", "-", cleaned).strip("-")
    return cleaned[:60]


def _skill_path(name: str) -> Path:
    return _skills_dir() / f"{_slug(name)}.md"


def _parse_skill_file(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return None

    lines = text.splitlines()
    name = ""
    description = ""
    triggers: list[str] = []
    used_count = 0
    created_at = datetime.now(timezone.utc).isoformat()
    steps_lines: list[str] = []
    in_steps = False

    for line in lines:
        if line.startswith("# ") and not name:
            name = line[2:].strip()
        elif "<!-- skill:triggers -->" in line:
            raw = line.split("<!-- skill:triggers -->", 1)[1].strip()
            triggers = [t.strip() for t in raw.split(",") if t.strip()]
        elif "<!-- skill:used_count -->" in line:
            raw = line.split("<!-- skill:used_count -->", 1)[1].strip()
            try:
                used_count = int(raw)
            except ValueError:
                used_count = 0
        elif "<!-- skill:created_at -->" in line:
            created_at = line.split("<!-- skill:created_at -->", 1)[1].strip()
        elif line.startswith("## Steps"):
            in_steps = True
            steps_lines.append(line)
        elif in_steps:
            steps_lines.append(line)
        elif line.strip() and not description and not line.startswith("#") and not line.startswith("<!--"):
            description = line.strip()

    steps = "\n".join(steps_lines).strip()
    return {
        "name": name or path.stem,
        "slug": path.stem,
        "description": description,
        "steps": steps,
        "triggers": triggers,
        "used_count": used_count,
        "created_at": created_at,
    }


def save_skill(
    name: str,
    description: str,
    steps: list[str] | str,
    triggers: list[str] | None = None,
) -> dict[str, Any]:
    """Create or update a skill. Returns skill dict."""
    if not name or not name.strip():
        raise ValueError("skill name cannot be empty")
    if steps is None:
        raise ValueError("steps cannot be empty")
    if isinstance(steps, list):
        steps_str = "\n".join(str(s) for s in steps)
    else:
        steps_str = str(steps)
    if not steps_str.strip():
        raise ValueError("steps cannot be empty")

    name = scrub_pii(name.strip())
    slug = _slug(name)
    description = scrub_pii(description.strip()) if isinstance(description, str) else ""
    steps_str = scrub_pii(steps_str.strip())
    trigger_list = [scrub_pii(str(t).strip()) for t in (triggers or []) if str(t).strip()]

    path = _skill_path(name)
    used_count = 0
    created_at = datetime.now(timezone.utc).isoformat()

    if path.exists():
        existing = _parse_skill_file(path)
        if existing:
            used_count = existing.get("used_count", 0)
            created_at = existing.get("created_at", created_at)

    file_lines = [
        f"# {name}",
        "",
        description,
        "",
        f"<!-- skill:triggers --> {', '.join(trigger_list)}",
        f"<!-- skill:used_count --> {used_count}",
        f"<!-- skill:created_at --> {created_at}",
        "",
    ]
    if not steps_str.startswith("## Steps"):
        file_lines.extend(["## Steps", steps_str])
    else:
        file_lines.append(steps_str)

    path.write_text("\n".join(file_lines).strip() + "\n", encoding="utf-8")

    return {
        "name": name,
        "slug": slug,
        "description": description,
        "steps": steps_str if steps_str.startswith("## Steps") else f"## Steps\n{steps_str}",
        "triggers": trigger_list,
        "used_count": used_count,
        "created_at": created_at,
    }


def get_skill(name_or_query: str) -> dict[str, Any] | None:
    if not name_or_query or not name_or_query.strip():
        return None
    q = name_or_query.strip().lower()
    q_slug = _slug(q)

    # 1. Exact slug match
    exact_path = _skills_dir() / f"{q_slug}.md"
    if exact_path.exists():
        skill = _parse_skill_file(exact_path)
        if skill:
            skill["used_count"] += 1
            # Update file with new used_count
            save_skill(
                skill["name"],
                skill["description"],
                skill["steps"],
                triggers=skill["triggers"],
            )
            # Re-update used count in file
            content = exact_path.read_text(encoding="utf-8")
            content = re.sub(
                r"<!-- skill:used_count --> \d+",
                f"<!-- skill:used_count --> {skill['used_count']}",
                content,
            )
            exact_path.write_text(content, encoding="utf-8")
            return skill

    # 2. Search through all skill files
    for f in _skills_dir().glob("*.md"):
        skill = _parse_skill_file(f)
        if not skill:
            continue
        if skill["slug"] == q_slug or skill["name"].lower() == q or q in skill["name"].lower():
            skill["used_count"] += 1
            content = f.read_text(encoding="utf-8")
            content = re.sub(
                r"<!-- skill:used_count --> \d+",
                f"<!-- skill:used_count --> {skill['used_count']}",
                content,
            )
            f.write_text(content, encoding="utf-8")
            return skill

    return None


def list_skills() -> list[dict[str, Any]]:
    skills: list[dict[str, Any]] = []
    for f in _skills_dir().glob("*.md"):
        s = _parse_skill_file(f)
        if s:
            skills.append(
                {
                    "name": s["name"],
                    "slug": s["slug"],
                    "description": s["description"],
                    "triggers": s["triggers"],
                    "used_count": s["used_count"],
                    "created_at": s["created_at"],
                }
            )
    return sorted(skills, key=lambda s: s["name"].lower())


def delete_skill(name: str) -> bool:
    target = _skill_path(name)
    if target.exists():
        target.unlink()
        return True
    q = name.strip().lower()
    for f in _skills_dir().glob("*.md"):
        s = _parse_skill_file(f)
        if s and (s["slug"] == _slug(q) or s["name"].lower() == q):
            f.unlink()
            return True
    return False


def build_skills_index(skills: list[dict[str, Any]]) -> str:
    if not skills:
        return ""
    lines = [_SKILLS_START, "## Available Skills", ""]
    for s in skills:
        name = s.get("name", "")
        desc = s.get("description", "")
        triggers = s.get("triggers", [])
        if triggers:
            top_triggers = ", ".join(triggers[:3])
            lines.append(f"- **{name}** ({top_triggers}): {desc}")
        else:
            lines.append(f"- **{name}**: {desc}")
    lines.append("")
    lines.append(_SKILLS_END)
    return "\n".join(lines).strip()


def format_skills_for_display(skills: list[dict[str, Any]]) -> str:
    if not skills:
        return "No skills saved yet. Use `arl skill save <name> <desc> <steps>` or the `save_skill` MCP tool."
    lines = [f"# Saved Skills ({len(skills)})", ""]
    for s in skills:
        name = s.get("name", "")
        desc = s.get("description", "")
        count = s.get("used_count", 0)
        lines.append(f"- **{name}**: {desc} (used {count} time(s))")
    return "\n".join(lines).strip()


def format_skill_detail(skill: dict[str, Any]) -> str:
    name = skill.get("name", "")
    desc = skill.get("description", "")
    triggers = ", ".join(skill.get("triggers", []))
    steps = skill.get("steps", "")
    lines = [
        f"# Skill: {name}",
        f"**Description:** {desc}",
        f"**Triggers:** {triggers}",
        "",
        steps,
    ]
    return "\n".join(lines).strip()
