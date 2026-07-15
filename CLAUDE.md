CLAUDE.md — Universal AI Engineering Operating Standard

Version: 2.1.0
Type: Machine-enforceable contract for autonomous coding agents
Compatibility: Claude Code, Codex, Cursor, Cline, Roo Code, OpenHands, Devin, Gemini CLI, Aider, and future AI coding agents
Architecture: Policy → Workflow → Capability → Validation (4-layer design)

---

Table of Contents

· 0. Scope & Precedence
· 1. Project Identity
· Layer 1: Policy
  · 1.1 Code Quality Policy
  · 1.2 Testing Policy
  · 1.3 Security Policy
  · 1.4 Observability Policy
  · 1.5 Documentation Policy
  · 1.6 Prohibited Actions
· Layer 2: Workflow
  · 2.1 Analysis Phase
  · 2.2 Planning Phase
  · 2.3 Implementation Phase
  · 2.4 Verification Phase
  · 2.5 Documentation Phase
  · 2.6 Completion Phase
· Layer 3: Capability Profiles
· Layer 4: Project Profile Matrix
· Reference Files
  · Tool Decision Matrix
  · Validation Matrix
· Agent Compatibility
· Testing Requirements
· Commit, Branching & Security
· Handling Ambiguity, Failure & Non-Recoverable State
· End-of-Session Report
· Initialization
· Maintenance
· Changelog

---

0. Scope & Precedence

1. This document governs human developer onboarding and all agent behavior in this repository.
2. Order of precedence when instructions conflict:
      User instruction (current turn) > CLAUDE.md > Agent's training defaults
3. If any rule is unclear or conflicts with a user request, do not silently reinterpret. Surface the conflict and defer (see Handling Ambiguity, Failure & Non-Recoverable State).
4. This standard is framework-agnostic, profile-driven, and tool-aware. All tool choices are derived from project profile and language ecosystem.
5. Reference data (capability definitions, tool matrices, validation criteria) are maintained in separate files under .agents/ (see Reference Files).

---

1. Project Identity

Field Value Description
Project Name ai-rule-learning Repository name
Primary Profile Hugging Face Space From Profile Matrix
Language(s) Python Primary language(s)
Runtime(s) Python 3.10 Runtime environment(s)
Package Manager pip Dependency manager
Default Branch main Main development branch
Deployment Target Hugging Face Spaces Production environment
Coverage Threshold 80 Minimum test coverage %
Branch Prefixes feat, fix, chore, docs, style, refactor, perf, test, build, ci, revert Allowed prefixes

---

Layer 1: Policy

No tool names appear in this layer. Tools are selected in reference files based on capabilities.

1.1 Code Quality Policy

Rule Enforcement
Formatting All code must be automatically formatted. No manual whitespace adjustments.
Linting All code must pass static analysis. No lint errors (warnings may be allowed per project).
Type Safety All code must pass strict type checking. No use of unsafe type escapes.
Naming Use descriptive, intention-revealing names. Abbreviations only if widely known.
Complexity Keep functions small and focused. Prefer composition over inheritance.

1.2 Testing Policy

Rule Enforcement
Unit Tests All pure logic must be unit tested. No external I/O.
Integration Tests All module interactions must be integration tested. Use test containers or mocks.
E2E Tests Critical user journeys must be E2E tested. Use real dependencies.
Regression Tests Bug fixes require a test that fails before the fix and passes after.
No Skipping Never delete or skip failing tests. Fix or quarantine them.
Coverage Maintain minimum coverage threshold (default 80%).

1.3 Security Policy

Rule Enforcement
Secrets Never commit secrets to version control. Use environment variables.
Dependencies Scan all dependencies for vulnerabilities. Block critical findings.
SAST Run static application security testing on all code changes.
Input Validation Validate and sanitize all user inputs.
Authentication Use established auth protocols (OAuth2, JWT, etc.). Never roll custom crypto.
Output Encoding Encode all output to prevent injection attacks.

1.4 Observability Policy

Rule Enforcement
Logging Use structured logging (JSON/key-value). Never use console.log/print in production code.
Health Checks Expose liveness and readiness endpoints for orchestration.
Metrics Export key business and system metrics.
Tracing Trace distributed transactions where applicable.
Alerting Configure alerts for critical failures and performance degradation.

1.5 Documentation Policy

Rule Enforcement
Comments Explain why, not what. Don't narrate code.
API Docs Document all public APIs (OpenAPI, GraphQL schema, etc.).
Architecture Record significant decisions (ADR format).
README Keep README up to date with setup and usage instructions.
Changelog Maintain changelog for versioned releases.

1.6 Prohibited Actions

The agent must never:

· Rewrite git history on shared branches without explicit approval.
· Run destructive shell commands (rm -rf, DROP TABLE, etc.) outside scratch paths.
· Install global packages or modify host machine outside the repo.
· Generate placeholder/lorem content in user-facing strings without marking as placeholder.
· Claim task complete when verification gate hasn't been run.
· Modify CLAUDE.md without explicit instruction.
· Disable or weaken security/type checks to bypass gate failures.

---

Layer 2: Workflow

Framework-agnostic development workflow. No tool-specific requirements.

2.1 Analysis Phase

1. Understand the requirement or user request.
2. Identify affected capabilities (see Layer 3: Capability Profiles).
3. Assess impact on existing code, tests, and infrastructure.
4. Determine if change touches public contracts, migrations, or shared components.

2.2 Planning Phase

1. Design solution approach.
2. Identify new dependencies (justify each addition).
3. Map changes to existing tests and capabilities.
4. Check health endpoints, monitoring, and alerting implications.

2.3 Implementation Phase

1. Write code following policy rules (Layer 1).
2. Add/update tests per Testing Requirements.
3. Update logging, metrics, and tracing as needed.
4. Document changes inline and in relevant docs.

2.4 Verification Phase

Must run before declaring any task complete, staging files, or opening PR:

```bash
ruff format --check .       # format:check (Python)
ruff check .                # lint
mypy src                    # typecheck
pytest                      # test
pytest tests/e2e            # test:e2e — only if changes affect critical flows
```

All must pass. Coverage must stay ≥ 80% (see Validation Matrix).

2.5 Documentation Phase

1. Update API documentation for changed endpoints.
2. Record architectural decisions (if significant).
3. Update README/CHANGELOG as needed.
4. Document migration steps (if applicable).

2.6 Completion Phase

1. Commit with Conventional Commit message (see Commit, Branching & Security).
2. Push to feature branch.
3. Open PR or deploy (if approved).

---

Layer 3: Capability Profiles

Defines engineering capabilities independent of tools. Tools are assigned in the Tool Matrix based on language and profile. See .agents/capabilities.md for complete definitions.

Core Capabilities Summary

Group Capabilities
Code Quality Formatting, Linting, Type Safety
Testing Unit Testing, Integration Testing, E2E Testing, Coverage
Security Secret Scanning, Dependency Scanning, SAST, DAST, Container Scanning
Reliability Logging, Metrics, Health Checks
Observability Tracing, Monitoring, Alerting
Performance Frontend Performance, Backend Performance, Load Testing, Benchmarking
Accessibility WCAG Validation, Accessibility Audits
Documentation API Documentation, Architecture Documentation
AI/LLM Evaluation, Tracing, Prompt Testing, Guardrails, Model Validation

---

Layer 4: Project Profile Matrix

Maps project types to required capabilities using explicit notation: Required/X where X = total capabilities in that group.

Legend: R/X = Required (X of X capabilities), O = Optional, N/A = Not Applicable

Profile Code Quality (3) Testing (4) Security (5) Reliability (3) Observability (3) Performance (4) Accessibility (2) Documentation (2) AI/LLM (5)
Backend API R/3 R/4 R/5 R/3 R/3 O N/A R/2 N/A
Frontend Web R/3 R/4 O R/3 O R/4 R/2 R/2 N/A
Next.js R/3 R/4 O R/3 O R/4 R/2 R/2 N/A
React R/3 R/4 O O O R/4 R/2 R/2 N/A
Mobile (React Native) R/3 R/4 O R/3 O R/4 R/2 R/2 N/A
CLI Tool R/3 R/4 O O N/A O N/A R/2 N/A
Worker/Background R/3 R/4 O R/3 O O N/A R/2 N/A
Microservice R/3 R/4 R/5 R/3 R/3 R/4 N/A R/2 N/A
Telegram Bot (Standard) R/3 R/4 O R/3 R/3 O N/A R/2 O
Telegram Bot (Production-Critical) R/3 R/4 R/5 R/3 R/3 R/4 N/A R/2 O
Telegram Mini App R/3 R/4 R/5 R/3 R/3 R/4 R/2 R/2 O
Discord Bot R/3 R/4 O R/3 R/3 O N/A R/2 O
Slack Bot R/3 R/4 O R/3 R/3 O N/A R/2 O
Hugging Face Space R/3 R/4 O R/3 O O R/2 R/2 O
HF Model Training R/3 O O O O R/4 N/A R/2 R/5
HF Dataset R/3 O O O O O N/A R/2 O
HF Inference Endpoint R/3 R/4 R/5 R/3 R/3 R/4 N/A R/2 R/5
AI Agent R/3 R/4 R/5 R/3 R/3 R/4 R/2 R/2 R/5
Infrastructure/DevOps R/3 O R/5 R/3 R/3 R/4 N/A R/2 N/A
Smart Contract / On-Chain R/3 R/4 R/5 R/3 R/3 O N/A R/2 N/A
Data Pipeline / ETL R/3 R/4 R/5 R/3 R/3 R/4 N/A R/2 N/A
Trading Bot / Financial Infrastructure R/3 R/4 R/5 R/3 R/3 R/4 N/A R/2 O

---

Reference Files

To keep CLAUDE.md focused on policy and workflow, reference data is maintained in separate files:

File Content Path
Capability Definitions Complete capability descriptions and mapping .agents/capabilities.md
Tool Decision Matrix Language-specific tool selection .agents/tools.md
Validation Matrix Single source of truth for pass/fail .agents/validation.md

Tool Decision Matrix

See .agents/tools.md for the complete matrix. Below is a summary of tool selection rules.

Tool Selection Rules

1. Use the Required tool by default.
2. If the project already uses an Optional or Alternative tool listed for the same capability, keep it — do not migrate.
3. Never combine two tools serving the same capability (e.g., do not run ESLint + Biome together).
4. Introducing a tool outside the matrix requires explicit user approval and an ADR.

Tool Matrix Summary

Capability TypeScript/JS Python Go Java Rust
Formatting Prettier Black gofmt Google Java Format rustfmt
Linting ESLint Ruff golangci-lint Checkstyle Clippy
Type Safety TypeScript mypy Built-in Javac -Xlint Built-in
Unit Testing Vitest pytest go test JUnit cargo test
E2E (Web) Playwright Playwright Playwright Playwright Playwright
Secret Scanning Gitleaks Gitleaks Gitleaks Gitleaks Gitleaks
Dep Scanning npm/pnpm audit pip-audit govulncheck OWASP DC cargo audit
SAST Semgrep Semgrep Semgrep Semgrep Semgrep
Logging Winston structlog slog Logback env_logger
Metrics Prometheus Prometheus Prometheus Prometheus Prometheus
Tracing OpenTelemetry OpenTelemetry OpenTelemetry OpenTelemetry OpenTelemetry

Validation Matrix

See .agents/validation.md for the complete validation criteria. All pass/fail conditions are centralized there.

Validation Summary

Capability Pass Condition Fail Condition
Formatting format:check returns 0 Any formatting violation
Linting lint returns 0 Any lint error
Type Safety Type checker exits 0 Any type error
Unit Testing All unit tests pass ≥1 failed test
Coverage Coverage ≥ threshold Coverage < threshold
Secret Scanning No secrets detected Any secret match
Dependency Scanning No critical vulnerabilities ≥1 critical vulnerability
SAST No critical/high findings ≥1 critical/high finding
Health Checks All return 200 Any returns non-200

---

Agent Compatibility

Commands classified for autonomous execution.

Morph MCP Tool Guidance

When Morph MCP tools are available in the active editor session:

· Use `edit_file` over `str_replace` or full-file rewrites. It supports partial code snippets and does not require full file content.
· Use `warpgrep_codebase_search` for broad semantic codebase exploration at the start of investigations, such as finding auth flows, billing flows, or error origins.


Agent-Safe (Headless, Autonomous)

```bash
# Code Quality
ruff format --check .
ruff check .
mypy src

# Testing (headless)
pytest
pytest --cov=src --cov-report=term-missing
pytest tests/e2e          # CI-compatible

# Build & Deploy (if automated)
# (deployment is handled by Hugging Face Spaces on push)

# Security
pip-audit
gitleaks detect --source .   # if configured
```

Human-Only (Requires GUI/Manual)

```bash
npm run release:*            # Version bumps (operator only)
```

Agent must not invoke human-only commands. Suggest user runs them manually.

Release Escalation

The agent must never invoke release:* commands directly. If a release is required, the agent opens a draft PR with title `chore(release): proposed <version>` containing the changelog diff and tags @maintainer for human approval. The agent then proceeds with other work; release execution is the human operator's responsibility.

---

Testing Requirements

Change Type Required Tests
New pure function/utility Unit tests
New API route/handler Integration + (if public) E2E
New UI component DOM unit tests + E2E (critical flows)
Bug fix Regression test (fails before fix)
Refactor (no behavior change) Existing tests must pass
New dependency Security audit must pass

Rules:

· Tests live next to source (foo.py → foo_test.py) or in mirrored tests/ directory. Pick one and be consistent.
· Never delete or skip failing tests to Fix or quarantine.
· External network calls must be mocked.

---

Commit, Branching & Security

Commits

· Conventional Commits 1.0.0 specification
· Allowed commit types: feat, fix, chore, docs, style, refactor, perf, test, build, ci, revert
· Breaking changes use the ! suffix or BREAKING CHANGE: footer
· One logical change per commit
· Never commit directly to main
· Use feat, fix, chore, docs, style, refactor, perf, test, build, ci, revert/<short-slug> branches (e.g., feat/user-onboarding)

AI Authorship

Option A (explicit attribution): Every agent-authored commit must include trailer:

```text
Co-Authored-By: Claude <noreply@anthropic.com>
```

Secrets

· Never commit `.env`, `.env.*`, `*.pem`, `*.key`, service-account JSON, etc.
· Use environment variables; document in .env.example
· Secret scanner findings = gate failure

Dependencies

· Justify every new dependency
· Run security audit after any add
· Block on critical findings

Off-Limits Zones (Read-only without explicit approval)

· .github/workflows/**
· .husky/**
· CODEOWNERS, LICENSE, SECURITY.md
· infrastructure/, terraform/, k8s/ (if present)
· Lockfiles (only as side effect of install)
· Shipped migration files (additive new migrations are fine)

---

Handling Ambiguity, Failure & Non-Recoverable State

Situation Required Behavior
Ambiguous requirement Make minimum reasonable assumption; state it in report; proceed
Recoverable failure Retry up to 2 times. If still failing, treat as unrecoverable
Unrecoverable component Quarantine: isolate, mark `// AGENT-QUARANTINE: <reason> <date>`, ensure rest passes, defer in report
Conflict user instruction vs CLAUDE.md Defer; surface conflict; let user resolve
Scope creep Complete original task; list additional work in report; don't expand silently

Do not halt for small ambiguities. Halting reserved for: missing credentials, destructive operations, off-limits file edits, explicit conflicts.

---

End-of-Session Report

Every non-trivial session ends with:

```markdown
## Session Report

### Completed
- <finished items with commit SHAs>

### Verification Gate
- format:check: PASS / FAIL
- lint:        PASS / FAIL
- typecheck:   PASS / FAIL
- test:        PASS / FAIL (coverage: X%)
- test:e2e:    PASS / FAIL / SKIPPED (reason)

### Assumptions Made
- <each assumption>

### Quarantined
- <path>: <reason> — deferred

### Deferred / Out of Scope
- <items not done>

### Follow-Ups Recommended
- <next steps>
```

A session with a failing gate must state so plainly.

---

Initialization

Execute in order. Halt on first non-recoverable failure:

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
cp .env.example .env            # if .env doesn't exist
mypy src
ruff check .
pytest
```

All verification commands must pass. If not, report as repo-state bug.

---

Maintenance

If the agent encounters recurring ambiguity not covered here, propose an amendment in the End-of-Session Report — phrased as a concrete clause with section. User accepts or rejects; agent does not self-edit.

---

Changelog

v2.1.0 — 2026-06-21

Fixed:

· Profile Matrix notation: replaced ambiguous R/RR/RRR with explicit Required/X notation (Task 1.1)
· Dead section references: converted all §N to named anchors (Task 1.2)
· Tool selection ambiguity: added Tool Selection Rules subsection (Task 1.3)

Added:

· Reference files: split matrices into .agents/capabilities.md, .agents/tools.md, .agents/validation.md (Task 2.1)
· Conventional Commit types enumerated (Task 2.2)
· Branch prefixes placeholder (Task 2.3)
· Release escalation path for unattended sessions (Task 2.4)
· AI-authorship trailer policy — Option A selected (explicit Co-Authored-By trailer) (Task 2.5)
· New project profiles: Smart Contract, Data Pipeline, Trading Bot (Task 3.1)
· Split Telegram Bot into Standard and Production-Critical profiles (Task 3.2)
· In-file changelog section (Task 3.3)

Changed:

· Profile Matrix from R/RR/RRR to explicit Required/X notation
· Section references from §N to named anchors

v2.0.0 — 2026-06-20

· Initial 4-layer architecture (Policy → Workflow → Capability → Validation)
· Framework-agnostic design
· Multi-language support (TypeScript, Python, Go, Java, Rust)
· 21 project profiles
· AI/LLM tooling support
· Single source of truth validation matrix

---

End of CLAUDE.md
