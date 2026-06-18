"""AI Rule Learning MCP server — personal and business tiers.

Works with any AI provider: Claude, ChatGPT, Cursor, Windsurf, Copilot, etc.

## Personal tier (free)
  Analyses YOUR sessions → generates YOUR personal rules → injects them back.
  Optionally contributes anonymised gap patterns to the community pool.

## Business tier (licence required)
  Same as personal PLUS access to aggregated community rules from all opted-in
  users — richer, broader ruleset for teams and organisations.
  Contact: info@tococolors.com

## Environment variables
  HF_TOKEN        Your Hugging Face write token (required)
  ARL_DATASET     Your personal HF dataset, e.g. "yourname/AI_Rule_Learning"
  ARL_TIER        "personal" (default) or "business"
  ARL_SESSIONS    Comma-separated paths to session directories or files.
                  Defaults to ~/.claude/projects (Claude Code).
                  Also accepts ChatGPT export directories, generic JSONL dirs.
  ARL_CONTRIBUTE  "true" to opt in to anonymised community contribution (default: false)
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from .community import contribute_gaps, fetch_community_rules
from .providers import parse_any
from .store import append_conversations, load_active_rules

_TIER = os.environ.get("ARL_TIER", "personal").lower()
_CONTRIBUTE = os.environ.get("ARL_CONTRIBUTE", "false").lower() == "true"

_DEFAULT_SESSIONS = [Path.home() / ".claude" / "projects"]
_SESSION_PATHS: list[Path] = []

_raw = os.environ.get("ARL_SESSIONS", "")
if _raw:
    _SESSION_PATHS = [Path(p.strip()) for p in _raw.split(",") if p.strip()]
else:
    _SESSION_PATHS = _DEFAULT_SESSIONS

app = Server("ai-rule-learning")


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

@app.list_tools()
async def list_tools() -> list[Tool]:
    tools = [
        Tool(
            name="get_guardrail_rules",
            description=(
                "Return your personal AI guardrail rules as a formatted block ready "
                "to inject into your system prompt. Works with any AI provider. "
                "Call at the start of important sessions."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "include_community": {
                        "type": "boolean",
                        "description": "Also include community rules (business tier only)",
                    }
                },
                "required": [],
            },
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

    if _TIER == "business":
        tools.append(Tool(
            name="get_community_rules",
            description=(
                "[Business tier] Fetch aggregated rules derived from all opted-in users. "
                "Returns a richer ruleset built from collective conversation patterns."
            ),
            inputSchema={"type": "object", "properties": {}, "required": []},
        ))

    return tools


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "get_guardrail_rules":
        return await _get_guardrail_rules(arguments.get("include_community", False))
    if name == "sync_sessions":
        paths = [Path(p) for p in arguments.get("paths", [])] or None
        contribute = arguments.get("contribute", _CONTRIBUTE)
        return await _sync_sessions(paths=paths, contribute=contribute)
    if name == "list_providers":
        return await _list_providers()
    if name == "get_community_rules":
        return await _get_community_rules()
    return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def _get_guardrail_rules(include_community: bool = False) -> list[TextContent]:
    personal_rules = load_active_rules()

    community_rules: list[dict] = []
    if include_community and _TIER == "business":
        community_rules = fetch_community_rules()

    if not personal_rules and not community_rules:
        return [TextContent(
            type="text",
            text="No guardrail rules yet. Run sync_sessions first, then trigger analysis on your Space.",
        )]

    lines = ["## Your AI Guardrail Rules\n"]

    if personal_rules:
        lines.append(f"### Personal rules ({len(personal_rules)})\n")
        for i, rule in enumerate(personal_rules, 1):
            lines.extend(_format_rule(i, rule))

    if community_rules:
        lines.append(f"\n### Community rules ({len(community_rules)}) — Business tier\n")
        for i, rule in enumerate(community_rules, 1):
            lines.extend(_format_rule(i, rule))

    return [TextContent(type="text", text="\n".join(lines))]


async def _sync_sessions(paths: list[Path] | None = None, contribute: bool = False) -> list[TextContent]:
    log: list[str] = []

    scan_paths = paths or _SESSION_PATHS

    # Collect all session files
    session_files: list[Path] = []
    for sp in scan_paths:
        sp = Path(sp)
        if not sp.exists():
            log.append(f"⚠️  Path not found: {sp}")
            continue
        if sp.is_file():
            session_files.append(sp)
        elif sp.is_dir():
            # Claude Code: subdirs with *.jsonl
            for sub in sp.iterdir():
                if sub.is_dir():
                    for f in sub.glob("*.jsonl"):
                        if ".ccr-tip" not in f.name:
                            session_files.append(f)
            # Direct *.jsonl or conversations.json in dir
            for f in sp.glob("*.jsonl"):
                if ".ccr-tip" not in f.name:
                    session_files.append(f)
            for f in sp.glob("conversations.json"):
                session_files.append(f)

    log.append(f"📂 Found {len(session_files)} session file(s) across {len(scan_paths)} path(s)")

    # Parse all files
    all_conversations: list[dict] = []
    for path in session_files:
        convs = parse_any(path)
        all_conversations.extend(convs)

    log.append(f"✅ Parsed {len(all_conversations)} valid conversation(s)")

    if not all_conversations:
        log.append("ℹ️  Nothing to upload.")
        return [TextContent(type="text", text="\n".join(log))]

    # Upload
    added = append_conversations(all_conversations)
    log.append(f"⬆️  Uploaded {added} new conversation(s) to your dataset")

    # Community contribution (opt-in, anonymised only)
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

    # Pull back latest rules
    rules = load_active_rules()
    log.append(f"📥 Pulled {len(rules)} active rule(s) from your dataset")

    log.append(
        "\n💡 Open your Space → Analysis tab → 🔁 Force Re-analyze All "
        "to generate new rules from uploaded conversations."
    )

    return [TextContent(type="text", text="\n".join(log))]


async def _list_providers() -> list[TextContent]:
    lines = [f"**Tier:** {_TIER.title()}", f"**Community opt-in:** {_CONTRIBUTE}", ""]
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
    if _TIER == "business":
        lines.append("**Community dataset:** vooom/AI_Rule_Learning_Community ✓")

    return [TextContent(type="text", text="\n".join(lines))]


async def _get_community_rules() -> list[TextContent]:
    if _TIER != "business":
        return [TextContent(
            type="text",
            text="Community rules are available on the business tier only. Contact info@tococolors.com.",
        )]
    rules = fetch_community_rules()
    if not rules:
        return [TextContent(type="text", text="No community rules available yet.")]
    lines = [f"## Community Rules ({len(rules)} rules)\n"]
    for i, rule in enumerate(rules, 1):
        lines.extend(_format_rule(i, rule))
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


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    async def _run():
        async with stdio_server() as streams:
            await app.run(streams[0], streams[1], app.create_initialization_options())

    asyncio.run(_run())


if __name__ == "__main__":
    main()
