"""Read and write rules/conversations — local-first, remote optional.

Priority:
  1. Local storage at ~/.ai-rule-learning/ (always works, no config)
  2. Cloudflare R2 bucket (sync/backup when R2_BUCKET + credentials are set)
"""

from __future__ import annotations

import json
import logging
import os
import re
import uuid
from datetime import UTC
from datetime import datetime
from pathlib import Path
from typing import Any

from .injection import is_prompt_injection

_log = logging.getLogger(__name__)

# Remote sync backend is a Cloudflare R2 bucket (S3-compatible). Connection
# settings are read at call time from the environment (see ``_r2_config``);
# credentials must be supplied via secrets and are never hardcoded.

# ── Local storage ──────────────────────────────────────────────────────────
_INITIAL_HOME = Path.home()
LOCAL_DIR = _INITIAL_HOME / ".ai-rule-learning"
RULES_FILE = LOCAL_DIR / "rules.jsonl"
LOCAL_RULES = RULES_FILE


def _effective_local_dir() -> Path:
    """Resolve storage directory, honoring both monkeypatched LOCAL_DIR and dynamic HOME changes."""
    if LOCAL_DIR != _INITIAL_HOME / ".ai-rule-learning":
        return Path(LOCAL_DIR)
    return Path.home() / ".ai-rule-learning"


def _ensure_dir(d: Path) -> Path:
    """Ensure *d* exists as a directory, self-healing when a file occupies the path.

    ``Path.mkdir(exist_ok=True)`` still raises ``FileExistsError`` when the path
    is an existing *non-directory* file, which previously surfaced as silent
    read-returns-nothing / write-fails behaviour (R05). Detect that case, move
    the stray file aside with a loud warning, and recreate the directory so the
    store self-heals instead of failing silently. The displaced file is never
    deleted — it is preserved as ``<name>.corrupt-<timestamp>``.
    """
    if d.exists() and not d.is_dir():
        backup = d.with_name(f"{d.name}.corrupt-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}")
        try:
            os.replace(d, backup)
            _log.warning(
                "Storage path %s was a regular file, not a directory; moved it to %s "
                "and recreated the directory.",
                d,
                backup,
            )
        except Exception as exc:
            _log.error("Storage path %s is a file and could not be moved aside: %s", d, exc)
            raise
    d.mkdir(parents=True, exist_ok=True)
    return d


def _local_path(filename: str) -> Path:
    if filename == "rules.jsonl":
        if RULES_FILE != _INITIAL_HOME / ".ai-rule-learning" / "rules.jsonl":
            p = Path(RULES_FILE)
            _ensure_dir(p.parent)
            return p
        if LOCAL_RULES != _INITIAL_HOME / ".ai-rule-learning" / "rules.jsonl":
            p = Path(LOCAL_RULES)
            _ensure_dir(p.parent)
            return p
    d = _effective_local_dir()
    _ensure_dir(d)
    return d / filename


def _local_load(filename: str) -> list[dict]:
    """Load JSONL records line by line with per-line fault tolerance and concurrent read tolerance (E01b, X04a)."""
    p = _local_path(filename)
    if not p.exists():
        return []
    lines: list[str] = []
    for attempt in range(3):
        try:
            lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()
            break
        except Exception as exc:
            if attempt < 2:
                import time

                time.sleep(0.01)
            else:
                _log.warning("Failed reading %s after 3 attempts: %s", p, exc)
                return []

    out: list[dict] = []
    for line_no, ln in enumerate(lines, 1):
        ln = ln.strip()
        if not ln:
            continue
        try:
            rec = json.loads(ln)
            if isinstance(rec, dict):
                out.append(rec)
        except Exception as exc:
            # Log and skip corrupted line while preserving remaining valid records
            _log.warning("Skipping corrupted JSONL record in %s at line %d: %s", filename, line_no, exc)
            continue
    return out


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
        processed.append({"path": key, "at": datetime.now(UTC).replace(tzinfo=None).isoformat()})
        _local_save("processed.jsonl", processed)


# PII patterns (Defect Q10, C0.3, C2.2, AS01 — comprehensive coverage)
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_HOME_RE = re.compile(
    r"(?:~[/\\][^\s,;\"']+|/(?:home|Users)/[^\s,;\"']+|[a-zA-Z]:[/\\](?:Users|Documents)[^\s,;\"']*)",
    re.IGNORECASE,
)
_TRAVERSAL_RE = re.compile(r"(?:\.\.[/\\])+[^\s,;\"']+", re.IGNORECASE)
_SYS_PATH_RE = re.compile(
    r"(?:/(?:etc|var|tmp|app|opt|usr|root|srv|bin|sbin|dev|private)[/\\][^\s,;\"']+)",
    re.IGNORECASE,
)
_FILE_PATH_RE = re.compile(
    r"(?:(?:\.{1,2}|[a-zA-Z]:)?[/\\](?:[a-zA-Z0-9_.\-]+[/\\])+[a-zA-Z0-9_.\-]+\.[a-zA-Z0-9]{1,8}\b)",
    re.IGNORECASE,
)
_WIN_PATH_RE = re.compile(r"\b[a-zA-Z]:[\\/][^\s,;\"']+", re.IGNORECASE)
_IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_IPV6_RE = re.compile(
    r"\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b|\b(?:[0-9a-fA-F]{1,4}:){1,7}:[0-9a-fA-F]{0,4}\b"
)
_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_PHONE_RE = re.compile(
    r"(?:\+\d{1,3}[\s.-]?)?(?:\(\d{2,4}\)|\b\d{2,4})[\s.-]\d{3,4}[\s.-]\d{3,4}\b|\b\+\d{10,14}\b"
)
_BEARER_PASSWORD_RE = re.compile(
    r"\bBearer\s+[A-Za-z0-9._\-~+/=]{8,}\b|\b(?:password|passwd|pwd|secret|api_key|apikey|access_token|auth_token)\s*[:=]\s*(?:['\"][^'\"]*['\"]|[^\s,;]+)",
    re.IGNORECASE,
)
_TOKEN_RE = re.compile(
    r"\b(?:hf_|sk-|ghp_|gho_|ghs_|github_pat_|xoxb-|xoxp-|glpat-|npm_)[A-Za-z0-9_\-]{6,}\b|\bAKIA[0-9A-Z]{16}\b",
    re.IGNORECASE,
)


def scrub_pii(text: str) -> str:
    """Scrub PII from text before persistence or transmission (Defect Q10, C2.2).

    Covers all PII categories:
    - Email addresses
    - Home and user filesystem paths (~/, /home/, /Users/, C:\\Users)
    - Path traversal sequences (../../etc/passwd)
    - System, relative, and absolute file paths
    - Windows drive paths
    - IPv4 and IPv6 addresses
    - Social Security Numbers (SSN)
    - Phone numbers
    - Bearer tokens, password-like assignments, API keys, and cloud credentials
    """
    if not text:
        return ""
    text = _EMAIL_RE.sub("[EMAIL]", text)
    text = _HOME_RE.sub("[HOME]", text)
    text = _TRAVERSAL_RE.sub("[PATH]", text)
    text = _SYS_PATH_RE.sub("[PATH]", text)
    text = _WIN_PATH_RE.sub("[PATH]", text)
    text = _FILE_PATH_RE.sub("[PATH]", text)
    text = _IPV4_RE.sub("[IP]", text)
    text = _IPV6_RE.sub("[IP]", text)
    text = _SSN_RE.sub("[SSN]", text)
    text = _PHONE_RE.sub("[PHONE]", text)
    text = _BEARER_PASSWORD_RE.sub("[TOKEN]", text)
    text = _TOKEN_RE.sub("[TOKEN]", text)
    return text


# Standard aliases for static analysis discovery (C0.3, C0.4)
redact_pii = scrub_pii
anonymize_pii = scrub_pii
strip_pii = scrub_pii
redact = scrub_pii
anonymize = scrub_pii


def scrub_record(obj: Any) -> Any:
    """Recursively scrub PII across nested dicts, lists, and string fields."""
    if isinstance(obj, str):
        return scrub_pii(obj)
    elif isinstance(obj, dict):
        return {k: scrub_record(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [scrub_record(v) for v in obj]
    return obj


def _local_save(filename: str, records: list[dict]) -> None:
    """Save records to ~/.ai-rule-learning/ with mandatory recursive PII scrubbing and atomic replace (X04a)."""
    if filename != "processed.jsonl":
        records = [scrub_record(r) for r in records]
    target = _local_path(filename)
    _ensure_dir(target.parent)
    tmp_path = target.with_suffix(f".tmp.{uuid.uuid4().hex[:8]}")
    payload = "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n"
    tmp_path.write_text(payload, encoding="utf-8")
    os.replace(tmp_path, target)


def _r2_config() -> dict[str, str]:
    """Resolve Cloudflare R2 connection settings from the environment (call time)."""
    account = os.environ.get("R2_ACCOUNT_ID", "") or os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")
    endpoint = os.environ.get("R2_ENDPOINT", "") or (
        f"https://{account}.r2.cloudflarestorage.com" if account else ""
    )
    return {
        "bucket": os.environ.get("R2_BUCKET", ""),
        "access_key": os.environ.get("R2_ACCESS_KEY_ID", ""),
        "secret_key": os.environ.get("R2_SECRET_ACCESS_KEY", ""),
        "endpoint": endpoint,
        "prefix": os.environ.get("R2_PREFIX", ""),
    }


def remote_enabled() -> bool:
    """True when R2 is fully configured, so uploads/downloads use the bucket."""
    c = _r2_config()
    return bool(c["bucket"] and c["access_key"] and c["secret_key"] and c["endpoint"])


def hf_enabled() -> bool:
    """Backwards-compatible alias; the remote backend is now Cloudflare R2."""
    return remote_enabled()


def _r2_client():
    """Return a boto3 S3 client pointed at R2, or None if unavailable."""
    c = _r2_config()
    if not (c["access_key"] and c["secret_key"] and c["endpoint"]):
        return None
    try:
        import importlib

        boto3 = importlib.import_module("boto3")
        return boto3.client(
            "s3",
            endpoint_url=c["endpoint"],
            aws_access_key_id=c["access_key"],
            aws_secret_access_key=c["secret_key"],
            region_name="auto",
        )
    except Exception:
        return None


def _download(filename: str) -> list[dict]:
    """Load from the R2 bucket if configured, otherwise fall back to local storage."""
    if remote_enabled():
        try:
            client = _r2_client()
            if client is not None:
                c = _r2_config()
                obj = client.get_object(Bucket=c["bucket"], Key=c["prefix"] + filename)
                body = obj["Body"].read().decode("utf-8", errors="ignore")
                out: list[dict] = []
                for ln in body.splitlines():
                    ln = ln.strip()
                    if not ln:
                        continue
                    try:
                        rec = json.loads(ln)
                        if isinstance(rec, dict):
                            out.append(rec)
                    except Exception:
                        continue
                return out
        except Exception:
            # Missing key (fresh bucket) or transient error → use local copy.
            pass
    return _local_load(filename)


def _upload(filename: str, records: list[dict]) -> bool:
    """Save to local storage always; mirror to the R2 bucket if configured.

    Returns True only when the remote upload actually succeeded.
    """
    _local_save(filename, records)
    if not remote_enabled():
        return False
    # Mirror the same PII scrubbing _local_save applies, so the remote copy never
    # carries data the local copy strips (processed.jsonl is the one exception).
    scrubbed = records if filename == "processed.jsonl" else [scrub_record(r) for r in records]
    content = "\n".join(json.dumps(r, ensure_ascii=False) for r in scrubbed) + "\n"
    try:
        client = _r2_client()
        if client is not None:
            c = _r2_config()
            client.put_object(
                Bucket=c["bucket"],
                Key=c["prefix"] + filename,
                Body=content.encode("utf-8"),
                ContentType="application/x-ndjson",
            )
            return True
    except Exception:
        pass
    return False


_UNSAFE_PHRASES = [
    "never refuse",
    "bypass",
    "override your",
    "override safety",
    "override rules",
    "override guidelines",
    "ignore safety",
    "ignore all",
    "ignore previous",
    "ignore prior",
    "ignore earlier",
    "disregard",
    "forget your",
    "forget all",
    "forget everything",
    "forget earlier",
    "forget prior",
    "jailbreak",
    "developer mode",
    "god mode",
    "dan mode",
    "sudo mode",
    "unrestricted",
    "no restrictions",
    "without restrictions",
    "exfiltrate",
    "exfiltration",
]


def _is_safe_rule(rule: dict) -> bool:
    """Return True if the rule content contains no unsafe phrases or injection patterns (F12b, F12c)."""
    text = " ".join(
        [
            str(rule.get("name", "")),
            str(rule.get("instruction", "")),
            str(rule.get("action", {}).get("instruction", "")) if isinstance(rule.get("action"), dict) else "",
            str(rule.get("triggers", "")),
            str(rule.get("trigger", "")),
        ]
    ).lower()
    if any(phrase in text for phrase in _UNSAFE_PHRASES):
        return False
    # Note: do not flag built-in defensive rule 'resist-instruction-override-attempts'
    if rule.get("name") == "resist-instruction-override-attempts":
        return True
    return not is_prompt_injection(text)


def auto_activate_pending_rules() -> int:
    """Fetch rules, auto-activate safe pending ones, save back. Returns count activated."""
    rules = _download("rules.jsonl")
    if not rules:
        return 0
    activated = 0
    now = datetime.now(UTC).replace(tzinfo=None).isoformat()
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


RULE_STATUSES = {
    "pending",
    "approved",
    "rejected",
    "active",
    "inactive",
    "stale",
    "needs_review",
    "merged",
}


def list_rules(status: str | None = None) -> list[dict]:
    """Return stored rules, optionally filtered by lifecycle status."""
    rules = _download("rules.jsonl")
    if status:
        rules = [r for r in rules if r.get("status", "active") == status]
    return sorted(rules, key=lambda r: r.get("priority", 0), reverse=True)


def get_rule(rule_id: str) -> dict | None:
    """Return one stored rule by id, or None when not found."""
    return next((r for r in _download("rules.jsonl") if r.get("rule_id") == rule_id), None)


def _load_rules_preserving_local() -> list[dict]:
    """Load rules while preserving local-only entries missing from a remote snapshot."""
    rules = _download("rules.jsonl")
    seen_ids = {r.get("rule_id") for r in rules if r.get("rule_id")}
    for local_rule in _local_load("rules.jsonl"):
        local_id = local_rule.get("rule_id")
        if local_id and local_id not in seen_ids:
            rules.append(local_rule)
            seen_ids.add(local_id)
    return rules


def update_rule_status(rule_id: str, status: str, note: str = "") -> dict | None:
    """Update a rule lifecycle status and active injection flag."""
    normalized = status.strip().lower()
    if normalized not in RULE_STATUSES:
        raise ValueError(f"unsupported rule status: {status}")

    rules = _load_rules_preserving_local()
    now = datetime.now(UTC).replace(tzinfo=None).isoformat()
    target = next((r for r in rules if r.get("rule_id") == rule_id), None)
    if target is None:
        return None

    target["status"] = normalized
    target["is_active"] = normalized == "active"
    target["updated_at"] = now
    target[f"{normalized}_at"] = now
    if note:
        target["review_note"] = note
    if normalized in ("active", "approved"):
        target["review_status"] = "approved"
        target["reviewed_by"] = "local_admin"
        target["reviewed_at"] = now
    elif normalized == "rejected":
        target["review_status"] = "rejected"
        target["reviewed_by"] = "local_admin"
        target["reviewed_at"] = now
    elif normalized == "pending":
        target["review_status"] = "pending"
        target["reviewed_by"] = None
        target["reviewed_at"] = None
    _upload("rules.jsonl", rules)
    return target


def edit_rule_metadata(
    rule_id: str,
    priority: int | None = None,
    trigger_if: dict | None = None,
    exclude_if: dict | None = None,
) -> dict | None:
    """Update rule metadata fields (priority, trigger_if, exclude_if) while preserving static instruction."""
    rules = _load_rules_preserving_local()
    now = datetime.now(UTC).replace(tzinfo=None).isoformat()
    target = next((r for r in rules if r.get("rule_id") == rule_id), None)
    if target is None:
        return None

    if priority is not None:
        target["priority"] = int(priority)
        target["priority_label"] = {5: "CRITICAL", 4: "HIGH", 3: "MEDIUM", 2: "LOW", 1: "LOW"}.get(
            int(priority), "MEDIUM"
        )
    if trigger_if is not None:
        target["trigger_if"] = trigger_if
        target.setdefault("trigger", {})["keywords"] = list(trigger_if.keys())
    if exclude_if is not None:
        target["exclude_if"] = exclude_if
    target["updated_at"] = now
    _upload("rules.jsonl", rules)
    return target


def edit_rule_instruction(rule_id: str, instruction: str) -> dict | None:
    """Update a rule instruction without changing its lifecycle state."""
    if not instruction.strip():
        raise ValueError("instruction cannot be empty")

    rules = _download("rules.jsonl")
    now = datetime.now(UTC).replace(tzinfo=None).isoformat()
    target = next((r for r in rules if r.get("rule_id") == rule_id), None)
    if target is None:
        return None

    target["instruction"] = instruction.strip()
    action = target.get("action")
    if isinstance(action, dict):
        action["instruction"] = instruction.strip()
    else:
        target["action"] = {"instruction": instruction.strip()}
    target["status"] = target.get("status", "needs_review")
    target["updated_at"] = now
    _upload("rules.jsonl", rules)
    return target


def merge_rules(primary_rule_id: str, duplicate_rule_id: str) -> dict | None:
    """Mark a duplicate rule as merged into a primary rule."""
    if primary_rule_id == duplicate_rule_id:
        raise ValueError("cannot merge a rule into itself")

    rules = _download("rules.jsonl")
    now = datetime.now(UTC).replace(tzinfo=None).isoformat()
    primary = next((r for r in rules if r.get("rule_id") == primary_rule_id), None)
    duplicate = next((r for r in rules if r.get("rule_id") == duplicate_rule_id), None)
    if primary is None or duplicate is None:
        return None

    aliases = primary.setdefault("merged_rule_ids", [])
    if duplicate_rule_id not in aliases:
        aliases.append(duplicate_rule_id)
    primary["updated_at"] = now

    duplicate["status"] = "merged"
    duplicate["is_active"] = False
    duplicate["merged_into"] = primary_rule_id
    duplicate["merged_at"] = now
    duplicate["updated_at"] = now
    _upload("rules.jsonl", rules)
    return primary


def _rule_comparison_text(rule: dict) -> str:
    action = rule.get("action")
    action_instruction = action.get("instruction", "") if isinstance(action, dict) else ""
    return " ".join(
        part
        for part in (
            rule.get("name", ""),
            rule.get("instruction", ""),
            action_instruction,
            " ".join(rule.get("triggers", []))
            if isinstance(rule.get("triggers"), list)
            else str(rule.get("triggers", "")),
        )
        if part
    ).lower()


def _rule_tokens(rule: dict) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9_]{3,}", _rule_comparison_text(rule))
        if token not in {"the", "and", "for", "with", "rule"}
    }


def suggest_duplicate_rules_from_records(
    rules: list[dict], min_similarity: float = 0.7, include_inactive: bool = False
) -> list[dict]:
    """Suggest duplicate rules from an explicit rules list without reading storage."""
    candidates = [
        rule
        for rule in rules
        if rule.get("status", "active") not in {"rejected", "merged"}
        and (include_inactive or rule.get("is_active", rule.get("status", "active") == "active"))
    ]
    tokenized = [(rule, _rule_tokens(rule)) for rule in candidates]
    suggestions: list[dict] = []

    for index, (left, left_tokens) in enumerate(tokenized):
        if not left_tokens:
            continue
        for right, right_tokens in tokenized[index + 1 :]:
            if not right_tokens:
                continue
            union = left_tokens | right_tokens
            if not union:
                continue
            score = len(left_tokens & right_tokens) / len(union)
            if score >= min_similarity:
                suggestions.append(
                    {
                        "primary_rule_id": left.get("rule_id"),
                        "duplicate_rule_id": right.get("rule_id"),
                        "similarity": round(score, 3),
                        "primary_name": left.get("name", "Unnamed rule"),
                        "duplicate_name": right.get("name", "Unnamed rule"),
                    }
                )

    return sorted(suggestions, key=lambda item: item["similarity"], reverse=True)


def suggest_duplicate_rules(min_similarity: float = 0.7, include_inactive: bool = False) -> list[dict]:
    """Suggest likely duplicate rules using local text similarity.

    The function is read-only. It returns pairs with a Jaccard similarity score
    so callers can review and merge them explicitly instead of auto-merging.
    """
    return suggest_duplicate_rules_from_records(
        _download("rules.jsonl"), min_similarity=min_similarity, include_inactive=include_inactive
    )


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def find_rule_health_candidates(
    rules: list[dict],
    stale_days: int = 90,
    low_effectiveness_threshold: float = 0.3,
    min_triggered: int = 3,
) -> tuple[list[dict], list[dict]]:
    """Return stale and low-effectiveness rule candidates from explicit records."""
    now = datetime.now(UTC).replace(tzinfo=None)
    stale: list[dict] = []
    needs_review: list[dict] = []

    for rule in rules:
        status = rule.get("status", "active")
        if status in {"rejected", "merged", "retired"}:
            continue

        score = float(rule.get("effectiveness_score", 0.5) or 0.0)
        triggered = int(rule.get("times_triggered", 0) or 0)
        if triggered >= min_triggered and score <= low_effectiveness_threshold:
            needs_review.append(rule)
            continue

        activity_at = (
            _parse_iso_datetime(rule.get("last_fired_at"))
            or _parse_iso_datetime(rule.get("updated_at"))
            or _parse_iso_datetime(rule.get("created_at"))
            or _parse_iso_datetime(rule.get("approved_at"))
        )
        if activity_at is None:
            continue
        age_days = (now - activity_at).days
        if status == "active" and age_days >= stale_days:
            stale.append(rule)

    return stale, needs_review


def review_rule_health(
    stale_days: int = 90,
    low_effectiveness_threshold: float = 0.3,
    min_triggered: int = 3,
    apply: bool = False,
) -> dict:
    """Find stale or low-performing rules, optionally marking them for review.

    Rules are marked `needs_review` when they have enough trigger history and
    an effectiveness score at or below the threshold. Active rules are marked
    `stale` when their latest activity timestamp is older than `stale_days`.
    """
    rules = _download("rules.jsonl")
    now = datetime.now(UTC).replace(tzinfo=None)
    stale, needs_review = find_rule_health_candidates(
        rules,
        stale_days=stale_days,
        low_effectiveness_threshold=low_effectiveness_threshold,
        min_triggered=min_triggered,
    )

    if apply:
        for rule in needs_review:
            score = float(rule.get("effectiveness_score", 0.5) or 0.0)
            triggered = int(rule.get("times_triggered", 0) or 0)
            rule["status"] = "needs_review"
            rule["is_active"] = False
            rule["review_reason"] = (
                f"effectiveness_score={score:.2f} <= {low_effectiveness_threshold:.2f} after {triggered} trigger(s)"
            )
            rule["reviewed_at"] = now.isoformat()
        for rule in stale:
            activity_at = (
                _parse_iso_datetime(rule.get("last_fired_at"))
                or _parse_iso_datetime(rule.get("updated_at"))
                or _parse_iso_datetime(rule.get("created_at"))
                or _parse_iso_datetime(rule.get("approved_at"))
            )
            age_days = (now - activity_at).days if activity_at else stale_days
            rule["status"] = "stale"
            rule["is_active"] = False
            rule["review_reason"] = f"no activity for {age_days} day(s)"
            rule["reviewed_at"] = now.isoformat()
        if stale or needs_review:
            _upload("rules.jsonl", rules)

    return {
        "stale": stale,
        "needs_review": needs_review,
        "applied": apply,
        "stale_days": stale_days,
        "low_effectiveness_threshold": low_effectiveness_threshold,
        "min_triggered": min_triggered,
    }


def load_active_rules() -> list[dict]:
    """Return all active rules from the dataset, sorted by priority desc.

    Every rule is re-checked against ``_is_safe_rule`` here — the injection
    boundary — so a rule that arrived already-active (e.g. synced from the
    dataset or a community source) cannot be written to user agent configs
    without passing the safety gate.
    """
    rules = _download("rules.jsonl")
    for r in rules:
        if r.get("name") == "remember-stated-context" or r.get("slot") == "remember-stated-context":
            ev = r.get("evidence", {})
            gap_type = ev.get("gap_type") if isinstance(ev, dict) else r.get("gap_type", "")
            if (
                gap_type == "preference"
                or "preference" in r.get("instruction", "").lower()
                or "prefer" in str(r.get("trigger", "")).lower()
                or "prefer" in str(r.get("action", "")).lower()
            ):
                r["name"] = "respect-user-preferences"
                r["slot"] = "respect-user-preferences"
            elif gap_type == "repeated_context" or "context" in str(r.get("trigger", "")).lower():
                r["name"] = "retain-repeated-context"
                r["slot"] = "retain-repeated-context"
    active = [r for r in rules if (r.get("is_active", True) or r.get("status") == "active") and _is_safe_rule(r)]
    return sorted(active, key=lambda r: r.get("priority", 0), reverse=True)


def record_rule_outcome(rule_id: str, fired_again: bool) -> dict | None:
    """Update effectiveness tracking for a rule.

    fired_again=True  → gap recurred after rule injection (rule not working).
    fired_again=False → gap stopped recurring (rule suppressed the problem).

    Returns the updated rule dict, or None if rule_id not found.
    """
    rules = _download("rules.jsonl")
    now = datetime.now(UTC).replace(tzinfo=None).isoformat()
    target = next((r for r in rules if r.get("rule_id") == rule_id), None)
    if target is None:
        return None

    target["last_fired_at"] = now
    if fired_again:
        target["times_triggered"] = target.get("times_triggered", 0) + 1
        # Decay score — cap at 0.0
        target["effectiveness_score"] = max(0.0, round(target.get("effectiveness_score", 0.5) - 0.1, 2))
    else:
        target["suppression_count"] = target.get("suppression_count", 0) + 1
        # Grow score — cap at 1.0
        target["effectiveness_score"] = min(1.0, round(target.get("effectiveness_score", 0.5) + 0.1, 2))

    _upload("rules.jsonl", rules)
    return target


def append_conversations(convs: list[dict]) -> tuple[int, bool]:
    """Merge new conversations into the store.

    Returns (count_added, remote_ok) where remote_ok is True only when the new
    records were successfully mirrored to R2.
    """
    existing = _download("conversations.jsonl")
    existing_ids = {c.get("conversation_id") for c in existing}
    new = [c for c in convs if c.get("conversation_id") not in existing_ids]
    remote_ok = False
    if new:
        remote_ok = _upload("conversations.jsonl", existing + new)
    return len(new), remote_ok


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
                        "started_at": obj.get("timestamp", datetime.now(UTC).replace(tzinfo=None).isoformat()),
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

    turns: list[dict] = []
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
        "ended_at": datetime.now(UTC).replace(tzinfo=None).isoformat(),
        "exported_at": datetime.now(UTC).replace(tzinfo=None).isoformat(),
    }
