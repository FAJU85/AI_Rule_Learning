.agents/validation.md — Validation Matrix (Single Source of Truth)

Parent Document: AGENTS.md v2.1.0 (Reference Files)
Purpose: This is the single source of truth for all pass/fail criteria.
Usage: The Verification Phase and End-of-Session Report in AGENTS.md defer to this file.
Standalone: This file should be readable independently of AGENTS.md.

---

Validation Matrix

Capability Pass Condition Fail Condition
Formatting ruff format --check . && npm run format:check exit with code 0 Any formatting violation found
Linting ruff check . exits with code 0 (no errors; warnings allowed per project config) Any lint error (not warning)
Type Safety mypy src exits with code 0 Any type error
Unit Testing All unit tests pass (pytest exits 0) ≥1 failed unit test
Integration Testing All integration tests pass (if run) ≥1 failed integration test
E2E Testing All E2E tests pass (run only if changes affect critical flows; see AGENTS.md §2.4) ≥1 failed E2E test or flaky test after 2 retries
Coverage Test coverage ≥ 80% (measured by pytest --cov=src --cov-report=term-missing) Coverage < threshold
Secret Scanning Secret scanner (e.g., Gitleaks) reports zero secrets Any secret match (verified as real)
Dependency Scanning pip-audit reports zero critical vulnerabilities ≥1 critical vulnerability found
SAST Static analysis tool (e.g., Semgrep) reports zero critical or high findings ≥1 critical or high finding
DAST Dynamic analysis (if applicable) reports zero critical findings ≥1 critical finding
Container Scanning Container image scan (e.g., Trivy) reports zero critical findings ≥1 critical finding
Logging No print statements in committed code (enforced by linting); structured logging configuration exists print() or unstructured logging detected
Metrics /metrics endpoint responds with HTTP 200 and valid Prometheus exposition format Endpoint missing, returns non-200, or malformed output
Health Checks All defined health endpoints (/health, /live, /ready) return HTTP 200 Any health endpoint returns non-200
Tracing Traces are exported to configured backend (e.g., OpenTelemetry collector) and appear in tracing UI No traces exported or tracing configuration missing
Monitoring Key dashboards (e.g., Grafana) are updated with relevant metrics Dashboard missing required panels or data
Alerting Alerts fire correctly for defined conditions (tested via dry-run or simulation) Alerts not configured or fail to trigger
Frontend Performance Lighthouse scores (Performance, Accessibility, Best Practices, SEO) ≥ target (default 90) Any core score below target
Backend Performance Latency and throughput meet defined Service Level Agreements (SLAs) Latency > SLA or throughput < SLA
Load Testing No performance regression under target load (e.g., throughput drops ≤5% compared to baseline) Degradation > threshold (default 5%)
Benchmarking Performance (e.g., request latency, memory usage) does not degrade significantly (≤5% drop) Degradation > 5% (or agreed threshold)
WCAG Validation Automated accessibility scans (axe-core) report zero critical violations Any critical violation found
Accessibility Audits All required manual and automated accessibility checks pass Any required check fails
API Documentation All public endpoints are documented (e.g., OpenAPI spec covers all routes) Missing documentation for any public endpoint
Architecture Documentation Significant architectural decisions are recorded as ADRs (Architecture Decision Records) Missing ADR for a major decision (e.g., new dependency, architectural change)
AI Evaluation Model evaluation scores (e.g., accuracy, F1) meet predefined thresholds Scores below threshold
AI Tracing LLM calls and prompts are traced and visible in tracing backend Missing traces for key flows
Prompt Testing All prompt variants pass defined test cases (e.g., output validation) Any variant fails validation
Guardrails No guardrail violations (e.g., safety, compliance) detected Violation detected
Model Validation Model drift (e.g., performance change) is below threshold Drift ≥ threshold

---

Notes

· The Verification Phase in AGENTS.md runs the core gate: ruff format --check ., npm run format:check, ruff check ., mypy src, pytest, and (conditionally) pytest tests/e2e. All other validation items may be executed as part of CI or separate quality gates.
· For any validation item that requires a tool, the tool must be installed and configured as per the Tool Decision Matrix (.agents/tools.md).
· Coverage threshold is 80% project-wide (see AGENTS.md Project Identity).
