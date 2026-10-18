# Product Requirements Document (PRD)

**Project Name:** AI Rule Learning MCP System (`ai-rule-learning`)  
**Document Version:** 1.0.0  
**Target Release:** v0.3.0  
**Status:** Approved / Active Production Baseline  
**Classification:** Product Specification & Technical Requirements

---

## 1. Executive Summary & Problem Statement

### 1.1 Context & Background

Modern autonomous coding agents (Claude Code, Cursor, Windsurf, GitHub Copilot, Codex, Gemini CLI) frequently exhibit recurrent friction: repetitive operational mistakes, violation of implicit codebase conventions, repeated security anti-patterns, and context drift across multi-turn sessions. Current mitigation strategies rely either on static prompt instructions (e.g., `CLAUDE.md`, `.cursorrules`) manually maintained by human engineers, or naive monolithic context dumps that exhaust LLM context budgets, trigger prompt dilution, and introduce vulnerabilities to prompt injection.

### 1.2 Core Problem Statement

There is no automated, privacy-preserving closed loop that transforms developer corrections, observed tool execution failures, and session friction into deterministic, context-filtered, prompt-injected guardrails without human toil, high token overhead, or centralized security vulnerabilities.

### 1.3 Value Proposition

The AI Rule Learning System provides a local Model Context Protocol (MCP) server and automated ingestion pipeline that:

1. Detects repeated operational mistakes and extracts actionable rules from live sessions.
2. Selects at most **10 rules** within a strict **500-token ceiling** tuned specifically to the immediate project context (language, framework, tooling, git changes).
3. Injects guardrails transparently into standard agent configuration files (`CLAUDE.md`, `.cursorrules`, `.windsurfrules`, `.github/copilot-instructions.md`).
4. Contributes scrubbed, k-anonymized failure telemetry to a zero-trust community knowledge catalog hosted on Cloudflare R2 via an Edge Worker relay, without requiring third-party API tokens (zero `HF_TOKEN` requirement for consumption).

---

## 2. Target Users & Stakeholders

| Persona                          | Role                                                     | Core Need                                             | Key Friction / Risk                                     |
| -------------------------------- | -------------------------------------------------------- | ----------------------------------------------------- | ------------------------------------------------------- |
| **Autonomous Agent Developer**   | Builds software using agentic IDEs (Cursor, Claude Code) | Agent follows repo conventions without re-prompting   | Token waste, instruction forgetting, hallucinated flags |
| **Engineering Lead / Architect** | Enforces team coding and security standards              | Consistent adherence across all team members' agents  | Rule drift, conflicting instructions, unvetted edits    |
| **Security Engineer**            | Protects repo codebases and developer data               | Prevent PII leakage and indirect prompt injection     | Malicious telemetry poisoned into shared rulesets       |
| **Open Source Contributor**      | Consumes community best practices                        | Access vetted, literature-backed rules out of the box | Dependency lock-in, vendor API token gating             |

---

## 3. Product Principles & Invariants

1. **Deterministic Catalog Immutability:** Instruction text in the literature catalog (`data/catalog_v1.json`) is static, immutable, and citation-backed (DOIs, CWEs, empirical papers). Client nodes cannot mutate canonical instruction text.
2. **Strict Resource Caps:** Dynamic context selection must never exceed **10 rules** or **500 prompt tokens**, preventing context bloat and prompt dilution.
3. **Zero-Trust Telemetry Separation:** Private user edits and session IDs reside exclusively on local disk (`rules.jsonl`). Community telemetry transmits strictly scrubbed failure signals and hashes ($k \ge 5$ quorum) with no reverse PII linkage.
4. **Credential-Free Ingestion & Consumption:** Consuming community templates requires zero authentication tokens (`HF_TOKEN` or cloud API keys). MCP core is strictly decoupled from third-party hubs.
5. **Fail-Closed Governance:** Any rule candidate or telemetry payload exhibiting prompt injection syntax, executable eval/exec markers, or un-scrubbed PII is dropped immediately at the edge.

---

## 4. Functional Requirements

### 4.1 Local MCP Server & Tooling Interface

The system exposes a Model Context Protocol (v1.x) compliant interface registering 21 distinct RPC tools across three functional domains:

#### Governance & Rule Management

- `list_rules(status, category, limit)`: Returns active, pending, or rejected rules with provenance metadata.
- `approve_rule(rule_id)`: Transitions pending candidate rule to `approved` state, updating `reviewed_by` and `reviewed_at`.
- `reject_rule(rule_id)`: Marks rule as `rejected`, preventing active injection.
- `edit_rule(rule_id, ...)`: Updates metadata (`priority`, `trigger_if`, `exclude_if`). **Invariant:** Rejects modifications to canonical instruction text.
- `why(rule_id)`: Explains the empirical rationale, literature source, and trigger activation history for a rule.
- `rules_health()` / `rules_duplicates()`: Detects rule decay, stale effectiveness, and semantic duplicates.

#### Feedback & Telemetry

- `record_feedback(session_id, trigger, action, outcome, gap_type)`: Records explicit user feedback or agent friction, queuing candidate rules with mandatory 7-field provenance.
- `sync_sessions(dry_run)`: Scans recent developer sessions, detects recurrent failures, extracts candidate rules, and updates target agent files.

#### Memory & Skill Index

- `memory_show()` / `memory_add(kind, content)`: Manages cross-session architectural facts and project conventions.
- `skill_index()`: Exposes domain-specific workflows and SOP markdown documentation.

### 4.2 Context-Aware Dynamic Selection Engine

- **Input:** Dynamic context object (`detected_languages`, `frameworks`, `task_type`, `git_modified_files`, `recent_errors`).
- **Processing:**
  1. Score matching against 130-rule catalog based on trigger regex, keyword similarity, and domain tags.
  2. Knapsack/greedy packing constrained by:
     - `Max Rules`: 10
     - `Max Token Budget`: 500 tokens (tiktoken/cl100k_base estimation).
  3. Context diversity enforcement: Distinct project contexts must produce distinct, non-identical rule subsets.
- **Output:** Ordered Markdown block formatted for direct injection into target configuration files.

### 4.3 Agent Configuration Target Injector

The system detects, parses, and safely patches target configuration files using delimited boundary markers:

- `CLAUDE.md` (Anthropic Claude Code)
- `.cursorrules` (Cursor IDE)
- `.windsurfrules` (Windsurf IDE)
- `.github/copilot-instructions.md` (GitHub Copilot)
- Delimiter: `<!-- AI-Rule-Learning:start -->` ... `<!-- AI-Rule-Learning:end -->`
- Reversible operation: `clear` command cleanly strips injected blocks without damaging surrounding user configuration.

### 4.4 Client-Side Security & Scrubbing Pipeline

- **Prompt Injection Defense:** Multi-stage scanner (`scan_injection`) rejecting jailbreaks, role-play overrides, system prompt extraction, and instruction ignores.
- **PII Stripping:** Deterministic regex scrubber (`scrub_pii`) stripping IPv4/IPv6 addresses, email addresses, absolute user home directory paths (`/Users/*`, `/home/*`), API tokens (`sk-*`, `ghp_*`), JWTs, and credit card / SSN patterns.
- **Provenance Enforcement:** Every persisted rule on write path must populate 7 mandatory audit fields:
  1. `source_session_id`
  2. `extraction_version`
  3. `extracted_at`
  4. `review_status` (`pending` | `approved` | `rejected`)
  5. `reviewed_by`
  6. `reviewed_at`
  7. `qa_report_id`

### 4.5 Community Ingestion & Aggregation (Cloudflare Edge)

- **Relay Worker (`POST /contribute`):** Ingests crowd-sourced gap signals, enforces 64 KB payload cap, validates `source_hash` and Zod provenance schema, applies edge rate-limiting (30 req/min per IP), and stages raw objects in private R2 bucket (`arl-learning-raw` / `arl-contributions`).
- **Aggregator Worker (Scheduled Cron):** Reads staged contributions, groups by pattern, enforces $k \ge 5$ distinct source quorum, applies content safety checks, synthesizes confidence ratings, and emits cryptographically signed `manifest.json` and `templates.jsonl` to public R2 bucket (`arl-catalog` / `arl-templates`).

---

## 5. Non-Functional Requirements (NFRs)

| Metric                         | Target                              | Measurement Method                                         |
| ------------------------------ | ----------------------------------- | ---------------------------------------------------------- |
| **MCP Startup Latency**        | $< 400\text{ ms}$                   | Time to respond to `initialize` and `tools/list` handshake |
| **Rule Selection Overhead**    | $< 35\text{ ms}$                    | Execution time of `cat.select(context)` over 130 rules     |
| **Token Budget Compliance**    | $100\%$ compliance $\le 500$ tokens | Automated token count verification in test suite           |
| **Rule Count Ceiling**         | $100\%$ compliance $\le 10$ rules   | Hard ceiling assertion in selection engine                 |
| **Edge Relay Response Time**   | $P_{95} < 75\text{ ms}$             | Cloudflare Worker edge execution duration                  |
| **Edge Payload Ceiling**       | $64\text{ KB}$                      | Hard edge drop with HTTP 413                               |
| **Local Storage Footprint**    | $< 10\text{ MB}$ typical            | Local JSONL rule file size under standard retention        |
| **Python Compatibility**       | Python 3.10, 3.11, 3.12             | Multi-version CI matrix                                    |
| **MCP Protocol Compatibility** | `mcp>=1.0.0,<2.0.0`                 | Pin validation against FastMCP / Model Context Protocol    |

---

## 6. Data Models & Schemas

### 6.1 Local Rule Schema (`rules.jsonl`)

```json
{
  "id": "ARL-SEC-004",
  "category": "security",
  "trigger": "executing shell commands with user input",
  "action": "Always sanitize and pass arguments as structured arrays, never via shell=True string interpolation",
  "evidence": "Observed command injection failure in session sess_98f12a",
  "effectiveness_score": 0.94,
  "created_at": "2026-10-18T04:00:00Z",
  "source_session_id": "sess_98f12a81c0",
  "extraction_version": "0.3.0",
  "extracted_at": "2026-10-18T04:00:05Z",
  "review_status": "approved",
  "reviewed_by": "developer",
  "reviewed_at": "2026-10-18T04:05:00Z",
  "qa_report_id": "QA-2026-LOCAL-001"
}
```

### 6.2 Community Telemetry Schema (`POST /contribute`)

```json
{
  "anonymous_id": "anon_8f91a2e7c41b",
  "source_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "source_session_id": "sess_8f91a2e7c4",
  "extraction_version": "0.3.0",
  "extracted_at": "2026-10-18T14:00:00Z",
  "review_status": "pending",
  "qa_report_id": "QA-RELAY-001",
  "pattern": "always parameterize queries",
  "category": "security",
  "example": "cursor.execute(\"SELECT * FROM users WHERE id = %s\", (user_id,))",
  "confidence": 0.95
}
```

---

## 7. Release Roadmap

- **v0.1.0 (Completed):** Core decision-rule extraction prototype, Hugging Face Spaces demonstration.
- **v0.2.1 (Completed):** 130-rule curated literature catalog, 21 MCP tools, dependency ceiling enforcement (`mcp>=1.0.0,<2.0.0`), PII/injection filters, PyPI publishing.
- **v0.3.0 (Current Baseline):** Cloudflare R2 / Worker zero-trust relay and aggregator deployment (Hono + Zod), 7-field provenance enforcement, empirical LLM benchmarks, 100% SEC-01 through SEC-05 verification.
- **v0.4.0 (Planned):** Automated multi-agent peer voting consensus on rule efficacy, zero-knowledge telemetry proofs.

---

## 8. Documented Production Constraints & Boundaries (v0.3.0)

1. **Scheduled Cron Trigger Verification:** The aggregator cron schedule (`0 */6 * * *`) relies on Cloudflare Workers scheduled event triggers. In automated headless environments, live triggers must be continuously monitored via Cloudflare Logs beyond the manual `/aggregate` and `/trigger-manual` endpoints.
2. **Automated QA Pipeline Scale:** The 12-test automated QA pipeline in the aggregator has been exercised and verified on synthetic corpus and mock R2 boundaries. Live community telemetry under high concurrency and real-world multi-client edge traffic is required to observe long-tail rule synthesis.
3. **HMAC Attestation Rollback:** Cryptographic HMAC attestation of `manifest.json` and `templates.jsonl` is active. However, emergency rollback from an active compromised release to a previous digest has been rehearsed in local staging and needs full automated failover verification during live drills.
4. **1% Traffic Canary Staging:** Canary deployment routing (Stage 4) isolates experimental rules to private staging. Production edge routing with weighted DNS/Cloudflare routing will be formally evaluated as community contributor volume scales.
5. **The 8 Out-of-Scope Catalog Rules:** While 122 of the 130 catalog rules (93.8%) strictly adhere to the 20–40 word envelope (averaging 23.9 words), 8 rules (`logical_fallacy_avoidance`, `regex_efficiency_and_safety`, `async_concurrency_correctness`, `dead_code_and_unused_import_elimination`, `semantic_versioning_compliance`, `iso8601_timestamp_format`, `respectful_boundary_enforcement`, `no_false_intimacy`) are concise imperatives ranging between 16 and 19 words. They are documented, fully cited, and scheduled for minor phrasing expansion in v0.3.1.
