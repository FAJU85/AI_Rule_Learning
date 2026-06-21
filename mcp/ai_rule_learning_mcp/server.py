"""AI Rule Learning MCP server — personal tier (free, open source).

Works with any AI provider: Claude, ChatGPT, Cursor, Windsurf, Copilot, etc.

Analyses YOUR sessions → generates YOUR personalised rules → injects them back.
Optionally contributes anonymised gap patterns to the community pool.

Environment variables (set in your MCP config):
  HF_TOKEN        Your Hugging Face write token (required)
  ARL_DATASET     Your personal HF dataset, e.g. "yourname/AI_Rule_Learning"
  ARL_SESSIONS    Comma-separated paths to session directories or files.
                  Defaults to ~/.claude/projects (Claude Code).
                  Also accepts ChatGPT export directories, generic JSONL dirs.
  ARL_CONTRIBUTE  "true" to opt in to anonymised community contribution (default: false)
"""

from __future__ import annotations

import asyncio
import hashlib
import os
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent
from mcp.types import Tool

from .community import contribute_gaps
from .providers import parse_any
from .store import append_conversations
from .store import auto_activate_pending_rules
from .store import load_active_rules

_CONTRIBUTE = os.environ.get("ARL_CONTRIBUTE", "false").lower() == "true"

_SESSION_PATHS: list[Path] = []
_raw = os.environ.get("ARL_SESSIONS", "")
if _raw:
    _SESSION_PATHS = [Path(p.strip()) for p in _raw.split(",") if p.strip()]
else:
    _SESSION_PATHS = [Path.home() / ".claude" / "projects"]

app = Server("ai-rule-learning")


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="get_guardrail_rules",
            description=(
                "Return your personal AI guardrail rules as a formatted block ready "
                "to inject into your system prompt. Works with any AI provider. "
                "Call at the start of important sessions."
            ),
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="sync_sessions",
            description=(
                "Scan your local AI session history, scrub PII, upload new conversations "
                "to your private HF dataset, and pull back the latest generated rules. "
                "Run weekly or after significant work to keep your rules current. "
                "Supports Claude Code, ChatGPT exports, and generic JSONL session files."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "contribute": {
                        "type": "boolean",
                        "description": (
                            "Opt in to contribute anonymised gap patterns (NOT raw text) "
                            "to the community pool. Improves rules for all users."
                        ),
                    },
                    "paths": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Optional override: paths to session directories or files. "
                            "Supports Claude Code dirs, ChatGPT conversations.json, "
                            "or any directory of JSONL files."
                        ),
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="list_providers",
            description="Show which session sources are configured and how many files are found.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "get_guardrail_rules":
        return await _get_guardrail_rules()
    if name == "sync_sessions":
        paths = [Path(p) for p in arguments.get("paths", [])] or None
        contribute = arguments.get("contribute", _CONTRIBUTE)
        return await _sync_sessions(paths=paths, contribute=contribute)
    if name == "list_providers":
        return await _list_providers()
    return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def _get_guardrail_rules() -> list[TextContent]:
    rules = load_active_rules()
    if not rules:
        return [
            TextContent(
                type="text",
                text="No guardrail rules yet. Run sync_sessions first, then trigger analysis on your Space.",
            )
        ]
    lines = ["## Your AI Guardrail Rules\n"]
    for i, rule in enumerate(rules, 1):
        lines.extend(_format_rule(i, rule))
    return [TextContent(type="text", text="\n".join(lines))]


async def _sync_sessions(paths: list[Path] | None = None, contribute: bool = False) -> list[TextContent]:
    log: list[str] = []

    scan_paths = paths or _SESSION_PATHS
    session_files: list[Path] = []

    for sp in scan_paths:
        sp = Path(sp)
        if not sp.exists():
            log.append(f"⚠️  Path not found: {sp}")
            continue
        if sp.is_file():
            session_files.append(sp)
        elif sp.is_dir():
            for sub in sp.iterdir():
                if sub.is_dir():
                    for f in sub.glob("*.jsonl"):
                        if ".ccr-tip" not in f.name:
                            session_files.append(f)
            for f in sp.glob("*.jsonl"):
                if ".ccr-tip" not in f.name:
                    session_files.append(f)
            for f in sp.glob("conversations.json"):
                session_files.append(f)

    log.append(f"📂 Found {len(session_files)} session file(s) across {len(scan_paths)} path(s)")

    all_conversations: list[dict] = []
    for path in session_files:
        convs = parse_any(path)
        all_conversations.extend(convs)

    log.append(f"✅ Parsed {len(all_conversations)} valid conversation(s)")

    if not all_conversations:
        log.append("ℹ️  Nothing to upload.")
        return [TextContent(type="text", text="\n".join(log))]

    added = append_conversations(all_conversations)
    log.append(f"⬆️  Uploaded {added} new conversation(s) to your dataset")

    if contribute:
        contributed = 0
        for conv in all_conversations:
            gaps_by_type: dict[str, list] = {}
            for turn in conv.get("turns", []):
                for gap in turn.get("gaps_detected", []):
                    gtype = gap.get("type", "unknown")
                    gaps_by_type.setdefault(gtype, []).append(gap)
            if gaps_by_type:
                h = hashlib.sha256(conv["session_id"].encode()).hexdigest()
                if contribute_gaps(gaps_by_type, h):
                    contributed += 1
        log.append(f"🤝 Contributed anonymised patterns from {contributed} session(s) to community pool")

    activated = auto_activate_pending_rules()
    if activated:
        log.append(f"✅ Auto-activated {activated} safe pending rule(s)")

    rules = load_active_rules()
    log.append(f"📥 Pulled {len(rules)} active rule(s) from your dataset")

    return [TextContent(type="text", text="\n".join(log))]


async def _list_providers() -> list[TextContent]:
    lines = [f"**Community opt-in:** {_CONTRIBUTE}", ""]
    lines.append("**Session paths:**")
    for sp in _SESSION_PATHS:
        sp = Path(sp)
        if not sp.exists():
            lines.append(f"  ❌ {sp} — not found")
            continue
        count = sum(1 for _ in sp.rglob("*.jsonl")) + sum(1 for _ in sp.rglob("conversations.json"))
        lines.append(f"  ✅ {sp} — {count} file(s)")
    lines.append("")
    lines.append("**Supported formats:** Claude Code (.jsonl), ChatGPT export (conversations.json), Generic JSONL")
    return [TextContent(type="text", text="\n".join(lines))]


def _format_rule(i: int, rule: dict) -> list[str]:
    priority = rule.get("priority_label", "MEDIUM")
    name = rule.get("name", rule.get("rule_id", f"Rule {i}"))
    instruction = rule.get("action", {}).get("instruction") or rule.get("instruction", "")
    triggers = rule.get("trigger", {}).get("keywords") or rule.get("triggers", [])
    out = [f"**Rule {i}: {name}** [{priority}]"]
    if instruction:
        out.append(f"→ {instruction}")
    if triggers:
        out.append(f"   Triggers on: {', '.join(str(t) for t in triggers[:6])}")
    out.append("")
    return out


def main() -> None:
    async def _run():
        async with stdio_server() as streams:
            await app.run(streams[0], streams[1], app.create_initialization_options())

    asyncio.run(_run())


if __name__ == "__main__":
    main()
