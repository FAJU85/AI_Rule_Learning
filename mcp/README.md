# AI Rule Learning — MCP Server

A personal MCP server that learns guardrail rules from your AI conversation
history and injects them into future sessions — automatically, with any AI
provider.

## How it works

```text
Your sessions (any AI tool)
  → MCP reads + scrubs PII locally
  → uploads to YOUR private HF dataset
  → analysis generates personalised rules
  → rules injected into your next session automatically
```

## Supported AI providers

| Provider              | Session format                                           |
| --------------------- | -------------------------------------------------------- |
| **Claude Code**       | `~/.claude/projects/**/*.jsonl` (auto-detected)          |
| **ChatGPT / OpenAI**  | `conversations.json` export                              |
| **Cursor / Windsurf** | Generic JSONL with `{role, content}` messages            |
| **Any tool**          | Generic JSONL — `{role, content}` or `{user, assistant}` |

## Two tiers

### Personal (free, open source)

- Analyses **your** sessions → generates **your** personalised rules
- Data stays in your own private HF dataset — you are the data controller
- Opt in to contribute anonymised gap patterns to the community pool

### Business / Government (licence required)

- Everything in personal PLUS access to aggregated community rules
- Broader ruleset built from collective patterns across all opted-in users
- Higher privacy guarantees for your organisation's own data
- Contact: <info@tococolors.com>

## Installation

```bash
# From source
git clone https://github.com/faju85/ai_rule_learning.git
cd ai_rule_learning/mcp
pip install -e .

# Once published to PyPI
pip install ai-rule-learning-mcp
```

## Configuration

Add to your Claude Desktop / Claude Code MCP config:

```json
{
  "mcpServers": {
    "ai-rule-learning": {
      "command": "ai-rule-learning-mcp",
      "env": {
        "HF_TOKEN": "hf_your_write_token",
        "ARL_DATASET": "yourname/AI_Rule_Learning",
        "ARL_TIER": "personal",
        "ARL_SESSIONS": "/path/to/sessions,/another/path",
        "ARL_CONTRIBUTE": "false"
      }
    }
  }
}
```

### Environment variables

| Variable         | Default              | Description                      |
| ---------------- | -------------------- | -------------------------------- |
| `HF_TOKEN`       | —                    | HF write token (required)        |
| `ARL_DATASET`    | —                    | Your HF dataset repo ID          |
| `ARL_TIER`       | `personal`           | `personal` or `business`         |
| `ARL_SESSIONS`   | `~/.claude/projects` | Comma-separated session paths    |
| `ARL_CONTRIBUTE` | `false`              | Opt in to community contribution |

## Tools exposed to Claude

### `get_guardrail_rules`

Returns your active rules as a formatted system prompt block.

> _"Load my guardrail rules before we start."_

### `sync_sessions`

Scans your session history, scrubs PII, uploads new conversations, pulls
back the latest rules.

> _"Sync my sessions."_
> _"Sync my ChatGPT sessions from ~/Downloads/chat-export"_

### `list_providers`

Shows which session paths are configured and how many files were found.

### `get_community_rules` (business tier only)

Fetches aggregated rules from the community dataset.

## Full automatic loop

```text
Session ends (any AI tool)
  → Stop hook: export_sessions.py --sync-rules
  → conversations uploaded, latest rules saved to ~/.claude/ai_rule_learning_rules.md

Next session starts
  → SessionStart hook reads that file
  → rules injected as context automatically
```

## Privacy

All PII scrubbing runs locally before any data leaves your machine.
Community contributions send only anonymised gap type/count data — never raw text.
See [PRIVACY.md](../PRIVACY.md).

## Licence

Free for personal use. Commercial and government use requires written permission.
See [LICENSE](../LICENSE) and [TERMS.md](../TERMS.md).
