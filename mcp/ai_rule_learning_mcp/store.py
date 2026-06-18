"""Read and write rules/conversations to the user's HF dataset."""

from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

HF_DATASET = os.environ.get("ARL_DATASET", "")
HF_TOKEN = os.environ.get("HF_TOKEN", "")

# PII patterns
_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", re.IGNORECASE)
_HOME_RE = re.compile(r"(?:/home/[^/\s]+|/Users/[^/\s]+|C:\\Users\\[^\\\s]+)", re.IGNORECASE)
_IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_PHONE_RE = re.compile(r"\b(?:\+?\d[\d\s\-().]{7,}\d)\b")
_TOKEN_RE = re.compile(r"\b(hf_|sk-|ghp_|gho_|ghs_|github_pat_)[A-Za-z0-9_\-]{10,}\b")


def scrub_pii(text: str) -> str:
    text = _EMAIL_RE.sub("[EMAIL]", text)
    text = _HOME_RE.sub("[HOME]", text)
    text = _IP_RE.sub("[IP]", text)
    text = _PHONE_RE.sub("[PHONE]", text)
    text = _TOKEN_RE.sub("[TOKEN]", text)
    return text


def _hf_api():
    from huggingface_hub import HfApi
    return HfApi(token=HF_TOKEN)


def _download(filename: str) -> list[dict]:
    if not HF_DATASET or not HF_TOKEN:
        return []
    try:
        from huggingface_hub import hf_hub_download
        path = hf_hub_download(
            repo_id=HF_DATASET, filename=filename,
            repo_type="dataset", token=HF_TOKEN, force_download=True,
        )
        with open(path, encoding="utf-8") as f:
            return [json.loads(l) for l in f if l.strip()]
    except Exception:
        return []


def _upload(filename: str, records: list[dict]) -> None:
    if not HF_DATASET or not HF_TOKEN:
        return
    content = "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n"
    _hf_api().upload_file(
        path_or_fileobj=content.encode(),
        path_in_repo=filename,
        repo_id=HF_DATASET,
        repo_type="dataset",
        commit_message=f"mcp: update {filename}",
    )


def load_active_rules() -> list[dict]:
    """Return all active rules from the dataset, sorted by priority desc."""
    rules = _download("rules.jsonl")
    active = [r for r in rules if r.get("is_active", True)]
    return sorted(active, key=lambda r: r.get("priority", 0), reverse=True)


def append_conversations(convs: list[dict]) -> int:
    """Merge new conversations into dataset. Returns count added."""
    existing = _download("conversations.jsonl")
    existing_ids = {c.get("conversation_id") for c in existing}
    new = [c for c in convs if c.get("conversation_id") not in existing_ids]
    if new:
        _upload("conversations.jsonl", existing + new)
    return len(new)


def _extract_text(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        return " ".join(
            b.get("text", "") for b in content
            if isinstance(b, dict) and b.get("type") == "text"
        ).strip()
    return ""


_SKIP_TAGS = ["<github-webhook-activity>", "<system-reminder>", "<task-notification>"]


def parse_claude_session(path: Path) -> dict | None:
    """Parse a Claude Code session JSONL into a scrubbed Conversation dict."""
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
                        "git_branch": obj.get("gitBranch", ""),
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

    turns = []
    i = 0
    while i < len(messages):
        if messages[i]["role"] == "user":
            j = i + 1
            while j < len(messages) and messages[j]["role"] != "assistant":
                j += 1
            if j < len(messages):
                turns.append({
                    "turn_number": len(turns) + 1,
                    "user_input": scrub_pii(messages[i]["text"][:4000]),
                    "agent_response": scrub_pii(messages[j]["text"][:4000]),
                    "timestamp": messages[i]["ts"],
                    "gaps_detected": [],
                    "rules_applied": [],
                    "sensor_reading": None,
                })
                i = j + 1
                continue
        i += 1

    if len(turns) < 2:
        return None

    # Sanitize cwd → relative path
    cwd = meta.get("cwd", "")
    try:
        project_context = str(Path(cwd).relative_to(Path.home()))
    except ValueError:
        project_context = _HOME_RE.sub("[HOME]", cwd)

    return {
        "conversation_id": f"claude_code_{meta['session_id']}",
        "session_id": meta["session_id"],
        "slug": meta["slug"],
        "project_context": project_context,
        "git_branch": meta.get("git_branch", ""),
        "source": "mcp_local",
        "turns": turns,
        "escalation_occurred": False,
        "human_intervention": False,
        "started_at": meta["started_at"],
        "ended_at": datetime.utcnow().isoformat(),
        "exported_at": datetime.utcnow().isoformat(),
    }
