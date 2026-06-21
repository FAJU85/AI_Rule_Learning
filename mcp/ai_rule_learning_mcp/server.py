"""AI Rule Learning MCP server — works with any AI agent.

Supports: Claude Code, Codex, Cursor, Windsurf, GitHub Copilot, and any
MCP-compatible agent. Rules are written automatically to every detected
agent's config directory so they apply to future sessions with zero setup.

Environment variables (all optional):
  HF_TOKEN        HuggingFace write token — enables cloud backup/sync
  ARL_DATASET     Your HF dataset, e.g. "yourname/AI_Rule_Learning"
  ARL_SESSIONS    Comma-separated paths to session dirs/files.
                  Defaults to ~/.claude/projects (Claude Code).
  ARL_CONTRIBUTE  "true" to contribute anonymised gap patterns (default: false)
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
from .gap_detector import analyze_conversations, generate_rules
from .injector import detected_targets, format_rules_block, write_memory_all, write_rules_all
from .memory import (
    add_memory,
    format_memory_for_display,
    forget,
    load_memory,
)
from .providers import parse_any
from .store import (
    _local_load,
    _local_save,
    append_conversations,
    auto_activate_pending_rules,
    is_already_processed,
    load_active_rules,
    mark_processed,
)

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
                "Return your personal AI guardrail rules as a formatted block. "
                "Works with any AI agent — Claude, Codex, Cursor, Windsurf, Copilot. "
                "Call at the start of important sessions to load your personalised rules."
            ),
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="record_feedback",
            description=(
                "Record a correction, preference, or friction pattern observed during "
                "this session. Call this whenever the user corrects you, repeats context "
                "they already gave, or you fail to complete all parts of a request. "
                "A rule is generated immediately and written to all detected AI agent "
                "config files so it applies to every future session automatically. "
                "No sync required — this works in real time."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "feedback_type": {
                        "type": "string",
                        "enum": [
                            "correction",
                            "preference",
                            "repeated_context",
                            "incomplete_response",
                        ],
                        "description": (
                            "correction: user said you were wrong or corrected your output. "
                            "preference: user stated a preference (language, style, format). "
                            "repeated_context: user had to re-state something they already told you. "
                            "incomplete_response: user pointed out you missed part of the request."
                        ),
                    },
                    "description": {
                        "type": "string",
                        "description": "What happened — what the user said or what pattern was observed.",
                    },
                    "rule_hint": {
                        "type": "string",
                        "description": (
                            "Optional: a specific instruction for the rule. "
                            "If omitted, a rule is generated from the feedback_type template."
                        ),
                    },
                },
                "required": ["feedback_type", "description"],
            },
        ),
        Tool(
            name="sync_sessions",
            description=(
                "Scan local AI session history, detect recurring friction patterns, "
                "generate personalised guardrail rules, and write them to every "
                "detected AI agent config (Claude Code, Cursor, Windsurf, Copilot). "
                "No HuggingFace account needed — works fully offline. "
                "Supports Claude Code, ChatGPT exports, and generic JSONL files."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "contribute": {
                        "type": "boolean",
                        "description": (
                            "Opt in to contribute anonymised gap patterns to the community "
                            "pool. Improves rules for all users. Does NOT share raw text."
                        ),
                    },
                    "paths": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Optional: paths to session directories or files. "
                            "Supports Claude Code dirs, ChatGPT conversations.json, "
                            "or any directory of JSONL files."
                        ),
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="remember",
            description=(
                "Persist a fact, preference, or context about the user so it is available "
                "in every future AI session across all agents (Claude Code, Cursor, Windsurf, "
                "Copilot, Codex). Call whenever the user states a preference, mentions their "
                "stack or projects, or gives context that should always apply. "
                "This is how the system compounds knowledge over time."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": [
                            "preference",
                            "project",
                            "never",
                            "user_info",
                            "context",
                        ],
                        "description": (
                            "preference: coding/style/format preference. "
                            "project: active project or task context. "
                            "never: hard constraint — something to never do. "
                            "user_info: fact about the user (timezone, role, team size). "
                            "context: stack, tools, environment info."
                        ),
                    },
                    "content": {
                        "type": "string",
                        "description": "The fact to remember, stated clearly and concisely.",
                    },
                },
                "required": ["type", "content"],
            },
        ),
        Tool(
            name="recall",
            description=(
                "Read all persisted facts, preferences, and context about the user. "
                "Call at the start of a session to load everything known about this user "
                "before they say a word. Returns memory grouped by type."
            ),
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="list_providers",
            description="Show which session sources and AI agents are detected on this machine.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "get_guardrail_rules":
        return await _get_guardrail_rules()
    if name == "remember":
        return await _remember(
            memory_type=arguments.get("type", "context"),
            content=arguments.get("content", ""),
        )
    if name == "recall":
        return await _recall()
    if name == "record_feedback":
        return await _record_feedback(
            feedback_type=arguments.get("feedback_type", "correction"),
            description=arguments.get("description", ""),
            rule_hint=arguments.get("rule_hint", ""),
        )
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
                text=(
                    "No guardrail rules yet.\n"
                    "Run sync_sessions to analyse your session history and generate rules,\n"
                    "or use record_feedback during a session to capture rules in real time."
                ),
            )
        ]
    write_rules_all(rules)
    return [TextContent(type="text", text=format_rules_block(rules))]


async def _remember(memory_type: str, content: str) -> list[TextContent]:
    if not content.strip():
        return [TextContent(type="text", text="❌ Content cannot be empty.")]

    entry = add_memory(memory_type, content)
    entries = load_memory()
    written = write_memory_all(entries)
    targets_str = ", ".join(n for n, _ in written) if written else "no agent configs detected"

    return [
        TextContent(
            type="text",
            text=(
                f"✅ Remembered [{entry['type']}]: {entry['content']}\n"
                f"Written to: {targets_str}\n"
                f"Total memories: {len(entries)}"
            ),
        )
    ]


async def _recall() -> list[TextContent]:
    entries = load_memory()
    return [TextContent(type="text", text=format_memory_for_display(entries))]


async def _record_feedback(
    feedback_type: str,
    description: str,
    rule_hint: str = "",
) -> list[TextContent]:
    _GAP_MAP = {
        "correction": "explicit_correction",
        "preference": "repeated_context",
        "repeated_context": "repeated_context",
        "incomplete_response": "incomplete_response",
    }
    gap_type = _GAP_MAP.get(feedback_type, "explicit_correction")

    gaps = {gap_type: [{"turn": 0, "signal": feedback_type, "snippet": description[:200]}]}
    rules = generate_rules(gaps)

    if not rules:
        return [TextContent(type="text", text="Could not generate a rule from this feedback.")]

    if rule_hint:
        rules[0]["action"] = {"instruction": rule_hint}
        rules[0]["instruction"] = rule_hint

    existing = _local_load("rules.jsonl")
    existing_ids = {r.get("rule_id") for r in existing}
    new_rules = [r for r in rules if r.get("rule_id") not in existing_ids]
    if new_rules:
        _local_save("rules.jsonl", existing + new_rules)

    all_rules = load_active_rules()
    written = write_rules_all(all_rules)
    targets_str = ", ".join(name for name, _ in written) if written else "no agent configs detected"

    rule_name = rules[0].get("name", "new rule")
    action = "Created" if new_rules else "Already known"

    return [
        TextContent(
            type="text",
            text=(
                f"✅ {action}: **{rule_name}**\n"
                f"Written to: {targets_str}\n"
                f"This rule will apply automatically to every future session."
            ),
        )
    ]


async def _sync_sessions(
    paths: list[Path] | None = None,
    contribute: bool = False,
) -> list[TextContent]:
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

    new_files = [f for f in session_files if not is_already_processed(f)]
    log.append(f"🆕 {len(new_files)} new file(s) to process")

    all_conversations: list[dict] = []
    for path in new_files:
        convs = parse_any(path)
        if convs:
            all_conversations.extend(convs)
            mark_processed(path)

    log.append(f"✅ Parsed {len(all_conversations)} valid conversation(s)")

    if not all_conversations:
        rules = load_active_rules()
        if rules:
            written = write_rules_all(rules)
            targets = ", ".join(n for n, _ in written)
            log.append(f"📝 {len(rules)} existing rule(s) refreshed → {targets}")
        else:
            log.append("ℹ️  No new conversations and no existing rules yet.")
        return [TextContent(type="text", text="\n".join(log))]

    # ── Local gap detection ────────────────────────────────────────────────
    detected_rules = analyze_conversations(all_conversations)
    if detected_rules:
        existing = _local_load("rules.jsonl")
        existing_ids = {r.get("rule_id") for r in existing}
        new_rules = [r for r in detected_rules if r.get("rule_id") not in existing_ids]
        if new_rules:
            _local_save("rules.jsonl", existing + new_rules)
            log.append(f"🧠 Generated {len(new_rules)} new rule(s) from detected patterns")
        else:
            log.append("ℹ️  All detected patterns already have rules")

    # ── HF upload (optional) ───────────────────────────────────────────────
    added = append_conversations(all_conversations)
    if added:
        log.append(f"⬆️  Uploaded {added} new conversation(s) to HF dataset")

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
        if contributed:
            log.append(f"🤝 Contributed anonymised patterns from {contributed} session(s)")

    activated = auto_activate_pending_rules()
    if activated:
        log.append(f"✅ Auto-activated {activated} safe pending rule(s) from HF dataset")

    # ── Write to all detected agent configs ────────────────────────────────
    rules = load_active_rules()
    if rules:
        written = write_rules_all(rules)
        if written:
            targets = ", ".join(n for n, _ in written)
            log.append(f"📝 {len(rules)} rule(s) written to: {targets}")
        log.append("🎉 Rules will apply automatically to every future session!")
    else:
        log.append("ℹ️  No active rules yet — need more session data")

    return [TextContent(type="text", text="\n".join(log))]


async def _list_providers() -> list[TextContent]:
    lines = [f"**Community opt-in:** {_CONTRIBUTE}", ""]

    lines.append("**Detected AI agents:**")
    for target in detected_targets():
        p = target.config_path()
        status = "✅ rules injected" if p.exists() else "⬜ config will be created on next sync"
        lines.append(f"  {target.name}: {status}")
    lines.append("")

    lines.append("**Session paths:**")
    for sp in _SESSION_PATHS:
        sp = Path(sp)
        if not sp.exists():
            lines.append(f"  ❌ {sp} — not found")
            continue
        count = sum(1 for _ in sp.rglob("*.jsonl")) + sum(
            1 for _ in sp.rglob("conversations.json")
        )
        lines.append(f"  ✅ {sp} — {count} file(s)")
    lines.append("")
    lines.append(
        "**Supported formats:** Claude Code (.jsonl), ChatGPT export (conversations.json), Generic JSONL"
    )
    return [TextContent(type="text", text="\n".join(lines))]


def main() -> None:
    async def _run():
        async with stdio_server() as streams:
            await app.run(streams[0], streams[1], app.create_initialization_options())

    asyncio.run(_run())


if __name__ == "__main__":
    main()
