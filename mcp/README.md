# AI Rule Learning — MCP

Your AI remembers what works and what doesn't — and gets better every session.

AI Rule Learning watches your AI conversations, learns from the moments where
things didn't go as expected, and automatically applies that knowledge to
future sessions. The result is an AI that progressively adapts to the way you
work, without you having to change anything.

---

## Five pillars

| Pillar        | What it does                                                                             |
| ------------- | ---------------------------------------------------------------------------------------- |
| **Rules**     | Detects friction patterns and generates guardrail rules automatically                    |
| **Memory**    | Persists facts, preferences, and context across all sessions                             |
| **Skills**    | Saves and retrieves reusable multi-step workflows                                        |
| **Injection** | Writes rules, memory, and skills into Claude Code, Cursor, Windsurf, and Copilot configs |
| **Auto-sync** | Installs a nightly cron/systemd job to keep everything current                           |

## MCP tools

| Tool                  | Description                                        |
| --------------------- | -------------------------------------------------- |
| `get_guardrail_rules` | Return active rules for the current session        |
| `record_feedback`     | Create a rule immediately from in-session feedback |
| `sync_sessions`       | Parse conversation history and generate new rules  |
| `remember`            | Store a fact or preference in persistent memory    |
| `recall`              | Search memory for relevant context                 |
| `save_skill`          | Save a reusable workflow                           |
| `list_skills`         | List saved skills with optional keyword filter     |
| `get_skill`           | Retrieve a specific skill by name                  |
| `install_scheduler`   | Install the nightly auto-sync job                  |
| `list_providers`      | Show detected conversation history locations       |

## What it detects

- Explicit corrections ("that's wrong", "actually,")
- Repeated context ("I already told you", "as I said")
- Incomplete responses ("you forgot", "you missed", "what about")
- Repeated questions (word-overlap across turns)
- Code without error handling
- Bare `except:` clauses
- `eval()` usage
- Hardcoded API keys and secrets

## Works with

- Claude Code, Claude Desktop
- ChatGPT / OpenAI exports
- Cursor and Windsurf
- GitHub Copilot
- Any AI tool that exports conversation history

## Installation

```bash
pip install ai-rule-learning-mcp
```

## Quick start

```bash
# Run the MCP server (add to your agent config)
ai-rule-learning-mcp

# Or use the CLI directly
ai-rule-learning sync          # scan sessions and generate rules
ai-rule-learning rules         # show active rules
ai-rule-learning status        # show storage status
ai-rule-learning memory show   # show persistent memory
ai-rule-learning skills list   # show saved skills
ai-rule-learning install-cron  # set up nightly auto-sync
```

## Agent config paths

| Agent          | Config file                          |
| -------------- | ------------------------------------ |
| Claude Code    | `~/.claude/CLAUDE.md`                |
| Cursor         | `.cursor/rules` in the project root  |
| Windsurf       | `.windsurfrules` in the project root |
| GitHub Copilot | `.github/copilot-instructions.md`    |

## Local storage

Everything lives under `~/.ai-rule-learning/`:

```text
~/.ai-rule-learning/
  rules.jsonl          # learned guardrail rules
  memory.jsonl         # persistent memory facts
  processed.jsonl      # record of processed sessions
  skills/              # saved workflows (one .md file each)
```

## Privacy

Conversation content is scrubbed locally (email, home paths, IPs, tokens)
before any storage. Community contributions (opt-in) share only anonymous
pattern counts — never your actual conversations or content.

See [PRIVACY.md](https://github.com/faju85/ai_rule_learning/blob/main/PRIVACY.md)
for full details.

## Licence

Free for personal use. Commercial and government use requires written
permission. See [LICENSE](https://github.com/faju85/ai_rule_learning/blob/main/LICENSE)
and [TERMS.md](https://github.com/faju85/ai_rule_learning/blob/main/TERMS.md).

---

> **For organisations and teams:** a business version is available by
> pre-order. Contact <info@tococolors.com> to request access.
