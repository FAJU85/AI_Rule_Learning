"""Gradio-free introspection of the ai-rule-learning MCP server internals.

Pulls live state from the MCP ``Server`` object so the dashboard can surface
every component — tools, resources, prompts, capabilities, runtime — with full
fidelity and zero hidden detail. Safe to import without gradio; degrades
gracefully (returns an ``errors`` entry) if the MCP package is unavailable.
"""

from __future__ import annotations

import asyncio
import json
import os
import platform
import time
from typing import Any

# Process start time — used to report dashboard/introspection uptime.
_START = time.time()


def _run(coro: Any) -> Any:
    """Run an async coroutine from sync code on a private event loop."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _jsonable(obj: Any) -> Any:
    """Coerce arbitrary objects into JSON-serialisable form (best effort)."""
    return json.loads(json.dumps(obj, default=str))


def _human_duration(seconds: float) -> str:
    """Format a duration in seconds as a compact human string (e.g. ``1h 3m 9s``)."""
    seconds = int(seconds)
    d, rem = divmod(seconds, 86400)
    h, rem = divmod(rem, 3600)
    m, s = divmod(rem, 60)
    parts = []
    if d:
        parts.append(f"{d}d")
    if h:
        parts.append(f"{h}h")
    if m:
        parts.append(f"{m}m")
    parts.append(f"{s}s")
    return " ".join(parts)


def _runtime(loaded: bool) -> dict[str, Any]:
    """Return runtime/environment facts (uptime, pid, python, transports, SDK version)."""
    info: dict[str, Any] = {
        "introspector_uptime_seconds": round(time.time() - _START, 1),
        "introspector_uptime": _human_duration(time.time() - _START),
        "pid": os.getpid(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "transports": ["stdio"],
        "mcp_package_loaded": loaded,
        # The dashboard introspects the server definition out-of-band; it is not
        # itself the live stdio session host, so per-connection session counts
        # are not observable from here.
        "active_sessions": "n/a (dashboard introspects server definition out-of-band)",
    }
    try:
        from importlib.metadata import version

        info["mcp_sdk_version"] = version("mcp")
    except Exception:
        info["mcp_sdk_version"] = "unknown"
    return info


def collect_mcp_internals() -> dict[str, Any]:
    """Return a structured snapshot of every introspectable MCP component."""
    out: dict[str, Any] = {
        "server": {},
        "tools": [],
        "resources": [],
        "prompts": [],
        "runtime": {},
        "errors": [],
        "collected_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
    }

    try:
        from ai_rule_learning_mcp import __version__ as pkg_version
        from ai_rule_learning_mcp import server as smod
    except Exception as e:  # package not installed / importable
        out["errors"].append(f"MCP package not importable: {e}")
        out["runtime"] = _runtime(loaded=False)
        return out

    app = smod.app

    # ── Server identity + capabilities ──────────────────────────────────────
    try:
        init = app.create_initialization_options()
        caps = init.capabilities.model_dump(exclude_none=True)
        # The package version is authoritative. ``server_version`` from an
        # out-of-band create_initialization_options() falls back to the SDK
        # version (the server sets it at runtime in main()), so expose that
        # separately rather than presenting it as the server's version.
        out["server"] = {
            "name": app.name,
            "version": pkg_version,
            "package_version": pkg_version,
            "init_server_version": getattr(init, "server_version", None),
            "instructions": getattr(init, "instructions", None),
            "capabilities": _jsonable(caps),
            "registered_request_handlers": sorted(t.__name__ for t in app.request_handlers),
        }
    except Exception as e:
        out["errors"].append(f"server info: {e}")

    # ── Tools ───────────────────────────────────────────────────────────────
    try:
        for t in _run(smod.list_tools()):
            schema = _jsonable(t.inputSchema) if getattr(t, "inputSchema", None) else {}
            out_schema = getattr(t, "outputSchema", None)
            out["tools"].append(
                {
                    "name": t.name,
                    "description": (t.description or "").strip(),
                    "input_schema": schema,
                    "output_schema": _jsonable(out_schema) if out_schema else None,
                    "status": "registered",
                }
            )
    except Exception as e:
        out["errors"].append(f"tools: {e}")

    # ── Resources (only if the server registered a handler) ─────────────────
    res_fn = getattr(smod, "list_resources", None)
    if callable(res_fn):
        try:
            for r in _run(res_fn()):
                out["resources"].append(
                    {
                        "uri": str(getattr(r, "uri", "")),
                        "name": getattr(r, "name", None),
                        "mime_type": getattr(r, "mimeType", None),
                        "size": getattr(r, "size", None),
                        "description": getattr(r, "description", None),
                    }
                )
        except Exception as e:
            out["errors"].append(f"resources: {e}")

    # ── Prompts (only if the server registered a handler) ───────────────────
    prompt_fn = getattr(smod, "list_prompts", None)
    if callable(prompt_fn):
        try:
            for p in _run(prompt_fn()):
                out["prompts"].append(
                    {
                        "name": getattr(p, "name", None),
                        "description": getattr(p, "description", None),
                        "arguments": _jsonable([a.model_dump() for a in (getattr(p, "arguments", None) or [])]),
                    }
                )
        except Exception as e:
            out["errors"].append(f"prompts: {e}")

    out["runtime"] = _runtime(loaded=True)
    return out


# ── Gradio-free formatters (return plain rows/strings for the dashboard) ─────


def _matches(query: str, *fields: Any) -> bool:
    """True if ``query`` (case-insensitive) is empty or a substring of any field."""
    q = (query or "").lower().strip()
    if not q:
        return True
    return any(q in str(f).lower() for f in fields if f is not None)


def tool_rows(data: dict[str, Any], query: str = "") -> list[list[str]]:
    """Build dataframe rows (name, description, inputs, required, status) for tools."""
    rows = []
    for t in data.get("tools", []):
        if not _matches(query, t.get("name"), t.get("description")):
            continue
        schema = t.get("input_schema") or {}
        props = list((schema.get("properties") or {}).keys())
        required = schema.get("required") or []
        rows.append(
            [
                t.get("name", ""),
                (t.get("description") or "")[:140],
                ", ".join(props) if props else "—",
                ", ".join(required) if required else "—",
                t.get("status", ""),
            ]
        )
    return rows


def resource_rows(data: dict[str, Any], query: str = "") -> list[list[str]]:
    """Build dataframe rows (uri, name, mime type, size) for resources."""
    rows = []
    for r in data.get("resources", []):
        if not _matches(query, r.get("uri"), r.get("name"), r.get("description")):
            continue
        rows.append(
            [
                str(r.get("uri", "")),
                str(r.get("name") or "—"),
                str(r.get("mime_type") or "—"),
                str(r.get("size") if r.get("size") is not None else "—"),
            ]
        )
    return rows


def prompt_rows(data: dict[str, Any], query: str = "") -> list[list[str]]:
    """Build dataframe rows (name, description, arguments) for prompt templates."""
    rows = []
    for p in data.get("prompts", []):
        if not _matches(query, p.get("name"), p.get("description")):
            continue
        args = ", ".join(a.get("name", "") for a in (p.get("arguments") or [])) or "—"
        rows.append([str(p.get("name") or "—"), str(p.get("description") or "—"), args])
    return rows


def server_markdown(data: dict[str, Any]) -> str:
    """Render a markdown summary of server identity, capabilities and runtime."""
    s = data.get("server", {})
    rt = data.get("runtime", {})
    if not s:
        errs = "; ".join(data.get("errors", [])) or "unknown"
        return f"### ⚠️ MCP server not introspectable\n\n`{errs}`"
    caps = s.get("capabilities", {})
    cap_names = ", ".join(k for k, v in caps.items() if v) or "—"
    lines = [
        f"### 🔌 `{s.get('name')}`  ·  v`{s.get('version')}`",
        "",
        f"- **Package version:** `{s.get('package_version')}`  "
        f"(SDK `{rt.get('mcp_sdk_version', '?')}`)",
        f"- **Transports:** {', '.join(rt.get('transports', [])) or '—'}",
        f"- **Capabilities advertised:** {cap_names}",
        f"- **Registered handlers:** {', '.join(s.get('registered_request_handlers', [])) or '—'}",
        f"- **Counts:** {len(data.get('tools', []))} tools · "
        f"{len(data.get('resources', []))} resources · {len(data.get('prompts', []))} prompts",
        f"- **Introspector uptime:** {rt.get('introspector_uptime', '?')}  ·  "
        f"PID `{rt.get('pid', '?')}`  ·  Python `{rt.get('python', '?')}`",
        f"- **Active sessions:** {rt.get('active_sessions', '—')}",
        f"- **Collected at:** {data.get('collected_at', '—')}",
    ]
    if data.get("errors"):
        lines.append("")
        lines.append("**Errors:** " + "; ".join(data["errors"]))
    return "\n".join(lines)


def empty_note(kind: str, count: int) -> str:
    """Return an italic 'none registered' note when ``count`` is zero, else ''."""
    if count:
        return ""
    return f"_No {kind} registered by this MCP server._"
