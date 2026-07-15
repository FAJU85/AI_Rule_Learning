"""Privacy-preserving, opt-in product metrics.

The metrics subsystem is intentionally local-first and disabled by default.
It records only coarse feature usage events (for example: command/tool name,
success/failure category, Python version bucket, and OS family). It never stores
raw prompts, rule text, memory content, file paths, usernames, repo names, host
names, or agent config content.
"""

from __future__ import annotations

import json
import os
import platform
from collections import Counter
from datetime import UTC
from datetime import datetime
from importlib import metadata
from typing import Any

from .store import _local_load
from .store import _local_path
from .store import _local_save

METRICS_EVENTS_FILE = "metrics.jsonl"
METRICS_SETTINGS_FILE = "metrics_settings.jsonl"
METRICS_ENV_VAR = "ARL_METRICS"
_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}
_ALLOWED_EXTRA_KEYS = {"command", "tool", "status", "category", "source"}


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _package_version() -> str:
    try:
        return metadata.version("ai-rule-learning-mcp")
    except metadata.PackageNotFoundError:
        return "unknown"


def _env_opt_in() -> bool | None:
    raw = os.environ.get(METRICS_ENV_VAR)
    if raw is None:
        return None
    normalized = raw.strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    return None


def _settings() -> dict[str, Any]:
    rows = _local_load(METRICS_SETTINGS_FILE)
    if not rows:
        return {"enabled": False}
    return rows[-1]


def metrics_enabled() -> bool:
    """Return True only when the user explicitly opted in."""
    env_value = _env_opt_in()
    if env_value is not None:
        return env_value
    return bool(_settings().get("enabled", False))


def set_metrics_enabled(enabled: bool) -> dict[str, Any]:
    """Persist the opt-in setting locally."""
    settings = {
        "enabled": bool(enabled),
        "updated_at": _now(),
        "privacy": "anonymous aggregate usage only; no prompts, rule text, memory, paths, usernames, or hostnames",
    }
    _local_save(METRICS_SETTINGS_FILE, [settings])
    return settings


def metrics_status() -> dict[str, Any]:
    """Return current opt-in state and local metrics file information."""
    env_value = _env_opt_in()
    events_path = _local_path(METRICS_EVENTS_FILE)
    return {
        "enabled": metrics_enabled(),
        "source": "environment" if env_value is not None else "local_settings",
        "env_var": METRICS_ENV_VAR,
        "event_count": len(_local_load(METRICS_EVENTS_FILE)),
        "events_path": str(events_path),
        "endpoint_configured": bool(os.environ.get("ARL_METRICS_ENDPOINT")),
    }


def _safe_text(value: Any, max_len: int = 80) -> str:
    """Normalize a metric label while preventing accidental content capture."""
    if not isinstance(value, str):
        return "unknown"
    safe = "".join(ch for ch in value if ch.isalnum() or ch in {"_", "-", ".", ":"}).strip("._-:")
    return safe[:max_len] or "unknown"


def record_metric_event(
    event: str,
    *,
    source: str = "cli",
    success: bool = True,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Record one local anonymous usage event when metrics are enabled.

    Only a short allow-list of metadata labels is persisted. Values are reduced
    to safe labels so callers cannot accidentally store user content.
    """
    if not metrics_enabled():
        return None

    extras = {
        key: _safe_text(value)
        for key, value in (metadata or {}).items()
        if key in _ALLOWED_EXTRA_KEYS and isinstance(value, str)
    }
    row = {
        "event": _safe_text(event),
        "source": _safe_text(source),
        "success": bool(success),
        "created_at": _now(),
        "package_version": _package_version(),
        "python": f"{platform.python_version_tuple()[0]}.{platform.python_version_tuple()[1]}",
        "os": _safe_text(platform.system().lower()),
        **extras,
    }
    rows = _local_load(METRICS_EVENTS_FILE)
    rows.append(row)
    _local_save(METRICS_EVENTS_FILE, rows)
    return row


def build_metrics_payload(limit: int = 1000) -> dict[str, Any]:
    """Build the exact aggregate payload that may be shared if the owner opts in."""
    rows = _local_load(METRICS_EVENTS_FILE)[-limit:]
    events = Counter(_safe_text(row.get("event")) for row in rows)
    commands = Counter(_safe_text(row.get("command")) for row in rows if row.get("command"))
    tools = Counter(_safe_text(row.get("tool")) for row in rows if row.get("tool"))
    statuses = Counter("success" if row.get("success", False) else "failure" for row in rows)
    versions = Counter(_safe_text(row.get("package_version")) for row in rows)
    python_versions = Counter(_safe_text(row.get("python")) for row in rows)
    os_families = Counter(_safe_text(row.get("os")) for row in rows)

    return {
        "schema_version": "1.0",
        "generated_at": _now(),
        "metrics_enabled": metrics_enabled(),
        "event_count": len(rows),
        "events": dict(sorted(events.items())),
        "commands": dict(sorted(commands.items())),
        "tools": dict(sorted(tools.items())),
        "outcomes": dict(sorted(statuses.items())),
        "package_versions": dict(sorted(versions.items())),
        "python_versions": dict(sorted(python_versions.items())),
        "os_families": dict(sorted(os_families.items())),
        "privacy_notice": "Aggregate labels only; no prompts, rule text, memory, paths, usernames, repo names, or hostnames.",
    }


def preview_metrics_payload(limit: int = 1000) -> str:
    """Return a formatted JSON preview of the aggregate metrics payload."""
    return json.dumps(build_metrics_payload(limit=limit), indent=2, sort_keys=True)
