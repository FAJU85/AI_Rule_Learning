# AI Rule Learning MCP Tool & API Reference

**Package**: `ai-rule-learning-mcp`  
**Version**: `0.2.1`  
**Reference Document**: ARL-REM-2026-007  
**Total Registered MCP Tools**: 21

---

## 1. Overview

The `ai-rule-learning-mcp` server exposes 21 standard Model Context Protocol (MCP) tools over `stdio`. It runs with zero runtime overhead and requires no mandatory cloud credentials. All tools operate within strict safety, privacy, and budget boundaries.

---

## 2. Complete 21 Tool Catalog

### 1. `get_guardrail_rules`

- **Description**: Return personal AI guardrail rules as a formatted markdown block. Loads context-aware selected rules capped at $\le 10$ rules and $\le 500$ tokens. Writes to detected agent configs (`CLAUDE.md`, `.cursorrules`, etc.).
- **Parameters**:
  - `dry_run` _(boolean, optional)_: Preview rules without writing to disk.
  - `context` _(object, optional)_: Explicit conversation context overrides (`language`, `task_type`, etc.).
  - `conversation` _(array/object, optional)_: Conversation turns to auto-detect context.

### 2. `record_feedback`

- **Description**: Record real-time user correction, preference, or friction. Immediately extracts a rule with two-stage prompt injection defense, recursive PII scrubbing, and distinct slot allocation.
- **Parameters**:
  - `feedback_type` _(string, required)_: One of `"correction"`, `"preference"`, `"repeated_context"`, `"incomplete_response"`.
  - `description` _(string, required)_: Description of what happened.
  - `rule_hint` _(string, optional)_: Suggested countermeasure.
  - `dry_run` _(boolean, optional)_: Preview without writing to `rules.jsonl`.

### 3. `sync_sessions`

- **Description**: Scan local session directories (Claude Code, ChatGPT, generic JSONL), extract recurring friction patterns, generate guardrail rules with full 7-field provenance, and write to agent configs.
- **Parameters**:
  - `paths` _(array of strings, optional)_: Custom directories to scan.
  - `contribute` _(boolean, optional)_: Submit anonymized gap counts to community relay (default: false).
  - `dry_run` _(boolean, optional)_: Preview extraction without modifying configs.

### 4. `remember`

- **Description**: Persist a key user fact, preference, or project stack convention into local memory across all AI sessions.
- **Parameters**:
  - `content` _(string, required)_: Fact or instruction to remember.
  - `type` _(string, optional)_: `"preference"`, `"project"`, `"never"`, `"user_info"`, `"context"`.

### 5. `recall`

- **Description**: Load all persisted facts, preferences, and stack context grouped by category.
- **Parameters**: None.

### 6. `install_scheduler`

- **Description**: Install, query status, or uninstall an automated background sync job (LaunchAgent on macOS, systemd user timer on Linux, cron fallback).
- **Parameters**:
  - `action` _(string, optional)_: `"install"`, `"status"`, or `"uninstall"`.
  - `dry_run` _(boolean, optional)_: Preview scheduler configuration.

### 7. `list_providers`

- **Description**: Inspect local machine to detect installed AI agents (Claude Code, Cursor, Windsurf, Copilot, Codex) and available session log sources.
- **Parameters**: None.

### 8. `save_skill`

- **Description**: Save a reusable multi-step workflow procedure to `~/.ai-rule-learning/skills/`.
- **Parameters**:
  - `name` _(string, required)_: Unique identifier slug.
  - `description` _(string, required)_: High-level purpose.
  - `steps` _(string or array of strings, required)_: Step-by-step instructions.

### 9. `list_skills`

- **Description**: List all stored reusable procedural skills (names and descriptions).
- **Parameters**: None.

### 10. `get_skill`

- **Description**: Retrieve the full instruction steps for a stored procedural skill and increment its usage counter.
- **Parameters**:
  - `name` _(string, required)_: Skill name or search keyword.

### 11. `list_rules`

- **Description**: Query stored rules filtered by lifecycle status.
- **Parameters**:
  - `status` _(string, optional)_: `"all"`, `"active"`, `"pending"`, `"rejected"`, `"inactive"`, `"stale"`, `"needs_review"`, `"merged"`.

### 12. `approve_rule`

- **Description**: Approve a pending or reviewed rule, transitioning its `review_status` to `"approved"` and `status` to `"active"`. Records reviewer provenance (`reviewed_by`, `reviewed_at`).
- **Parameters**:
  - `rule_id` _(string, required)_: Rule identifier.
  - `dry_run` _(boolean, optional)_: Preview activation.

### 13. `reject_rule`

- **Description**: Reject a stored rule, setting `review_status` to `"rejected"` and `is_active` to `false`. Prevents rule injection and community propagation.
- **Parameters**:
  - `rule_id` _(string, required)_: Rule identifier.
  - `note` _(string, optional)_: Review note explaining rejection rationale.
  - `dry_run` _(boolean, optional)_: Preview rejection.

### 14. `edit_rule` ⚠️ Special Policy Constraints

- **Description**: Update rule metadata fields without modifying the instruction text.
- **Policy Enforcement**: **Instruction modification is strictly prohibited.** Rule instruction text is static and drawn from verified literature (`data/catalog_v1.json`) to prevent prompt injection and instruction drift. Any call attempting to modify `instruction` is immediately rejected.
- **Parameters**:
  - `rule_id` _(string, required)_: Rule identifier to update.
  - `priority` _(integer, optional)_: Updated priority rating (1 to 5).
  - `trigger_if` _(object, optional)_: Updated context activation mapping.
  - `exclude_if` _(object, optional)_: Updated context suppression mapping.
  - `instruction` _(string, prohibited)_: Prohibited argument. Non-empty values return an error.
  - `dry_run` _(boolean, optional)_: Preview metadata update.

### 15. `merge_rules`

- **Description**: Mark a duplicate rule as merged into a primary rule.
- **Parameters**:
  - `primary_rule_id` _(string, required)_: Target rule to retain.
  - `duplicate_rule_id` _(string, required)_: Redundant rule to mark merged.
  - `dry_run` _(boolean, optional)_: Preview merge.

### 16. `record_rule_outcome`

- **Description**: Record empirical hit/miss feedback when a rule fired during a task, updating its `effectiveness_score`.
- **Parameters**:
  - `rule_id` _(string, required)_: Rule identifier.
  - `worked` _(boolean, required)_: `true` if rule succeeded; `false` if rule failed or was bypassed.
  - `dry_run` _(boolean, optional)_: Preview outcome update.

### 17. `suggest_duplicate_rules`

- **Description**: Inspect active and pending rules using local semantic similarity to surface redundant candidates for merging.
- **Parameters**:
  - `threshold` _(number, optional)_: Similarity cutoff $[0.0, 1.0]$ (default: 0.82).

### 18. `review_rule_health`

- **Description**: Identify stale rules, zero-effectiveness rules, or unreviewed rules.
- **Parameters**:
  - `apply` _(boolean, optional)_: Automatically deactivate stale rules.
  - `dry_run` _(boolean, optional)_: Preview health assessment.

### 19. `analyze`

- **Description**: Multi-action analysis engine for session health, failure taxonomy classification, and prompt injection detection.
- **Parameters**:
  - `action` _(string, optional)_: `"all"`, `"health"`, `"failure_modes"`, `"check_injection"`, `"effectiveness"`.
  - `prompt` _(string, optional)_: Text to scan when `action="check_injection"`.

### 20. `update_community_knowledge`

- **Description**: Pull verified k-anonymity templates from Cloudflare R2 CDN, update local template cache, and augment RAG generation.
- **Parameters**:
  - `min_sources` _(integer, optional)_: Source threshold (default: 3 local / 5 edge).

### 21. `why`

- **Description**: Inspect active guardrails and display the exact context activation reasoning for each selected rule.
- **Parameters**: None.
