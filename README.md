# AI Rule Learning

Your AI gets smarter every session — automatically.

AI Rule Learning watches how your AI conversations go, spots where things go wrong, and turns
those moments into rules that prevent the same mistakes from happening again. It also remembers
facts about you and saves reusable workflows — so every future session starts with full context.

Works with **Claude Code, Cursor, Windsurf, GitHub Copilot, Codex, and any MCP-compatible
agent**. No manual prompting. No configuration tweaking.

**Free for individuals. Commercial and government use requires written permission.**

See [LICENSE](LICENSE) · [TERMS](TERMS.md) · [PRIVACY](PRIVACY.md)

---

## How it works

Every session, AI Rule Learning builds on five compounding capabilities:

| Pillar                  | What it does                                                                                                                           |
| ----------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| **Rules**               | Detects friction patterns (corrections, repeated context, incomplete responses) and writes guardrail rules to every AI agent config    |
| **Memory**              | Remembers facts about you — preferences, stack, projects, constraints — and loads them at the start of every session                   |
| **Universal injection** | Writes rules and memory into Claude Code, Cursor, Windsurf, and GitHub Copilot configs automatically                                   |
| **Auto-sync**           | Runs nightly via LaunchAgent / systemd / cron — no manual action needed                                                                |
| **Skills**              | Saves repeatable multi-step workflows (e.g. "deploy to HF", "create FastAPI endpoint") so any agent can recall and follow them exactly |

---

## Install

```bash
pip install ai-rule-learning-mcp
```

### Connect to your AI agent

**Claude Code** — add to `~/.claude/claude_desktop_config.json` or `claude_code_config.json`:

```json
{
  "mcpServers": {
    "ai-rule-learning": {
      "command": "ai-rule-learning-mcp"
    }
  }
}
```

**Cursor / Windsurf** — add the same block to your MCP settings file.

**Zero config option** — use the CLI directly without any MCP setup (see below).

---

## MCP tools

Once connected, your AI agent has access to these tools automatically:

| Tool                  | When to call it                                                            |
| --------------------- | -------------------------------------------------------------------------- |
| `get_guardrail_rules` | Start of a session — loads your personalised rules                         |
| `record_feedback`     | When you correct the agent or repeat context — creates a rule in real time |
| `sync_sessions`       | Scans session history, detects patterns, writes rules to all agent configs |
| `remember`            | Stores a fact, preference, or constraint about you                         |
| `recall`              | Loads everything known about you at session start                          |
| `save_skill`          | Saves a multi-step workflow for future reuse                               |
| `list_skills`         | Shows all saved skills (names + descriptions)                              |
| `get_skill`           | Loads the full steps for a saved skill                                     |
| `install_scheduler`   | Installs nightly auto-sync (macOS/Linux)                                   |
| `list_providers`      | Shows which agents and session paths are detected                          |

### Memory types

```text
preference   coding/style/format preference
project      active project or task context
never        hard constraint — something to never do
user_info    fact about you (timezone, role, team size)
context      stack, tools, environment info
```

---

## CLI (zero MCP config required)

```bash
# Scan sessions and generate rules
ai-rule-learning sync

# Show current rules and detected agent configs
ai-rule-learning status

# Print active rules
ai-rule-learning rules

# Remove all injected sections
ai-rule-learning clear

# Memory
ai-rule-learning memory show
ai-rule-learning memory add preference "Always use type hints in Python"
ai-rule-learning memory clear

# Skills
ai-rule-learning skills
ai-rule-learning skills show "Deploy to HuggingFace"
ai-rule-learning skills delete "Old Workflow"

# Auto-sync scheduler
ai-rule-learning install-cron
ai-rule-learning cron-status
ai-rule-learning uninstall-cron
```

---

## What gets written where

Rules, memory, and skills are injected as fenced blocks (using HTML comment markers) into every detected AI agent config:

| Agent          | Config file                                |
| -------------- | ------------------------------------------ |
| Claude Code    | `~/.claude/CLAUDE.md`                      |
| Cursor         | `~/.cursor/rules/ai-guardrails.md`         |
| Windsurf       | `~/.windsurf/rules/ai-guardrails.md`       |
| GitHub Copilot | `~/.config/github-copilot/instructions.md` |

All sections are idempotent — re-running sync updates the block without duplicating it.

---

## Local storage

All data is stored at `~/.ai-rule-learning/`:

```text
~/.ai-rule-learning/
  rules.jsonl          Active guardrail rules
  memory.jsonl         Remembered facts and preferences
  conversations.jsonl  Parsed session history
  processed.jsonl      Deduplication index
  skills/              Saved skill procedures (one .md per skill)
  sync.log             Auto-sync output
```

No data leaves your machine unless you explicitly opt in to community contribution (see below).

---

## Optional: HuggingFace backup

Set environment variables to back up rules to a private HF dataset:

```bash
export HF_TOKEN=hf_...
export ARL_DATASET=yourname/my-rules
```

---

## Optional: community contribution

Opt in to share **anonymised gap pattern counts** (no conversation text, no code) with the
community pool. This improves rule templates for everyone.

```bash
ai-rule-learning sync --contribute
```

Or in MCP: `sync_sessions(contribute=True)`

---

## Privacy

- Raw conversation text **never** leaves your machine
- PII (email, home paths, IPs, tokens) is scrubbed before any storage
- Community contributions contain only gap type, severity, and turn count — nothing else
- See [PRIVACY.md](PRIVACY.md) for the full policy

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).
