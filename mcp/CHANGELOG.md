# Changelog

All notable changes to `ai-rule-learning-mcp` are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Fine-tuning dataset exporter (Phase 4, optional/opt-in).** A new
  `ai-rule-learning export-dataset` command (and `dataset.export_sft_jsonl`)
  turns the learned rules corpus into a standard SFT JSONL file for external,
  opt-in fine-tuning (e.g. Unsloth on a GPU/Colab). Pure data transformation —
  no `torch`/`transformers`/`unsloth` dependency, no training in CI. The export
  is instruction-style (directive + grounded correction); a true DPO/preference
  dataset is intentionally not fabricated, as the corpus does not store
  before/after transcripts. See `docs/fine-tuning.md` for scope, limits, and the
  training recipe.
- **Semantic clustering of community signals (Phase 3).** A new dependency-free
  clustering module (single-linkage TF-IDF cosine, built on the Phase 1
  similarity module) groups near-duplicate correction signals, so community
  aggregation collapses variants like "add type hints" / "include type hints" /
  "type hints missing" into one canonical trigger instead of listing them
  separately. Wired into `build_community_templates` for both enhanced-builtin
  and newly-discovered patterns; distinct signals are always preserved. (The
  deeper per-cluster k-anonymity would need per-source signal attribution from
  the aggregator, which the Cloudflare Worker does not yet emit.)

- **`AGENTS.md` as a first-class injection target.** Rules are now written to an
  existing `AGENTS.md` at the project root or in the home directory — the
  cross-tool standard read by Codex, Cursor, Zed and a growing set of agents. An
  `AGENTS.md` is honored only when it already exists; one is never created
  unprompted (the same policy as the Cursor/Windsurf flat files).
- **Relevance-based rule selection.** When `get_guardrail_rules` is given task
  context, a user's own rules are ranked by relevance to it (via a dependency-free
  TF-IDF cosine) instead of a flat priority cap, so a large rule set no longer
  starves the rules that matter for the current task. Critical rules are always
  kept and priority is the tiebreak; with no context, behaviour is unchanged.

### Fixed

- **Cross-environment injection for Cursor/Windsurf flat files (M02):** rules now
  reach `~/.cursorrules` and `~/.windsurfrules` even when the server's working
  directory is not the project that holds them. Previously the flat files were
  only ever looked for in the current working directory, so on a machine where
  the server ran from an unrelated cwd they were silently skipped while the
  home-based configs (`CLAUDE.md`, Copilot) still updated — the "injected across
  2/4 environments" result.
- **Store self-heals when its path is a regular file (R05):** if
  `~/.ai-rule-learning` exists as a file instead of a directory, the store now
  moves the stray file aside (preserved as `<name>.corrupt-<timestamp>`),
  recreates the directory, and logs a loud warning, instead of failing silently
  on every read and write (`FileExistsError` was swallowed upstream).

## [0.2.6] - 2026-10-22

### Changed

- **Faithful correction capture:** autonomously learned rules now carry the
  user's own correction as an imperative directive (e.g. "you forgot the type
  hints" → "Always include the type hints."), rather than a generic meta-template
  with the correction only attached as `evidence`. This is deterministic (no
  LLM): `distill_directive` strips friction, cuts PII/unrelated tails, and nudges
  a complaint into an imperative; behavioural corrections keep the user's own
  phrasing verbatim. Corrections that yield nothing usable fall back to the
  template, and code-smell gaps (no user utterance) keep their template. Fixes
  the behaviourally-inert "auto == cold" result the 0.2.5 evidence capture did
  not resolve on its own.

### Build

- PyPI releases emit PEP 740 provenance attestations again (the publish step had
  `attestations: false`, which caused a "loss of provenance" warning on 0.2.5).

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

[0.2.6]: https://github.com/faju85/ai_rule_learning/releases/tag/mcp-v0.2.6
[0.2.5]: https://github.com/faju85/ai_rule_learning/releases/tag/mcp-v0.2.5
[0.2.4]: https://github.com/faju85/ai_rule_learning/releases/tag/mcp-v0.2.4
[0.2.3]: https://github.com/faju85/ai_rule_learning/releases/tag/mcp-v0.2.3
[0.2.1]: https://github.com/faju85/ai_rule_learning/releases/tag/mcp-v0.2.1
[0.2.0]: https://github.com/faju85/ai_rule_learning/releases/tag/mcp-v0.2.0
[0.1.1]: https://github.com/faju85/ai_rule_learning/releases/tag/mcp-v0.1.1
[0.1.0]: https://github.com/faju85/ai_rule_learning/releases/tag/mcp-v0.1.0
