"""AI Rule Learning MCP server.

Exposes two tools to Claude:
  - get_guardrail_rules   → returns active rules as a formatted system prompt block
  - sync_sessions         → exports new local sessions to HF dataset, triggers analysis

Environment variables (set in your MCP config):
  HF_TOKEN     Your Hugging Face write token
  ARL_DATASET  Your HF dataset repo ID, e.g. "yourname/AI_Rule_Learning"
  ARL_CLAUDE_DIR  Path to ~/.claude/projects (defaults to auto-detect)
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from .store import append_conversations, load_active_rules, parse_claude_session

_CLAUDE_DIR = Path(os.environ.get("ARL_CLAUDE_DIR", Path.home() / ".claude" / "projects"))

app = Server("ai-rule-learning")


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="get_guardrail_rules",
            description=(
                "Return your personal AI guardrail rules as a formatted system prompt block. "
                "Call this at the start of important sessions to inject your learned rules."
            ),
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="sync_sessions",
            description=(
                "Export new local Claude Code sessions to your HF dataset and pull back "
                "the latest rules. Run this periodically (e.g. weekly) to keep your rules current."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "trigger_analysis": {
                        "type": "boolean",
                        "description": "If true, trigger gap analysis on the Space after upload (default: true)",
                    }
                },
                "required": [],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "get_guardrail_rules":
        return await _get_guardrail_rules()
    if name == "sync_sessions":
        trigger = arguments.get("trigger_analysis", True)
        return await _sync_sessions(trigger_analysis=trigger)
    return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def _get_guardrail_rules() -> list[TextContent]:
    rules = load_active_rules()
    if not rules:
        return [TextContent(type="text", text="No guardrail rules found. Run sync_sessions first.")]

    lines = ["## Your AI Guardrail Rules\n"]
    for i, rule in enumerate(rules, 1):
        priority = rule.get("priority_label", "MEDIUM")
        name = rule.get("name", rule.get("rule_id", f"Rule {i}"))
        instruction = (
            rule.get("action", {}).get("instruction")
            or rule.get("instruction", "")
        )
        triggers = (
            rule.get("trigger", {}).get("keywords")
            or rule.get("triggers", [])
        )
        lines.append(f"**Rule {i}: {name}** [{priority}]")
        if instruction:
            lines.append(f"→ {instruction}")
        if triggers:
            lines.append(f"   Triggers on: {', '.join(triggers[:6])}")
        lines.append("")

    return [TextContent(type="text", text="\n".join(lines))]


async def _sync_sessions(trigger_analysis: bool = True) -> list[TextContent]:
    log: list[str] = []

    if not _CLAUDE_DIR.exists():
        return [TextContent(type="text", text=f"Claude projects dir not found: {_CLAUDE_DIR}")]

    # Collect all session files
    session_files: list[Path] = []
    for project_dir in _CLAUDE_DIR.iterdir():
        if project_dir.is_dir():
            for f in project_dir.glob("*.jsonl"):
                if ".ccr-tip" not in f.name:
                    session_files.append(f)

    log.append(f"Found {len(session_files)} session file(s) in {_CLAUDE_DIR}")

    # Parse and scrub
    conversations = []
    for path in session_files:
        conv = parse_claude_session(path)
        if conv:
            conversations.append(conv)

    log.append(f"Parsed {len(conversations)} valid conversation(s)")

    if not conversations:
        log.append("Nothing to upload.")
        return [TextContent(type="text", text="\n".join(log))]

    # Upload to HF dataset
    added = append_conversations(conversations)
    log.append(f"Uploaded {added} new conversation(s) to dataset")

    # Pull back latest rules
    rules = load_active_rules()
    log.append(f"Pulled {len(rules)} active rule(s) from dataset")

    if trigger_analysis:
        log.append(
            "Tip: open your AI Rule Learning Space and click "
            "🔁 Force Re-analyze All to generate new rules from the uploaded conversations."
        )

    return [TextContent(type="text", text="\n".join(log))]


def main() -> None:
    async def _run():
        async with stdio_server() as streams:
            await app.run(streams[0], streams[1], app.create_initialization_options())

    asyncio.run(_run())


if __name__ == "__main__":
    main()
