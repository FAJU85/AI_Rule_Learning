"""Read and write rules/conversations — local-first, HF optional.

Priority:
  1. Local storage at ~/.ai-rule-learning/ (always works, no config)
  2. HuggingFace dataset (sync/backup when HF_TOKEN + ARL_DATASET are set)
"""

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

# ── Local storage ──────────────────────────────────────────────────────────
LOCAL_DIR = Path.home() / ".ai-rule-learning"


def _local_path(filename: str) -> Path:
    LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    return LOCAL_DIR / filename


def _local_load(filename: str) -> list[dict]:
    p = _local_path(filename)
    if not p.exists():
        return []
    try:
        return [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
    except Exception:
        return []


def _local_save(filename: str, records: list[dict]) -> None:
    _local_path(filename).write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n",
        encoding="utf-8",
    )


def _processed_path() -> Path:
    return _local_path("processed.jsonl")


def is_already_processed(file_path: Path) -> bool:
    """Return True if this file has been synced before."""
    key = str(file_path.resolve())
    processed = _local_load("processed.jsonl")
    return any(r.get("path") == key for r in processed)


def mark_processed(file_path: Path) -> None:
    key = str(file_path.resolve())
    processed = _local_load("processed.jsonl")
    if not any(r.get("path") == key for r in processed):
        processed.append({"path": key, "at": datetime.utcnow().isoformat()})
        _local_save("processed.jsonl", processed)

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
    """Load from HF if configured, otherwise fall back to local storage."""
    if HF_DATASET and HF_TOKEN:
        try:
            from huggingface_hub import hf_hub_download

            path = hf_hub_download(
                repo_id=HF_DATASET,
                filename=filename,
                repo_type="dataset",
                token=HF_TOKEN,
                force_download=True,
            )
            with open(path, encoding="utf-8") as f:
                return [json.loads(ln) for ln in f if ln.strip()]
        except Exception:
            pass
    return _local_load(filename)


def hf_enabled() -> bool:
    """True when both an HF dataset and token are configured (uploads will happen)."""
    return bool(HF_DATASET and HF_TOKEN)


def _upload(filename: str, records: list[dict]) -> None:
    """Save to local storage always; also push to HF if configured."""
    _local_save(filename, records)
    if not HF_DATASET or not HF_TOKEN:
        return
    content = "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n"
    try:
        _hf_api().upload_file(
            path_or_fileobj=content.encode(),
            path_in_repo=filename,
            repo_id=HF_DATASET,
            repo_type="dataset",
            commit_message=f"mcp: update {filename}",
        )
    except Exception:
        pass


_UNSAFE_PHRASES = [
    "never refuse",
    "bypass",
    "override your",
    "ignore safety",
    "ignore all",
    "disregard",
    "forget your",
]


def _is_safe_rule(rule: dict) -> bool:
    """Return True if the rule content contains no unsafe phrases."""
    text = " ".join(
        [
            rule.get("name", ""),
            rule.get("instruction", ""),
            rule.get("action", {}).get("instruction", "") if isinstance(rule.get("action"), dict) else "",
            str(rule.get("triggers", "")),
            str(rule.get("trigger", "")),
        ]
    ).lower()
    return not any(phrase in text for phrase in _UNSAFE_PHRASES)


def auto_activate_pending_rules() -> int:
    """Fetch rules, auto-activate safe pending ones, save back. Returns count activated."""
    rules = _download("rules.jsonl")
    if not rules:
        return 0
    activated = 0
    now = datetime.utcnow().isoformat()
    for rule in rules:
        if rule.get("status") == "pending_review" and not rule.get("is_active", False):
            if _is_safe_rule(rule):
                rule["is_active"] = True
                rule["status"] = "active"
                rule["approved_at"] = now
                activated += 1
    if activated:
        _upload("rules.jsonl", rules)
    return activated


def load_active_rules() -> list[dict]:
    """Return all active rules from the dataset, sorted by priority desc."""
    rules = _download("rules.jsonl")
    active = [r for r in rules if r.get("is_active", True) or r.get("status") == "active"]
    return sorted(active, key=lambda r: r.get("priority", 0), reverse=True)


def record_rule_outcome(rule_id: str, fired_again: bool) -> dict | None:
    """Update effectiveness tracking for a rule.

    fired_again=True  → gap recurred after rule injection (rule not working).
    fired_again=False → gap stopped recurring (rule suppressed the problem).

    Returns the updated rule dict, or None if rule_id not found.
    """
    rules = _download("rules.jsonl")
    now = datetime.utcnow().isoformat()
    target = next((r for r in rules if r.get("rule_id") == rule_id), None)
    if target is None:
        return None

    target["last_fired_at"] = now
    if fired_again:
        target["times_triggered"] = target.get("times_triggered", 0) + 1
        # Decay score — cap at 0.0
        target["effectiveness_score"] = max(
            0.0, round(target.get("effectiveness_score", 0.5) - 0.1, 2)
        )
    else:
        target["suppression_count"] = target.get("suppression_count", 0) + 1
        # Grow score — cap at 1.0
        target["effectiveness_score"] = min(
            1.0, round(target.get("effectiveness_score", 0.5) + 0.1, 2)
        )

    _upload("rules.jsonl", rules)
    return target


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
        return " ".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text").strip()
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
                turns.append(
                    {
                        "turn_number": len(turns) + 1,
                        "user_input": scrub_pii(messages[i]["text"][:4000]),
                        "agent_response": scrub_pii(messages[j]["text"][:4000]),
                        "timestamp": messages[i]["ts"],
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
