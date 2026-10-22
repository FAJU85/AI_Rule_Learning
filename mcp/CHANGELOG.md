# Changelog

All notable changes to `ai-rule-learning-mcp` are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.5] - 2026-10-22

### Added

- **Grounded rule extraction:** autonomously generated rules now carry the user's
  actual correction text in a new `evidence` field, instead of discarding it in
  favour of generic template wording. Fixes the "auto == cold" defect where
  learned rules were behaviourally inert.
- **Review-before-trust gate:** autonomously learned rules are created as
  `pending_review` / inactive and are not written to agent configs until
  approved. Explicit user feedback (`record_feedback`) remains trusted and is
  activated immediately. Opt-in auto-activation via the `ARL_AUTO_ACTIVATE`
  environment variable.
- **Per-session evidence scoping:** when the same gap type recurs across
  sessions, a rule's `evidence` is drawn from a single session rather than
  co-mingling corrections, while instance counts still aggregate across sessions.

### Changed

- **Community rules backend migrated from the Hugging Face dataset to Cloudflare
  R2.** Reads resolve through an offline override file, then `COMMUNITY_RULES_URL`,
  then the CDN URL, then cache, then the bundled snapshot. The Hugging Face Space
  continues to host the core package and dashboard.
- `sync_sessions` now reports newly generated rules as "(pending review)" with
  approve/reject guidance.

### Removed

- `huggingface-hub` runtime dependency (community sync no longer requires it).

## [0.2.4] - 2026-10-19

### Added

- `CallToolResult` support with structured error handling in `server.py`.
- Regression tests for tool feedback logic.

## [0.2.3] - 2026-10-19

### Fixed

- **Packaging defect (ARL-BUG-004):** `active_rules.json` is now always resolved
  to an absolute path under `~/.ai-rule-learning/`, so relative paths no longer
  persist in distributed wheels.

### Added

- CI wheel-integrity verification that inspects built wheels for the absolute
  `_ACTIVE_RULES_PATH` invariant and required catalog data.

## [0.2.1] - 2026-10-17

### Fixed

- **P0 Remediation (ARL-REM-2026-006):** Declared strict upper bound ceiling `mcp>=1.0.0,<2.0.0` in `pyproject.toml` to prevent package installation failure against incompatible `mcp>=2.0.0` releases.
- Added default install regression test suite in `tests/test_default_install.py`.
- Added compatibility and migration documentation in `docs/mcp-versioning.md`.

## [0.2.0] - 2026-06-25

### Added

- `update_community_knowledge` tool — aggregates contributed gap patterns into
  community templates for RAG augmentation.
- README disclosure of what the tool changes on the machine (config-file writes,
  opt-in scheduler, opt-in cloud upload) and the rule safety gate.

### Changed

- `serverInfo.version` now reports the package version via `InitializationOptions`
  instead of the constructor (compatible with the `mcp>=1.0.0` floor, which does
  not accept a `version=` constructor argument).
- `sync_sessions` log now distinguishes local-only saves from Hugging Face uploads
  via `store.hf_enabled()`.

### Fixed

- **Injection detection (A1):** `check_injection` now normalises whitespace and
  case and uses a filler-tolerant regex, catching variants such as
  "ignore all previous instructions". Regression tests added.

### Security

- Rules are re-checked against the safety gate (`_is_safe_rule`) at the injection
  boundary (`load_active_rules`), so an already-active rule carrying an unsafe
  phrase cannot be written to user agent configs.
- Hugging Face downloads now pass an explicit `revision` (bandit B615).

## [0.1.1] - earlier

- Maintenance release.

## [0.1.0] - earlier

- Initial public release: rules, memory, skills, injection, and auto-sync across
  Claude Code, Cursor, Windsurf, and Copilot.

[0.2.5]: https://github.com/faju85/ai_rule_learning/releases/tag/mcp-v0.2.5
[0.2.4]: https://github.com/faju85/ai_rule_learning/releases/tag/mcp-v0.2.4
[0.2.3]: https://github.com/faju85/ai_rule_learning/releases/tag/mcp-v0.2.3
[0.2.1]: https://github.com/faju85/ai_rule_learning/releases/tag/mcp-v0.2.1
[0.2.0]: https://github.com/faju85/ai_rule_learning/releases/tag/mcp-v0.2.0
[0.1.1]: https://github.com/faju85/ai_rule_learning/releases/tag/mcp-v0.1.1
[0.1.0]: https://github.com/faju85/ai_rule_learning/releases/tag/mcp-v0.1.0
