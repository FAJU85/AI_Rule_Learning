# Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) and
[Conventional Commits](https://www.conventionalcommits.org/), with versions
managed by [standard-version](https://github.com/conventional-changelog/standard-version).

## [Unreleased]

## [0.2.4] - 2026-10-19

### Fixed

- **Release integrity defect (ARL-BUG-004)**: Resolved packaging discrepancy where the published v0.2.3 wheel on PyPI retained a stale relative path (`Path("active_rules.json")`) rather than the absolute path under `$HOME/.ai-rule-learning/active_rules.json`.
- **Pre-publish CI verification gate**: Added automated zipfile wheel inspection to `.github/workflows/publish.yml` that asserts `_ACTIVE_RULES_PATH` in `ai_rule_learning_mcp/catalog.py` contains `Path.home` or `expanduser` prior to PyPI distribution.
- **Source and location assertion gates**: Added `tests/test_active_rules_constant.py`, `tests/test_wheel_contains_absolute_path.py`, and `tests/test_active_rules_location.py` ensuring active rules always land under `$HOME/.ai-rule-learning/` and never leak into the working directory.

## [0.2.3] - 2026-10-19

### Fixed

- **Active rules path resolution & duplicate write (ARL-BUG-003)**: Resolved `active_rules.json` to `$HOME/.ai-rule-learning/active_rules.json` and removed duplicate call in `server.py` overriding token count.

### Added

- **Skills pillar** (`mcp/ai_rule_learning_mcp/skills.py`) — save and retrieve reusable
  multi-step workflows. Stored as markdown files in `~/.ai-rule-learning/skills/` with
  usage tracking and fuzzy search. MCP tools: `save_skill`, `list_skills`, `get_skill`.
  CLI: `ai-rule-learning skills [list|show|delete]`.
- **Memory pillar** (`mcp/ai_rule_learning_mcp/memory.py`) — persist facts, preferences,
  and context across all sessions and agents. MCP tools: `remember`, `recall`.
  CLI: `ai-rule-learning memory [show|add|clear]`.
- **Universal injection** (`mcp/ai_rule_learning_mcp/injector.py`) — writes rules, memory,
  and skills index to Claude Code, Cursor, Windsurf, and GitHub Copilot configs
  automatically. All sections are idempotent HTML-comment-fenced blocks.
- **Auto-sync scheduler** (`mcp/ai_rule_learning_mcp/scheduler.py`) — installs a nightly
  sync job using LaunchAgent (macOS), systemd user timer (Linux), or cron (fallback).
  MCP tool: `install_scheduler`. CLI: `ai-rule-learning install-cron`.
- **Gap detection and rule generation** (`mcp/ai_rule_learning_mcp/gap_detector.py`) —
  detects friction patterns (explicit corrections, repeated context, incomplete responses,
  repeated questions, code with no error handling) and generates stable SHA-256 keyed rules.
- **Multi-provider session parsing** (`mcp/ai_rule_learning_mcp/providers.py`) — parses
  Claude Code JSONL, ChatGPT/OpenAI export, and generic JSONL formats. PII scrubbed before
  storage.
- **Real-time feedback loop** — `record_feedback` MCP tool creates a rule mid-session
  without waiting for batch sync.
- **Community contribution** (`mcp/ai_rule_learning_mcp/community.py`) — opt-in upload of
  anonymised gap pattern counts (no raw text) to `vooom/AI_Rule_Learning_Community`.
- **MCP server** (`mcp/ai_rule_learning_mcp/server.py`) with 10 tools: `get_guardrail_rules`,
  `record_feedback`, `sync_sessions`, `remember`, `recall`, `save_skill`, `list_skills`,
  `get_skill`, `install_scheduler`, `list_providers`.
- **Standalone CLI** (`mcp/ai_rule_learning_mcp/cli.py`) — full feature parity with the
  MCP server, zero config required: `sync`, `status`, `rules`, `clear`, `memory`, `skills`,
  `install-cron`, `uninstall-cron`, `cron-status`.
- **Test suite** — 170 tests across 9 files covering all modules: unit tests per module,
  provider and store integration tests, and 11 E2E journey tests (sync, feedback, memory,
  skills, combined pillar write/remove with idempotency).
- **README** rewritten to document all five pillars, 10 MCP tools, CLI reference, agent
  config paths, local storage layout, and privacy guarantees.

### Changed

- `mcp/ai_rule_learning_mcp/injector.py` extended to support memory and skills blocks
  alongside the existing rules block; all writes to Claude Code, Cursor, Windsurf, and
  GitHub Copilot configs.

## [0.1.0] — Initial tooling setup

### Added — tooling

- Universal development environment setup reference (`README-DEVELOPMENT-1.md`)
- `package.json` with scripts for linting, formatting, and versioning
- Markdown linting via `markdownlint-cli2` (`.markdownlint.json`)
- Code formatting via `Prettier` (`.prettierrc.json`)
- Git hooks via `Husky` — pre-commit and commit-msg hooks
- Pre-commit validation via `lint-staged`
- Conventional commit enforcement via `commitlint` (`.commitlintrc.json`)
- Semantic versioning via `standard-version` (`.versionrc.json`)
- GitHub Actions CI workflow (lint, format check, commit message lint)
- GitHub Actions Security workflow (secret scanning, dependency audit)
- GitHub Actions Release workflow (manual dispatch, version bump, changelog)
- `README.md` with project overview and usage
- `CONTRIBUTING.md` with development workflow guidelines
- `CHANGELOG.md` (this file)
- `.editorconfig` for editor consistency
- `.gitignore`
