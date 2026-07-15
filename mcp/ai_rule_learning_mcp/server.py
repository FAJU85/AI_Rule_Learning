"""AI Rule Learning MCP server — works with any AI agent.

Supports: Claude Code, Codex, Cursor, Windsurf, GitHub Copilot, and any
MCP-compatible agent. Rules are written automatically to every detected
agent's config directory so they apply to future sessions with zero setup.

Environment variables (all optional):
  HF_TOKEN        HuggingFace write token — enables cloud backup/sync
  ARL_DATASET     Your HF dataset, e.g. "yourname/AI_Rule_Learning"
  ARL_SESSIONS    Comma-separated paths to session dirs/files.
                  Defaults to existing Claude dirs: ~/.claude/projects, ~/.claude.
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

from . import __version__
from .analyzer import run_analyze
from .community import contribute_gaps
from .gap_detector import analyze_conversations
from .gap_detector import generate_rules
from .injector import detected_targets
from .injector import format_rules_block
from .injector import write_memory_all
from .injector import write_rules_all
from .injector import write_skills_all
from .memory import add_memory
from .memory import format_memory_for_display
from .memory import load_memory
from .providers import parse_any
from .skills import format_skill_detail
from .skills import format_skills_for_display
from .skills import get_skill
from .skills import list_skills
from .skills import save_skill
from .store import _local_load
from .store import _local_save
from .store import append_conversations
from .store import auto_activate_pending_rules
from .store import edit_rule_instruction
from .store import get_rule
from .store import hf_enabled
from .store import is_already_processed
from .store import list_rules as store_list_rules
from .store import load_active_rules
from .store import mark_processed
from .store import merge_rules as store_merge_rules
from .store import offline_enabled
from .store import record_rule_outcome
from .store import review_rule_health
from .store import suggest_duplicate_rules
from .store import update_rule_status

_CONTRIBUTE = os.environ.get("ARL_CONTRIBUTE", "false").lower() == "true"

_SESSION_PATHS: list[Path] = []
_raw = os.environ.get("ARL_SESSIONS", "")
if _raw:
    _SESSION_PATHS = [Path(p.strip()) for p in _raw.split(",") if p.strip()]
else:
    _SESSION_PATHS = [Path.home() / ".claude" / "projects", Path.home() / ".claude"]

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
            inputSchema={
                "type": "object",
                "properties": {
                    "dry_run": {
                        "type": "boolean",
                        "description": "Preview formatted rules without writing them to agent config files.",
                    }
                },
                "required": [],
            },
        ),
        Tool(
            name="record_feedback",
            description=(
                "Record a correction, preference, or friction pattern observed during "
                "this session. Call this whenever the user corrects you, repeats context "
                "they already gave, or you fail to complete all parts of a request. "
                "A rule is generated immediately and written to all detected AI agent "
                "config files so it applies to every future session automatically. "
                "No sync required — this works in real time. Required input: "
                "description — describe what happened and the required correction."
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
                        "description": (
                            "Required. Description of what happened and the required correction. "
                            "Example: 'User corrected my answer; always acknowledge the correction and fix it immediately.'"
                        ),
                    },
                    "rule_hint": {
                        "type": "string",
                        "description": (
                            "Optional: a specific instruction for the rule. "
                            "If omitted, a rule is generated from the feedback_type template."
                        ),
                    },
                    "dry_run": {
                        "type": "boolean",
                        "description": "Preview the generated rule without saving it or writing agent configs.",
                    },
                },
                "required": ["feedback_type", "description"],
            },
        ),
        Tool(
            name="sync_sessions",
            description=(
                "Analyse local AI session files, detect recurring friction patterns, "
                "generate personalised guardrail rules, and write them to your AI agent "
                "configs (Claude Code, Cursor, Windsurf, Copilot). "
                "Works offline with no setup. "
                "Optionally feeds anonymised patterns to a central learning dataset that "
                "makes the rule engine smarter for every user over time — "
                "similar to how spell-check improves from aggregated corrections. "
                "Raw conversation text is never stored or shared; only structural gap "
                "patterns (e.g. 'missing_context occurred 3 times') are extracted. "
                "The dataset is used exclusively to improve rule quality — "
                "not sold, not shared with third parties, not readable by other users. "
                "Supports Claude Code projects, ChatGPT exports, and generic JSONL files."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "contribute": {
                        "type": "boolean",
                        "description": (
                            "Default: false. Set true to contribute anonymised gap-type "
                            "counts to the central learning dataset. "
                            "No raw text, no filenames, no personal data is included — "
                            "only aggregate pattern counts that help improve rule detection "
                            "accuracy for all users."
                        ),
                    },
                    "paths": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Optional list of session file paths or directories to scan. "
                            "Supports Claude Code project dirs, ChatGPT conversations.json, "
                            "or any directory of JSONL files. "
                            "If omitted, scans existing default directories only: "
                            "~/.claude/projects and ~/.claude. "
                            "If none exist, pass paths or set ARL_SESSIONS."
                        ),
                    },
                    "dry_run": {
                        "type": "boolean",
                        "description": "Preview what would be parsed and generated without marking files processed or writing data/configs.",
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
                "This is how the system compounds knowledge over time. Valid types: "
                "preference, project, never, user_info, context."
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
                    "dry_run": {
                        "type": "boolean",
                        "description": "Preview the memory entry without saving it or writing agent configs.",
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
            name="install_scheduler",
            description=(
                "Install a nightly automatic sync job on the user's machine so that "
                "ai-rule-learning sync runs every night at 02:00 without any manual action. "
                "Uses LaunchAgent on macOS, systemd timer on Linux, or cron as fallback. "
                "Call this once after the user installs the MCP to make the system fully autonomous."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["install", "uninstall", "status"],
                        "description": "install: set up nightly sync. uninstall: remove it. status: check current state.",
                    },
                    "dry_run": {
                        "type": "boolean",
                        "description": "Preview install/uninstall actions without changing scheduler configuration.",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="list_providers",
            description="Show which session sources and AI agents are detected on this machine.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="save_skill",
            description=(
                "Save a reusable workflow procedure so it can be recalled in any future session "
                "across all AI agents. Call when the user completes a multi-step task that they "
                "are likely to repeat — e.g. 'create a FastAPI endpoint' or 'prepare a release checklist'. "
                "The skill is stored locally and its name is injected into every agent config "
                "so agents know it exists without loading the full steps every time. "
                "The steps field may be a newline-separated string or an array of step strings."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Short descriptive name, e.g. 'Create FastAPI Endpoint'.",
                    },
                    "description": {
                        "type": "string",
                        "description": "One sentence explaining what this skill does.",
                    },
                    "steps": {
                        "oneOf": [
                            {"type": "string"},
                            {"type": "array", "items": {"type": "string"}},
                        ],
                        "description": (
                            "The full procedure in markdown. Use a newline-separated string, "
                            "for example: 'Step 1: Check input\nStep 2: Process data\nStep 3: Return result'. "
                            "Arrays of strings are also accepted and joined with newlines."
                        ),
                    },
                    "triggers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Keywords or phrases that should trigger loading this skill.",
                    },
                    "dry_run": {
                        "type": "boolean",
                        "description": "Preview the skill save without writing the skill file or agent configs.",
                    },
                },
                "required": ["name", "description", "steps"],
            },
        ),
        Tool(
            name="list_skills",
            description=(
                "List all saved skill procedures (names and descriptions only). "
                "Call at the start of a session to know which reusable workflows are available, "
                "then call get_skill to load the full steps when needed."
            ),
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="get_skill",
            description=(
                "Load the full steps for a saved skill by name or keyword. "
                "Returns the complete procedure so you can follow it exactly. "
                "Also increments the usage counter so popular skills are tracked."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Skill name or keyword to search for.",
                    }
                },
                "required": ["name"],
            },
        ),
        Tool(
            name="list_rules",
            description=(
                "List stored guardrail rules by lifecycle status. Use status='all' for every rule, "
                "or filter by pending, active, rejected, inactive, stale, needs_review, or merged."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": [
                            "all",
                            "pending",
                            "approved",
                            "rejected",
                            "active",
                            "inactive",
                            "stale",
                            "needs_review",
                            "merged",
                        ],
                        "description": "Rule lifecycle status to list. Defaults to active.",
                    }
                },
                "required": [],
            },
        ),
        Tool(
            name="approve_rule",
            description="Approve and activate a stored rule so it can be injected into agent configs.",
            inputSchema={
                "type": "object",
                "properties": {
                    "rule_id": {"type": "string", "description": "Rule id to approve."},
                    "dry_run": {
                        "type": "boolean",
                        "description": "Preview approval without changing the rule store.",
                    },
                },
                "required": ["rule_id"],
            },
        ),
        Tool(
            name="reject_rule",
            description="Reject a stored rule so it is not injected into agent configs.",
            inputSchema={
                "type": "object",
                "properties": {
                    "rule_id": {"type": "string", "description": "Rule id to reject."},
                    "note": {"type": "string", "description": "Optional review note explaining the rejection."},
                    "dry_run": {
                        "type": "boolean",
                        "description": "Preview rejection without changing the rule store.",
                    },
                },
                "required": ["rule_id"],
            },
        ),
        Tool(
            name="edit_rule",
            description="Update a stored rule instruction without manually editing JSONL files.",
            inputSchema={
                "type": "object",
                "properties": {
                    "rule_id": {"type": "string", "description": "Rule id to edit."},
                    "instruction": {"type": "string", "description": "Replacement instruction for the rule."},
                    "dry_run": {
                        "type": "boolean",
                        "description": "Preview the edit without changing the rule store.",
                    },
                },
                "required": ["rule_id", "instruction"],
            },
        ),
        Tool(
            name="merge_rules",
            description="Mark a duplicate rule as merged into a primary rule.",
            inputSchema={
                "type": "object",
                "properties": {
                    "primary_rule_id": {"type": "string", "description": "Rule id to keep."},
                    "duplicate_rule_id": {"type": "string", "description": "Duplicate rule id to merge/deactivate."},
                    "dry_run": {
                        "type": "boolean",
                        "description": "Preview the merge without changing the rule store.",
                    },
                },
                "required": ["primary_rule_id", "duplicate_rule_id"],
            },
        ),
        Tool(
            name="record_rule_outcome",
            description="Record whether a rule worked or failed so effectiveness can improve over time.",
            inputSchema={
                "type": "object",
                "properties": {
                    "rule_id": {"type": "string", "description": "Rule id to score."},
                    "worked": {
                        "type": "boolean",
                        "description": "True if the rule prevented the issue; false if the issue recurred.",
                    },
                    "dry_run": {
                        "type": "boolean",
                        "description": "Preview the outcome update without changing the rule store.",
                    },
                },
                "required": ["rule_id", "worked"],
            },
        ),
        Tool(
            name="suggest_duplicate_rules",
            description=(
                "Suggest likely duplicate guardrail rules using read-only local similarity so the owner "
                "can review and merge redundant rules explicitly."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "min_similarity": {
                        "type": "number",
                        "description": "Minimum similarity score between 0 and 1. Default: 0.7.",
                    },
                    "include_inactive": {
                        "type": "boolean",
                        "description": "Include inactive/stale/needs_review rules in suggestions. Default: false.",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="review_rule_health",
            description=(
                "Preview or apply rule health review automation. Finds stale active rules "
                "and low-effectiveness rules that should be reviewed before future injection."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "apply": {
                        "type": "boolean",
                        "description": "When true, update matching rule statuses. Defaults to preview only.",
                    },
                    "dry_run": {
                        "type": "boolean",
                        "description": "Preview changes even when apply=true; no rule store writes occur.",
                    },
                    "stale_days": {
                        "type": "integer",
                        "description": "Mark active rules stale after this many days without activity. Default: 90.",
                    },
                    "low_effectiveness_threshold": {
                        "type": "number",
                        "description": "Mark rules needs_review at or below this effectiveness score. Default: 0.3.",
                    },
                    "min_triggered": {
                        "type": "integer",
                        "description": "Minimum trigger count before low effectiveness can mark a rule. Default: 3.",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="analyze",
            description=(
                "All-in-one analysis tool. Call with action='all' for a complete report, "
                "or choose a specific action:\n"
                "• failure_modes — breakdown of active rules by Composo failure category and Planit layer\n"
                "• session_health — 0-100 session health score with top contributing issues\n"
                "• check_injection — scan a prompt for injection attack patterns\n"
                "• effectiveness — summary of rule effectiveness scores (green/amber/red)\n"
                "• record_outcome — update effectiveness tracking for a specific rule\n"
                "• all — run all of the above and return a unified report"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": [
                            "all",
                            "failure_modes",
                            "session_health",
                            "check_injection",
                            "effectiveness",
                            "record_outcome",
                        ],
                        "description": "Which analysis to perform. Defaults to 'all'.",
                    },
                    "prompt": {
                        "type": "string",
                        "description": "Required for action='check_injection'. The text to scan.",
                    },
                    "rule_id": {
                        "type": "string",
                        "description": "Required for action='record_outcome'. The rule_id to update.",
                    },
                    "fired_again": {
                        "type": "boolean",
                        "description": (
                            "Required for action='record_outcome'. "
                            "True if the gap recurred (rule not working); "
                            "False if the gap stopped (rule suppressed it)."
                        ),
                    },
                },
                "required": ["action"],
            },
        ),
        Tool(
            name="update_community_knowledge",
            description=(
                "Read accumulated community gap contributions, derive enhanced rule templates "
                "from patterns that appear across 3+ independent sessions, and publish them "
                "back to the community dataset so all users benefit on next sync. "
                "Requires HF_TOKEN and write access to the community dataset. "
                "Run this periodically to close the learning loop: "
                "contribute → aggregate → improve → distribute."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "min_sources": {
                        "type": "integer",
                        "description": "Minimum unique session sources before a pattern becomes a template. Default: 3.",
                    }
                },
                "required": [],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    # Contain handler failures: return a structured error to the agent rather
    # than letting an unexpected exception propagate (and leak a stack trace).
    try:
        if name == "get_guardrail_rules":
            return await _get_guardrail_rules(dry_run=bool(arguments.get("dry_run", False)))
        if name == "remember":
            return await _remember(
                memory_type=arguments.get("type", "context"),
                content=arguments.get("content", ""),
                dry_run=bool(arguments.get("dry_run", False)),
            )
        if name == "recall":
            return await _recall()
        if name == "record_feedback":
            return await _record_feedback(
                feedback_type=arguments.get("feedback_type", "correction"),
                description=arguments.get("description", ""),
                rule_hint=arguments.get("rule_hint", ""),
                dry_run=bool(arguments.get("dry_run", False)),
            )
        if name == "sync_sessions":
            paths = [Path(p) for p in arguments.get("paths", [])] or None
            contribute = arguments.get("contribute", _CONTRIBUTE)
            return await _sync_sessions(
                paths=paths,
                contribute=contribute,
                dry_run=bool(arguments.get("dry_run", False)),
            )
        if name == "install_scheduler":
            return await _install_scheduler(
                arguments.get("action", "install"),
                dry_run=bool(arguments.get("dry_run", False)),
            )
        if name == "list_providers":
            return await _list_providers()
        if name == "save_skill":
            return await _save_skill(
                skill_name=arguments.get("name", ""),
                description=arguments.get("description", ""),
                steps=arguments.get("steps", ""),
                triggers=arguments.get("triggers", []),
                dry_run=bool(arguments.get("dry_run", False)),
            )
        if name == "list_skills":
            return await _list_skills()
        if name == "get_skill":
            return await _get_skill(arguments.get("name", ""))
        if name == "list_rules":
            return await _list_rules(status=arguments.get("status", "active"))
        if name == "approve_rule":
            return await _approve_rule(
                rule_id=arguments.get("rule_id", ""),
                dry_run=bool(arguments.get("dry_run", False)),
            )
        if name == "reject_rule":
            return await _reject_rule(
                rule_id=arguments.get("rule_id", ""),
                note=arguments.get("note", ""),
                dry_run=bool(arguments.get("dry_run", False)),
            )
        if name == "edit_rule":
            return await _edit_rule(
                rule_id=arguments.get("rule_id", ""),
                instruction=arguments.get("instruction", ""),
                dry_run=bool(arguments.get("dry_run", False)),
            )
        if name == "merge_rules":
            return await _merge_rules(
                primary_rule_id=arguments.get("primary_rule_id", ""),
                duplicate_rule_id=arguments.get("duplicate_rule_id", ""),
                dry_run=bool(arguments.get("dry_run", False)),
            )
        if name == "record_rule_outcome":
            return await _record_rule_outcome(
                rule_id=arguments.get("rule_id", ""),
                worked=bool(arguments.get("worked", False)),
                dry_run=bool(arguments.get("dry_run", False)),
            )

        if name == "suggest_duplicate_rules":
            return await _suggest_duplicate_rules(
                min_similarity=float(arguments.get("min_similarity", 0.7)),
                include_inactive=bool(arguments.get("include_inactive", False)),
            )
        if name == "review_rule_health":
            return await _review_rule_health(
                apply=bool(arguments.get("apply", False)),
                dry_run=bool(arguments.get("dry_run", False)),
                stale_days=int(arguments.get("stale_days", 90)),
                low_effectiveness_threshold=float(arguments.get("low_effectiveness_threshold", 0.3)),
                min_triggered=int(arguments.get("min_triggered", 3)),
            )
        if name == "analyze":
            return await _analyze(
                action=arguments.get("action", "all"),
                prompt=arguments.get("prompt", ""),
                rule_id=arguments.get("rule_id", ""),
                fired_again=arguments.get("fired_again"),
            )
        if name == "update_community_knowledge":
            return await _update_community_knowledge(min_sources=int(arguments.get("min_sources", 3)))
        return [TextContent(type="text", text=f"Unknown tool: {name}")]
    except Exception as exc:  # noqa: BLE001 — boundary handler, report not crash
        return [TextContent(type="text", text=f"❌ {name} failed: {type(exc).__name__}: {exc}")]


async def _get_guardrail_rules(dry_run: bool = False) -> list[TextContent]:
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
    if dry_run:
        return [
            TextContent(
                type="text",
                text="🔎 Dry run: would refresh guardrail rules in detected agent configs.\n\n"
                + format_rules_block(rules),
            )
        ]
    write_rules_all(rules)
    return [TextContent(type="text", text=format_rules_block(rules))]


async def _remember(memory_type: str, content: str, dry_run: bool = False) -> list[TextContent]:
    if not content.strip():
        return [TextContent(type="text", text="❌ Content cannot be empty.")]

    if dry_run:
        return [
            TextContent(
                type="text",
                text=f"🔎 Dry run: would remember [{memory_type}]: {content.strip()}",
            )
        ]

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
    dry_run: bool = False,
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

    rule_name = rules[0].get("name", "new rule")
    if dry_run:
        return [
            TextContent(
                type="text",
                text=(
                    f"🔎 Dry run: would create rule **{rule_name}** from "
                    f"{feedback_type} feedback. No rule store or agent config files changed."
                ),
            )
        ]

    existing = _local_load("rules.jsonl")
    existing_by_id = {r.get("rule_id"): r for r in existing}
    now = rules[0].get("last_observed")
    new_rules = [r for r in rules if r.get("rule_id") not in existing_by_id]
    if new_rules:
        _local_save("rules.jsonl", existing + new_rules)
    else:
        target = existing_by_id.get(rules[0].get("rule_id"))
        if target is not None:
            target["evidence_count"] = int(target.get("evidence_count", target.get("instance_count", 0)) or 0) + 1
            target["instance_count"] = max(int(target.get("instance_count", 0) or 0), target["evidence_count"])
            target["confidence"] = min(0.95, round(float(target.get("confidence", 0.55) or 0.55) + 0.05, 2))
            target["last_observed"] = now
            target["updated_at"] = now
            _local_save("rules.jsonl", existing)

    all_rules = load_active_rules()
    written = write_rules_all(all_rules)
    targets_str = ", ".join(name for name, _ in written) if written else "no agent configs detected"

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
    dry_run: bool = False,
) -> list[TextContent]:
    log: list[str] = []
    if offline_enabled():
        log.append("🔌 Offline mode enabled (ARL_OFFLINE=true): Hugging Face/community network access is disabled.")
    if dry_run:
        log.append("🔎 Dry run: no session files will be marked processed and no data/config files will be written.")

    requested_paths = [Path(p) for p in paths] if paths else []
    default_paths = [Path(p) for p in _SESSION_PATHS]
    scan_paths = requested_paths or [path for path in default_paths if path.exists()]
    session_files: list[Path] = []

    if not scan_paths:
        defaults = ", ".join(str(path) for path in default_paths)
        log.append("⚠️  No session directories found.")
        log.append("Set ARL_SESSIONS or pass paths/session_paths to sync_sessions.")
        log.append(f"Checked defaults: {defaults}")
        return [TextContent(type="text", text="\n".join(log))]

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
            if not dry_run:
                mark_processed(path)

    log.append(f"✅ Parsed {len(all_conversations)} valid conversation(s)")

    if not all_conversations:
        rules = load_active_rules()
        if rules:
            if dry_run:
                log.append(f"🔎 Dry run: would refresh {len(rules)} existing rule(s)")
            else:
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
            if dry_run:
                log.append(f"🔎 Dry run: would generate {len(new_rules)} new rule(s) from detected patterns")
            else:
                _local_save("rules.jsonl", existing + new_rules)
                log.append(f"🧠 Generated {len(new_rules)} new rule(s) from detected patterns")
        else:
            log.append("ℹ️  All detected patterns already have rules")
    else:
        log.append(
            "ℹ️  No rules generated from parsed conversations. "
            "Need at least one recognized friction pattern; set ARL_MIN_RULE_EVIDENCE to tune the evidence threshold."
        )

    # ── HF upload (optional) ───────────────────────────────────────────────
    added = 0 if dry_run else append_conversations(all_conversations)
    if dry_run and all_conversations:
        log.append(f"🔎 Dry run: would save {len(all_conversations)} conversation(s) locally")
    if added:
        if hf_enabled():
            log.append(f"⬆️  Uploaded {added} new conversation(s) to HF dataset")
        else:
            log.append(f"💾 Saved {added} new conversation(s) locally (no HF token — upload skipped)")

    if contribute and dry_run:
        log.append("🔎 Dry run: would evaluate anonymised community contribution eligibility")
    if contribute and not dry_run:
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

    activated = 0 if dry_run else auto_activate_pending_rules()
    if activated:
        log.append(f"✅ Auto-activated {activated} safe pending rule(s) from HF dataset")

    # ── RAG: pull and load community templates ─────────────────────────────
    from .community import pull_community_templates
    from .gap_detector import load_community_templates

    community_tpls = [] if dry_run else pull_community_templates()
    if community_tpls:
        load_community_templates(community_tpls)
        log.append(f"🔍 Loaded {len(community_tpls)} community-derived template(s) for RAG augmentation")

    # ── Write to all detected agent configs ────────────────────────────────
    rules = load_active_rules()
    if rules:
        if dry_run:
            log.append(f"🔎 Dry run: would write {len(rules)} active rule(s) to detected agent configs")
        else:
            written = write_rules_all(rules)
            if written:
                targets = ", ".join(n for n, _ in written)
                log.append(f"📝 {len(rules)} rule(s) written to: {targets}")
            log.append("🎉 Rules will apply automatically to every future session!")
    else:
        log.append("ℹ️  No active rules yet — need more session data")

    return [TextContent(type="text", text="\n".join(log))]


async def _install_scheduler(action: str = "install", dry_run: bool = False) -> list[TextContent]:
    from .scheduler import install
    from .scheduler import is_installed
    from .scheduler import status
    from .scheduler import uninstall

    if action == "uninstall":
        if dry_run:
            return [TextContent(type="text", text="🔎 Dry run: would remove the nightly auto-sync job.")]
        removed = uninstall()
        msg = "✅ Nightly auto-sync removed." if removed else "ℹ️  No auto-sync job found."
        return [TextContent(type="text", text=msg)]

    if action == "status":
        return [TextContent(type="text", text=status())]

    # install
    if dry_run:
        return [TextContent(type="text", text="🔎 Dry run: would install the nightly auto-sync job at 02:00.")]

    if is_installed():
        return [TextContent(type="text", text=f"ℹ️  Already installed.\n{status()}")]

    result = install()
    return [
        TextContent(
            type="text",
            text=(
                f"✅ {result}\n\n"
                "The system will now sync automatically every night at 02:00.\n"
                "Rules and memory will update without any manual action."
            ),
        )
    ]


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
        count = sum(1 for _ in sp.rglob("*.jsonl")) + sum(1 for _ in sp.rglob("conversations.json"))
        lines.append(f"  ✅ {sp} — {count} file(s)")
    lines.append("")
    lines.append("**Supported formats:** Claude Code (.jsonl), ChatGPT export (conversations.json), Generic JSONL")
    return [TextContent(type="text", text="\n".join(lines))]


async def _save_skill(
    skill_name: str,
    description: str,
    steps: str | list[str],
    triggers: list[str] | None = None,
    dry_run: bool = False,
) -> list[TextContent]:
    if isinstance(steps, list):
        steps = "\n".join(str(step) for step in steps)
    else:
        steps = str(steps)

    if not skill_name.strip():
        return [TextContent(type="text", text="❌ Skill name cannot be empty.")]
    if not steps.strip():
        return [TextContent(type="text", text="❌ Steps cannot be empty.")]

    if dry_run:
        return [
            TextContent(
                type="text",
                text=f"🔎 Dry run: would save skill **{skill_name.strip()}** and refresh agent configs.",
            )
        ]

    skill = save_skill(skill_name, description, steps, triggers or [])
    skills = list_skills()
    written = write_skills_all(skills)
    targets_str = ", ".join(n for n, _ in written) if written else "no agent configs detected"

    return [
        TextContent(
            type="text",
            text=(
                f"✅ Skill saved: **{skill['name']}**\n"
                f"Slug: {skill['slug']}\n"
                f"Written to: {targets_str}\n"
                f"Total skills: {len(skills)}\n\n"
                f'Call `get_skill("{skill["name"]}")` to load the full steps.'
            ),
        )
    ]


async def _list_skills() -> list[TextContent]:
    skills = list_skills()
    return [TextContent(type="text", text=format_skills_for_display(skills))]


async def _get_skill(name: str) -> list[TextContent]:
    if not name.strip():
        return [TextContent(type="text", text="❌ Skill name cannot be empty.")]

    skill = get_skill(name)
    if skill is None:
        return [
            TextContent(
                type="text",
                text=(f"❌ Skill not found: {name!r}\nUse list_skills to see available skills."),
            )
        ]
    return [TextContent(type="text", text=format_skill_detail(skill))]


def _format_rule_summary(rules: list[dict], title: str) -> str:
    if not rules:
        return f"No {title.lower()} rules found."
    lines = [f"{title} ({len(rules)}):", ""]
    for rule in rules:
        name = rule.get("name", rule.get("rule_id", "rule"))
        rule_id = rule.get("rule_id", "?")
        status = rule.get("status", "active")
        label = rule.get("priority_label", "MEDIUM")
        instruction = rule.get("action", {}).get("instruction") or rule.get("instruction", "")
        lines.append(f"- [{label}] {name}")
        lines.append(f"  id: {rule_id} | status: {status}")
        if instruction:
            lines.append(f"  → {instruction}")
    return "\n".join(lines)


async def _list_rules(status: str = "active") -> list[TextContent]:
    normalized = (status or "active").strip().lower()
    rules = store_list_rules(status=None if normalized == "all" else normalized)
    title = "All rules" if normalized == "all" else f"{normalized} rules"
    return [TextContent(type="text", text=_format_rule_summary(rules, title))]


async def _approve_rule(rule_id: str, dry_run: bool = False) -> list[TextContent]:
    if not rule_id.strip():
        return [TextContent(type="text", text="❌ Rule id cannot be empty.")]
    if dry_run:
        return [TextContent(type="text", text=f"🔎 Dry run: would approve and activate rule {rule_id!r}.")]
    rule = update_rule_status(rule_id, "active")
    if rule is None:
        return [TextContent(type="text", text=f"❌ Rule not found: {rule_id}")]
    return [TextContent(type="text", text=f"✅ Approved and activated rule: {rule_id}")]


async def _reject_rule(rule_id: str, note: str = "", dry_run: bool = False) -> list[TextContent]:
    if not rule_id.strip():
        return [TextContent(type="text", text="❌ Rule id cannot be empty.")]
    if dry_run:
        return [TextContent(type="text", text=f"🔎 Dry run: would reject rule {rule_id!r}.")]
    rule = update_rule_status(rule_id, "rejected", note=note)
    if rule is None:
        return [TextContent(type="text", text=f"❌ Rule not found: {rule_id}")]
    return [TextContent(type="text", text=f"✅ Rejected rule: {rule_id}")]


async def _edit_rule(rule_id: str, instruction: str, dry_run: bool = False) -> list[TextContent]:
    if not rule_id.strip():
        return [TextContent(type="text", text="❌ Rule id cannot be empty.")]
    if not instruction.strip():
        return [TextContent(type="text", text="❌ Instruction cannot be empty.")]
    if dry_run:
        return [TextContent(type="text", text=f"🔎 Dry run: would update instruction for rule {rule_id!r}.")]
    rule = edit_rule_instruction(rule_id, instruction)
    if rule is None:
        return [TextContent(type="text", text=f"❌ Rule not found: {rule_id}")]
    return [TextContent(type="text", text=f"✅ Updated rule instruction: {rule_id}")]


async def _merge_rules(
    primary_rule_id: str,
    duplicate_rule_id: str,
    dry_run: bool = False,
) -> list[TextContent]:
    if not primary_rule_id.strip() or not duplicate_rule_id.strip():
        return [TextContent(type="text", text="❌ Both primary_rule_id and duplicate_rule_id are required.")]
    if dry_run:
        return [
            TextContent(
                type="text",
                text=f"🔎 Dry run: would merge duplicate rule {duplicate_rule_id!r} into {primary_rule_id!r}.",
            )
        ]
    rule = store_merge_rules(primary_rule_id, duplicate_rule_id)
    if rule is None:
        return [TextContent(type="text", text=f"❌ Could not find both rules: {primary_rule_id}, {duplicate_rule_id}")]
    return [TextContent(type="text", text=f"✅ Merged {duplicate_rule_id} into {primary_rule_id}")]


async def _record_rule_outcome(
    rule_id: str,
    worked: bool,
    dry_run: bool = False,
) -> list[TextContent]:
    if not rule_id.strip():
        return [TextContent(type="text", text="❌ Rule id cannot be empty.")]
    if dry_run:
        outcome = "worked" if worked else "failed"
        return [TextContent(type="text", text=f"🔎 Dry run: would record rule {rule_id!r} outcome as {outcome}.")]
    rule = record_rule_outcome(rule_id, fired_again=not worked)
    if rule is None:
        return [TextContent(type="text", text=f"❌ Rule not found: {rule_id}")]
    score = rule.get("effectiveness_score", "unknown")
    return [TextContent(type="text", text=f"✅ Recorded outcome for rule: {rule_id} (effectiveness: {score})")]


async def _suggest_duplicate_rules(
    min_similarity: float = 0.7,
    include_inactive: bool = False,
) -> list[TextContent]:
    suggestions = suggest_duplicate_rules(min_similarity=min_similarity, include_inactive=include_inactive)
    if not suggestions:
        return [TextContent(type="text", text="No likely duplicate rules found.")]
    lines = [f"Likely duplicate rules ({len(suggestions)}):", ""]
    for item in suggestions:
        lines.append(
            f"- {item['primary_rule_id']} ↔ {item['duplicate_rule_id']} (similarity: {item['similarity']:.0%})"
        )
        lines.append(f"  {item['primary_name']} / {item['duplicate_name']}")
    lines.append("")
    lines.append("Review candidates, then call merge_rules if a pair should be merged.")
    return [TextContent(type="text", text="\n".join(lines))]


async def _review_rule_health(
    apply: bool = False,
    dry_run: bool = False,
    stale_days: int = 90,
    low_effectiveness_threshold: float = 0.3,
    min_triggered: int = 3,
) -> list[TextContent]:
    report = review_rule_health(
        stale_days=stale_days,
        low_effectiveness_threshold=low_effectiveness_threshold,
        min_triggered=min_triggered,
        apply=apply and not dry_run,
    )
    mode = "applied" if report["applied"] else "preview"
    lines = [
        f"Rule health review ({mode}):",
        f"stale: {len(report['stale'])}",
        f"needs_review: {len(report['needs_review'])}",
    ]
    for title in ("stale", "needs_review"):
        rules = report[title]
        if rules:
            lines.append("")
            lines.append(f"{title} candidates:")
            for rule in rules:
                lines.append(f"- {rule.get('rule_id')}: {rule.get('name', 'Unnamed rule')}")
    if dry_run:
        lines.append("")
        lines.append("🔎 Dry run: would update matching rule statuses if apply=true.")
    elif not apply:
        lines.append("")
        lines.append("Preview only. Re-run with apply=true to update rule statuses.")
    return [TextContent(type="text", text="\n".join(lines))]


async def _analyze(
    action: str,
    prompt: str,
    rule_id: str,
    fired_again: bool | None,
) -> list[TextContent]:
    text = run_analyze(action=action, prompt=prompt, rule_id=rule_id, fired_again=fired_again)
    return [TextContent(type="text", text=text)]


async def _update_community_knowledge(min_sources: int = 3) -> list[TextContent]:
    from .community import build_community_templates
    from .community import fetch_community_patterns
    from .community import push_community_templates

    log = []
    freq = fetch_community_patterns()
    if not freq:
        return [TextContent(type="text", text="⚠️ No community contributions found or HF_TOKEN not set.")]
    total_contributions = sum(v["count"] for v in freq.values())
    unique_types = len(freq)
    log.append(f"📊 Community corpus: {total_contributions} gap instances across {unique_types} pattern type(s)")
    qualified = {k: v for k, v in freq.items() if v["unique_sources"] >= min_sources}
    log.append(f"✅ {len(qualified)} pattern type(s) meet threshold (≥{min_sources} independent sources)")
    templates = build_community_templates(min_sources=min_sources)
    if not templates:
        log.append("ℹ️ No new templates to publish (insufficient data or no new signals).")
        return [TextContent(type="text", text="\n".join(log))]
    log.append(f"🧠 Derived {len(templates)} enhanced template(s)")
    ok = push_community_templates(templates)
    if ok:
        log.append(f"⬆️ Published {len(templates)} template(s) to community dataset")
    else:
        log.append("⚠️ Could not publish templates (check HF_TOKEN and dataset permissions)")
    return [TextContent(type="text", text="\n".join(log))]


def main() -> None:
    async def _run():
        async with stdio_server() as streams:
            # Set our package version on InitializationOptions rather than the
            # Server() constructor — the latter's `version=` kwarg is not present
            # in older mcp SDKs (the package floor is mcp>=1.0.0).
            opts = app.create_initialization_options()
            opts.server_version = __version__
            await app.run(streams[0], streams[1], opts)

    asyncio.run(_run())


if __name__ == "__main__":
    main()
