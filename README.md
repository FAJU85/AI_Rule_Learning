# AI Rule Learning

Your AI gets smarter every session — automatically.

AI Rule Learning watches how your AI conversations go, spots where things go
wrong, and turns those moments into rules that prevent the same mistakes from
happening again. No manual prompting. No configuration tweaking. It just works
in the background and makes every future session better than the last.

**Free for individuals. Commercial and government use requires written
permission.**
See [LICENSE](LICENSE) · [TERMS](TERMS.md) · [PRIVACY](PRIVACY.md)

---

## What you get

- **An AI that improves with use** — the more you work with it, the better it
  gets at serving your specific needs and preferences
- **Automatic correction** — mistakes and friction points from past sessions
  are caught before they repeat
- **Personalised to you** — rules are built from your actual conversations, not
  generic best practices
- **Works with any AI tool** — Claude, ChatGPT, Cursor, Windsurf, or anything
  that logs conversations

## Get started

```bash
pip install ai-rule-learning-mcp
```

Add to your AI config:

```json
{
  "mcpServers": {
    "ai-rule-learning": {
      "command": "ai-rule-learning-mcp",
      "env": {
        "HF_TOKEN": "your_token_here",
        "ARL_DATASET": "yourname/AI_Rule_Learning"
      }
    }
  }
}
```

Then tell your AI: _"Sync my sessions"_ or _"Load my guardrail rules"_ — and
it handles the rest.

See [mcp/README.md](mcp/README.md) for full setup.

## Dashboard

Explore your rules, review your session history, and run analysis from the
live dashboard:

<https://huggingface.co/spaces/vooom/AI_Rule_Learning>

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md).
