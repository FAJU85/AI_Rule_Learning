# AI Rule Learning MCP

AI Rule Learning MCP is a local MCP server and CLI for turning repeated AI-session feedback into
persistent guardrails, memory, and reusable skills that can be injected into supported AI-agent
configuration files.

This README describes what is implemented in this repository today. Earlier decision-rule mining
examples have been removed because those public classes are not part of the current package API.

---

## What is real today?

| Capability               | Status          | Implemented as                                                  |
| ------------------------ | --------------- | --------------------------------------------------------------- |
| MCP server               | Real            | `ai-rule-learning-mcp` entry point                              |
| CLI                      | Real            | `ai-rule-learning` entry point                                  |
| Guardrail rules          | Real            | Local JSONL storage plus injected markdown blocks               |
| Memory                   | Real            | Local JSONL storage plus injected markdown blocks               |
| Skills                   | Real            | Local markdown skill files plus injected skill index            |
| Agent config injection   | Real            | Claude Code, Cursor, Windsurf, and GitHub Copilot targets       |
| Auto-sync scheduler      | Real            | LaunchAgent, systemd user timer, or cron fallback               |
| Decision-rule mining API | Not current API | The current package exposes MCP tools and CLI commands instead. |

---

## Installation

```bash
pip install ai-rule-learning-mcp
```

Run the MCP server:

```bash
ai-rule-learning-mcp
```

Run the CLI directly:

```bash
ai-rule-learning status
```

---

## MCP setup

Add the server to an MCP-compatible client configuration:

```json
{
  "mcpServers": {
    "ai-rule-learning": {
      "command": "ai-rule-learning-mcp"
    }
  }
}
```

---

## CLI commands

```bash
# Scan sessions and generate rules
ai-rule-learning sync

# Preview sync without writing local storage or agent config files
ai-rule-learning sync --dry-run

# Show current rules and detected agent configs
ai-rule-learning status

# Print active rules
ai-rule-learning rules

# Review and manage rule lifecycle
ai-rule-learning rules pending
ai-rule-learning rules approve <rule-id>
ai-rule-learning rules reject <rule-id>
ai-rule-learning rules edit <rule-id> "Always run focused tests first"
ai-rule-learning rules merge <primary-rule-id> <duplicate-rule-id>
ai-rule-learning rules outcome <rule-id> --worked
ai-rule-learning rules outcome <rule-id> --failed
ai-rule-learning rules health
ai-rule-learning rules health --apply
ai-rule-learning rules duplicates

# Remove all injected sections
ai-rule-learning clear

# Preview destructive/write operations before changing files
ai-rule-learning clear --dry-run

# Memory
ai-rule-learning memory show
ai-rule-learning memory add preference "Always use type hints in Python"
ai-rule-learning memory add preference "Always use type hints in Python" --dry-run
ai-rule-learning memory clear
ai-rule-learning memory clear --dry-run

# Skills
ai-rule-learning skills
ai-rule-learning skills show "Deploy Workflow"
ai-rule-learning skills delete "Old Workflow"

# Auto-sync scheduler
ai-rule-learning install-cron
ai-rule-learning cron-status
ai-rule-learning uninstall-cron
ai-rule-learning install-cron --dry-run
ai-rule-learning uninstall-cron --dry-run

# Privacy-preserving opt-in metrics
ai-rule-learning metrics status
ai-rule-learning metrics preview
ai-rule-learning metrics enable
ai-rule-learning metrics disable
```

These commands are implemented by the `ai-rule-learning` console script.

Usage metrics are **disabled by default**. If you opt in, the CLI records only anonymous aggregate labels such as
command/tool names, success/failure counts, package version, Python version bucket, and OS family. It never records
prompts, rule text, memory content, file paths, usernames, repo names, hostnames, or agent config content. Run
`ai-rule-learning metrics preview` before enabling sharing to inspect the exact aggregate payload.

---

## Rule generation thresholds and confidence

Rule generation is intentionally local and heuristic. By default, one recognized friction pattern can generate a first-use
rule, which means a single session with clear corrections, repeated context, incomplete-response feedback, or code safety
patterns can produce guardrails immediately. Set `ARL_MIN_RULE_EVIDENCE` to a higher integer if you want rules to require
more repeated evidence before they are created. Generated rules include `evidence_count`, `confidence`, and
`last_observed` indicators so you can tell whether a rule is new, weakly suggested, or repeatedly reinforced.

If no rule is generated, the session did not contain a recognized friction pattern or did not meet `ARL_MIN_RULE_EVIDENCE`.
Pass more session data, lower the threshold, or use `record_feedback` to capture a rule explicitly.

## Network and offline mode

The MCP package is local-first. Network access is only used for optional Hugging Face backup/sync or optional community
template/pattern features. These paths can contact Hugging Face over HTTPS when `HF_TOKEN`, `ARL_DATASET`, contribution,
or community-template loading is enabled. To force zero package-initiated network access, set:

```bash
export ARL_OFFLINE=true
```

With `ARL_OFFLINE=true`, local rule, memory, skill, and conversation storage still works, but Hugging Face upload/download
and community template fetches are disabled. `sync_sessions` reports offline mode at startup so operators can verify the
network posture.

## Known environment notes

Some hosted notebooks include unrelated preinstalled packages that can make `pip check` fail. For example, older Colab
images may include `ipython==7.34.0` without its optional `jedi` dependency. This is environment-specific, not caused by
`ai-rule-learning-mcp`. In those environments, install the missing notebook dependency explicitly:

```bash
python -m pip install jedi
```

## MCP tools

| Tool                      | What it does                                                                          |
| ------------------------- | ------------------------------------------------------------------------------------- |
| `get_guardrail_rules`     | Returns active guardrail rules as a formatted text block.                             |
| `record_feedback`         | Generates a rule from session feedback such as corrections or repeated context.       |
| `sync_sessions`           | Parses supported local session files, detects patterns, and refreshes injected rules. |
| `remember`                | Stores a preference, project detail, hard constraint, user fact, or context item.     |
| `recall`                  | Reads stored memory entries.                                                          |
| `save_skill`              | Saves a reusable workflow.                                                            |
| `list_skills`             | Lists saved workflows.                                                                |
| `get_skill`               | Retrieves a saved workflow by name or keyword.                                        |
| `install_scheduler`       | Installs, uninstalls, or checks the nightly sync scheduler.                           |
| `list_providers`          | Shows detected session sources and agent config targets.                              |
| `list_rules`              | Lists stored rules by lifecycle status.                                               |
| `approve_rule`            | Approves and activates a reviewed rule.                                               |
| `reject_rule`             | Rejects a rule so it is not injected.                                                 |
| `edit_rule`               | Updates a rule instruction.                                                           |
| `merge_rules`             | Marks a duplicate rule as merged into a primary rule.                                 |
| `record_rule_outcome`     | Tracks whether a rule worked or failed.                                               |
| `review_rule_health`      | Finds stale or low-effectiveness rules and can mark them for review.                  |
| `suggest_duplicate_rules` | Suggests likely duplicate rules for explicit review and merge.                        |
| `analyze`                 | Reports health, failure modes, injection checks, and rule-effectiveness data.         |

---

## What gets written where

Rules, memory, and skills are injected as fenced markdown blocks using HTML comment markers into
every detected supported AI-agent config.

| Agent          | Config file                                |
| -------------- | ------------------------------------------ |
| Claude Code    | `~/.claude/CLAUDE.md`                      |
| Cursor         | `~/.cursor/rules/ai-guardrails.md`         |
| Windsurf       | `~/.windsurf/rules/ai-guardrails.md`       |
| GitHub Copilot | `~/.config/github-copilot/instructions.md` |

All sections are idempotent: re-running sync updates existing blocks instead of duplicating them.

Remove injected sections with:

```bash
ai-rule-learning clear
```

---

## Local storage

All local data is stored under `~/.ai-rule-learning/`:

```text
~/.ai-rule-learning/
  rules.jsonl          Active guardrail rules
  memory.jsonl         Remembered facts and preferences
  conversations.jsonl  Parsed session history
  processed.jsonl      Deduplication index
  skills/              Saved skill procedures, one markdown file per skill
  sync.log             Auto-sync output
```

---

## Auto-sync scheduler

The scheduler is opt-in. It is only installed when you run:

```bash
ai-rule-learning install-cron
```

Depending on your OS, the package uses one of these mechanisms:

| OS    | Mechanism                                         |
| ----- | ------------------------------------------------- |
| macOS | LaunchAgent                                       |
| Linux | systemd user timer when available, otherwise cron |
| Other | cron fallback when available                      |

Check scheduler status:

```bash
ai-rule-learning cron-status
```

Remove scheduler automation:

```bash
ai-rule-learning uninstall-cron
ai-rule-learning install-cron --dry-run
ai-rule-learning uninstall-cron --dry-run
```

---

## Supported session inputs

The sync command can parse supported local conversation/session files, including Claude Code JSONL
sessions and generic JSONL-style session exports. You can pass a path explicitly:

```bash
ai-rule-learning sync ~/.claude/projects
```

If no path is passed, the CLI checks known default local session locations.

---

## Safety notes

- The tool writes local files when you run write operations such as `sync`, `remember`, `save_skill`,
  `clear`, or scheduler commands.
- The tool updates supported agent config files using explicit HTML comment markers.
- Scheduler installation is opt-in and reversible.
- Use `--dry-run` on write or destructive CLI commands to preview changes before files are modified.
- MCP write tools also accept `dry_run: true` for safe previews of rule refreshes, feedback
  capture, session sync, memory writes, skill saves, and scheduler install/uninstall actions.
- Review generated rules before relying on them for critical workflows; use
  `ai-rule-learning rules pending`, `approve`, `reject`, `edit`, `merge`, and `outcome` to
  manage lifecycle state.
- Do not store secrets as memory entries or skill content.

---

## Blue-green deployments

Production Space releases can be staged in an idle blue/green Hugging Face Space, smoke-tested, and then cut over
through a router webhook with a manual approval gate. See
[Blue-Green Deployment Strategy](docs/BLUE_GREEN_DEPLOYMENT.md) for environment variables, rollback commands, and
migration rules.

## Development

Install development dependencies from the repository root, then run checks:

```bash
python -m pip install -r requirements-dev.txt
ruff format --check .
npm run format:check
ruff check .
mypy src
pytest
python -m pytest -c /dev/null mcp/tests -q
```

---

## License

See `LICENSE` and `TERMS.md` in this repository.
