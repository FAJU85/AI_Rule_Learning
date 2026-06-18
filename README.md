# AI Rule Learning

A platform that learns guardrail rules from real AI conversation failures and
delivers them automatically via an MCP server — so your AI improves with every
session.

**Free for individuals. Commercial/government use requires written permission.**
See [LICENSE](LICENSE) · [TERMS](TERMS.md) · [PRIVACY](PRIVACY.md)

---

## What it does

1. Exports your Claude Code sessions (PII-scrubbed) to a private HF dataset
2. Analyses 7 gap types across all conversations (corrections, frustration, unanswered questions…)
3. Calls `Qwen/Qwen2.5-72B-Instruct` to generate grounded guardrail rules
4. Delivers the rules back via an MCP server that injects them into future sessions automatically

## Quick start — MCP (personal use)

```bash
pip install ai-rule-learning-mcp          # coming soon — build from mcp/ for now
```

Add to your Claude config:

```json
{
  "mcpServers": {
    "ai-rule-learning": {
      "command": "ai-rule-learning-mcp",
      "env": {
        "HF_TOKEN": "hf_your_write_token",
        "ARL_DATASET": "yourname/AI_Rule_Learning"
      }
    }
  }
}
```

Then in Claude: _"Sync my sessions"_ / _"Load my guardrail rules"_.
See [mcp/README.md](mcp/README.md) for full setup.

## Gradio Dashboard (Space)

Live at: <https://huggingface.co/spaces/vooom/AI_Rule_Learning>

Tabs: Overview · Upload History · Import Sessions · Analysis · Rules · How It Works

## Repository overview

This repository provides a project-agnostic development environment template covering:

- **SDLC** — linting, formatting, type checking, git hooks, commit standards, semantic versioning, changelog generation
- **Testing** — unit, integration, end-to-end, coverage reporting
- **Security** — dependency scanning, secret scanning, static analysis, security headers
- **CI/CD** — automated build, test, release, and deployment pipelines
- **SRE** — structured logging, metrics, health checks, tracing, alerting

See [README-DEVELOPMENT-1.md](./README-DEVELOPMENT-1.md) for the full tooling reference across all supported ecosystems.

## Quick Start

```bash
npm install
npm run validate
```

## Scripts

| Script                  | Description                      |
| ----------------------- | -------------------------------- |
| `npm run lint`          | Lint all Markdown files          |
| `npm run lint:fix`      | Auto-fix Markdown lint issues    |
| `npm run format`        | Format all files with Prettier   |
| `npm run format:check`  | Check formatting without writing |
| `npm run validate`      | Run lint + format check          |
| `npm run release`       | Create a release (auto bump)     |
| `npm run release:patch` | Bump patch version               |
| `npm run release:minor` | Bump minor version               |
| `npm run release:major` | Bump major version               |

## Commit Convention

This repository follows [Conventional Commits](https://www.conventionalcommits.org/):

```text
<type>(<scope>): <subject>

Types: feat | fix | docs | style | refactor | perf | test | build | ci | chore | revert
```

Examples:

```text
docs: add python tooling reference
feat: add observability section to dev guide
fix: correct eslint configuration example
```

## CI/CD

| Workflow | Trigger            | Description                             |
| -------- | ------------------ | --------------------------------------- |
| CI       | push / PR          | Lint, format check, commit message lint |
| Security | push / PR / weekly | Secret scanning, dependency audit       |
| Release  | manual dispatch    | Version bump, changelog, git tag        |

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md).

## Changelog

See [CHANGELOG.md](./CHANGELOG.md).
