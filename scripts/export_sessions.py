#!/usr/bin/env python3
"""Export Claude Code session files to the HF dataset.

Reads ~/.claude/projects/**/*.jsonl (Claude Code stores every session there),
converts them to the Conversation format the dashboard understands, and
uploads to the vooom/AI_Rule_Learning HF dataset — no Anthropic API needed.

Usage:
    python scripts/export_sessions.py                    # export all sessions
    python scripts/export_sessions.py --session <id>     # export one session
    python scripts/export_sessions.py --dry-run          # preview without uploading
    python scripts/export_sessions.py --project /path    # use a different project dir
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DATASET_ID = "vooom/AI_Rule_Learning"
HF_TOKEN = os.environ.get("HF_TOKEN")
DEFAULT_CLAUDE_DIR = Path.home() / ".claude" / "projects"

# Regex patterns for PII detection
_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", re.IGNORECASE)
_HOME_RE = re.compile(r"(?:/home/[^/\s]+|/Users/[^/\s]+|C:\\Users\\[^\\\s]+)", re.IGNORECASE)
_IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_PHONE_RE = re.compile(r"\b(?:\+?\d[\d\s\-().]{7,}\d)\b")
_TOKEN_RE = re.compile(r"\b(hf_|sk-|ghp_|gho_|ghs_|github_pat_)[A-Za-z0-9_\-]{10,}\b")


def _scrub_pii(text: str) -> str:
    """Replace common PII patterns with safe placeholders."""
    text = _EMAIL_RE.sub("[EMAIL]", text)
    text = _HOME_RE.sub("[HOME]", text)
    text = _IP_RE.sub("[IP]", text)
    text = _PHONE_RE.sub("[PHONE]", text)
    text = _TOKEN_RE.sub("[TOKEN]", text)
    return text


def _sanitize_path(cwd: str) -> str:
    """Return only the project folder name, stripping the home prefix."""
    if not cwd:
        return ""
    path = Path(cwd)
    # Drop everything up to and including the home directory
    try:
        rel = path.relative_to(Path.home())
        return str(rel)
    except ValueError:
        pass
    # Fallback: strip leading /home/<user> or /Users/<user>
    sanitized = _HOME_RE.sub("[HOME]", str(path))
    return sanitized


# ---------------------------------------------------------------------------
# Parse a single session JSONL file → Conversation dict
# ---------------------------------------------------------------------------


def _extract_text(content: Any) -> str:
    """Pull plain text out of either a string or a Gradio/Anthropic content block list."""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block["text"])
        return " ".join(parts).strip()
    return ""


def parse_session(path: Path) -> dict | None:
    """Parse one Claude Code session JSONL into a Conversation dict.

    Returns None if the session has fewer than 2 turns or is unreadable.
    """
    messages: list[dict] = []
    session_meta: dict = {}

    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue

                msg = obj.get("message", {})
                role = msg.get("role")

                # Capture session-level metadata from the first record
                if not session_meta:
                    session_meta = {
                        "session_id": obj.get("sessionId", str(uuid.uuid4())),
                        "slug": obj.get("slug", ""),
                        "cwd": obj.get("cwd", ""),
                        "git_branch": obj.get("gitBranch", ""),
                        "started_at": obj.get("timestamp", datetime.utcnow().isoformat()),
                    }

                if role not in ("user", "assistant"):
                    continue

                text = _extract_text(msg.get("content", ""))
                if not text:
                    continue

                # Skip system-injected messages (webhook activity, tool results wrapped as user)
                if role == "user" and any(
                    tag in text
                    for tag in [
                        "<github-webhook-activity>",
                        "<system-reminder>",
                        "<task-notification>",
                        "<untrusted_external_data",
                    ]
                ):
                    continue

                messages.append(
                    {
                        "role": role,
                        "text": text,
                        "timestamp": obj.get("timestamp", ""),
                        "uuid": obj.get("uuid", ""),
                        "parent_uuid": obj.get("parentUuid"),
                    }
                )
    except Exception as exc:
        print(f"  ⚠️  Could not read {path.name}: {exc}", file=sys.stderr)
        return None

    if not session_meta:
        return None

    # Build turns by pairing consecutive user→assistant messages
    turns: list[dict] = []
    turn_number = 0
    i = 0
    while i < len(messages):
        if messages[i]["role"] == "user":
            user_text = messages[i]["text"]
            # Find the next assistant reply
            j = i + 1
            while j < len(messages) and messages[j]["role"] != "assistant":
                j += 1
            if j < len(messages):
                assistant_text = messages[j]["text"]
                turn_number += 1
                turns.append(
                    {
                        "turn_number": turn_number,
                        "user_input": _scrub_pii(user_text[:4000]),
                        "agent_response": _scrub_pii(assistant_text[:4000]),
                        "timestamp": messages[i]["timestamp"],
                        "gaps_detected": [],
                        "rules_applied": [],
                        "sensor_reading": None,
                    }
                )
                i = j + 1
                continue
        i += 1

    if len(turns) < 2:
        return None

    conversation_id = f"claude_code_{session_meta['session_id']}"
    return {
        "conversation_id": conversation_id,
        "session_id": session_meta["session_id"],
        "slug": session_meta["slug"],
        "project_context": _sanitize_path(session_meta.get("cwd", "")),
        "git_branch": session_meta.get("git_branch", ""),
        "source": "claude_code_local",
        "turns": turns,
        "escalation_occurred": False,
        "human_intervention": False,
        "started_at": session_meta["started_at"],
        "ended_at": datetime.utcnow().isoformat(),
        "exported_at": datetime.utcnow().isoformat(),
    }


# ---------------------------------------------------------------------------
# Discover session files
# ---------------------------------------------------------------------------


def find_sessions(projects_dir: Path, session_filter: str | None = None) -> list[Path]:
    """Return all session JSONL paths under *projects_dir*."""
    paths = []
    for project_dir in projects_dir.iterdir():
        if not project_dir.is_dir():
            continue
        for f in project_dir.glob("*.jsonl"):
            # Skip .ccr-tip files (they're checkpoint metadata, not sessions)
            if ".ccr-tip" in f.name:
                continue
            if session_filter and session_filter not in f.stem:
                continue
            paths.append(f)
    return sorted(paths, key=lambda p: p.stat().st_mtime, reverse=True)


# ---------------------------------------------------------------------------
# HF dataset I/O
# ---------------------------------------------------------------------------


def _download_existing(filename: str) -> list[dict]:
    try:
        from huggingface_hub import hf_hub_download

        path = hf_hub_download(
            repo_id=DATASET_ID,
            filename=filename,
            repo_type="dataset",
            token=HF_TOKEN,
            force_download=True,
        )
        records = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        return records
    except Exception:
        return []


def _upload(filename: str, records: list[dict]) -> None:
    from huggingface_hub import HfApi

    api = HfApi(token=HF_TOKEN)
    content = "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n"
    api.upload_file(
        path_or_fileobj=content.encode("utf-8"),
        path_in_repo=filename,
        repo_id=DATASET_ID,
        repo_type="dataset",
        commit_message=f"Import {len(records)} conversation(s) from Claude Code sessions",
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

RULES_CACHE = Path.home() / ".claude" / "ai_rule_learning_rules.md"


def _save_rules_locally(rules: list[dict]) -> None:
    """Save active rules to a local markdown cache for SessionStart hook injection."""
    if not rules:
        return
    lines = [
        "## Your AI Guardrail Rules\n",
        f"*{len(rules)} active rule(s) — auto-synced from AI Rule Learning*\n",
    ]
    for i, rule in enumerate(rules, 1):
        priority = rule.get("priority_label", "MEDIUM")
        name = rule.get("name", rule.get("rule_id", f"Rule {i}"))
        instruction = rule.get("action", {}).get("instruction") or rule.get("instruction", "")
        triggers = rule.get("trigger", {}).get("keywords") or rule.get("triggers", [])
        lines.append(f"**Rule {i}: {name}** [{priority}]")
        if instruction:
            lines.append(f"→ {instruction}")
        if triggers:
            lines.append(f"   Triggers on: {', '.join(str(t) for t in triggers[:6])}")
        lines.append("")
    RULES_CACHE.parent.mkdir(parents=True, exist_ok=True)
    RULES_CACHE.write_text("\n".join(lines), encoding="utf-8")
    print(f"💾 Rules saved to {RULES_CACHE}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export Claude Code sessions to HF dataset")
    parser.add_argument("--session", help="Export only this session ID")
    parser.add_argument("--project", help="Path to .claude/projects dir", default=str(DEFAULT_CLAUDE_DIR))
    parser.add_argument("--dry-run", action="store_true", help="Parse only, do not upload")
    parser.add_argument("--force", action="store_true", help="Re-upload even if session already exists")
    parser.add_argument("--sync-rules", action="store_true", help="After upload, pull latest rules and save locally")
    args = parser.parse_args()

    projects_dir = Path(args.project)
    if not projects_dir.exists():
        print(f"❌ Projects directory not found: {projects_dir}")
        sys.exit(1)

    print(f"📂 Scanning {projects_dir} …")
    session_files = find_sessions(projects_dir, args.session)
    print(f"   Found {len(session_files)} session file(s)")

    # Load existing conversations to avoid duplicates
    existing_ids: set[str] = set()
    if not args.dry_run and not args.force:
        print("📥 Loading existing conversations from dataset …")
        existing = _download_existing("conversations.jsonl")
        existing_ids = {c.get("conversation_id") for c in existing}
        print(f"   {len(existing_ids)} conversation(s) already in dataset")
    else:
        existing = []

    # Parse sessions
    new_conversations: list[dict] = []
    skipped = 0
    for path in session_files:
        conv = parse_session(path)
        if conv is None:
            skipped += 1
            continue
        if conv["conversation_id"] in existing_ids:
            print(f"   ↩️  Already uploaded: {conv['slug'] or conv['session_id'][:12]}")
            continue
        turns = len(conv["turns"])
        print(f"   ✅ {conv['slug'] or conv['session_id'][:12]} — {turns} turn(s)")
        new_conversations.append(conv)

    print(f"\n📊 Summary: {len(new_conversations)} new, {skipped} skipped (too short/unreadable)")

    if not new_conversations:
        print("ℹ️  Nothing new to upload.")
        return

    if args.dry_run:
        print("\n[dry-run] Would upload the above conversations. Pass without --dry-run to upload.")
        return

    if not HF_TOKEN:
        print("\n❌ HF_TOKEN not set. Export HF_TOKEN=<your-token> and retry.")
        sys.exit(1)

    print(f"\n⬆️  Uploading {len(new_conversations)} conversation(s) to {DATASET_ID} …")
    all_conversations = existing + new_conversations
    _upload("conversations.jsonl", all_conversations)
    print(f"🎉 Done! Dataset now has {len(all_conversations)} conversation(s).")
    print("   Open the Space → Overview tab to see the updated metrics.")

    if args.sync_rules:
        print("\n📥 Pulling latest rules from dataset …")
        rules = _download_existing("rules.jsonl")
        active = sorted(
            [r for r in rules if r.get("is_active", True)],
            key=lambda r: r.get("priority", 0),
            reverse=True,
        )
        if active:
            _save_rules_locally(active)
            print(f"   {len(active)} active rule(s) cached locally.")
        else:
            print("   No active rules found in dataset yet.")


if __name__ == "__main__":
    main()
