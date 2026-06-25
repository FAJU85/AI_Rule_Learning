# Changelog

All notable changes to `ai-rule-learning-mcp` are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[0.2.0]: https://github.com/faju85/ai_rule_learning/releases/tag/mcp-v0.2.0
[0.1.1]: https://github.com/faju85/ai_rule_learning/releases/tag/mcp-v0.1.1
[0.1.0]: https://github.com/faju85/ai_rule_learning/releases/tag/mcp-v0.1.0
