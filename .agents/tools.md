.agents/tools.md — Tool Decision Matrix

Parent Document: CLAUDE.md v2.1.0 (Reference Files)
Purpose: This file contains the complete language-specific tool selection matrix referenced by CLAUDE.md.
Standalone: This file should be readable independently of CLAUDE.md.

---

Tool Selection Rules

1. Use the Required tool by default.
2. If the project already uses an Optional or Alternative tool listed for the same capability, keep it — do not migrate.
3. Never combine two tools serving the same capability (e.g., do not run ESLint + Biome together).
4. Introducing a tool outside the matrix requires explicit user approval and an ADR.

---

Capability: Code Quality

Formatting

Language Required Optional Alternative Validation
TypeScript/JS Prettier Biome dprint format:check passes
Python Black Ruff autopep8 No violations
Go gofmt - - gofmt -l empty
Java Google Java Format - - No violations
Rust rustfmt - - No violations

Linting

Language Required Optional Alternative Validation
TypeScript/JS ESLint Biome - lint passes with 0 errors
Python Ruff Pylint Flake8 ruff check passes
Go golangci-lint - - golangci-lint run passes
Java Checkstyle PMD SpotBugs No critical violations
Rust Clippy - - cargo clippy passes

Type Safety

Language Required Optional Alternative Validation
TypeScript/JS TypeScript - - tsc --noEmit passes
Python mypy Pyright - mypy --strict passes
Go Built-in - - go build passes
Java Javac -Xlint:all - - No compilation errors
Rust Built-in - - cargo check passes

---

Capability: Testing

Unit Testing

Language Required Optional Alternative Validation
TypeScript/JS Vitest Jest Mocha+Chai All tests pass
Python pytest unittest - All tests pass
Go go test - - All tests pass
Java JUnit TestNG - All tests pass
Rust cargo test - - All tests pass

Integration Testing

Language Required Optional Alternative Validation
TypeScript/JS Vitest Jest - All tests pass
Python pytest - - All tests pass
Go go test -tags=integration - - All tests pass
Java JUnit + TestContainers - - All tests pass
Rust cargo test - - All tests pass

E2E Testing (Web)

Language Required Optional Alternative Validation
TypeScript/JS Playwright Cypress Selenium Critical journeys pass
Python Playwright Selenium - Critical journeys pass
Go Playwright Selenium - Critical journeys pass
Java Playwright Selenium - Critical journeys pass
Rust Playwright - - Critical journeys pass

E2E Testing (CLI)

Language Required Optional Alternative Validation
TypeScript/JS Bash + expect - - Expected output matches
Python Bash + expect - - Expected output matches
Go Bash + expect - - Expected output matches
Java Bash + expect - - Expected output matches
Rust Bash + expect - - Expected output matches

Coverage

Language Required Optional Alternative Validation
TypeScript/JS Vitest --coverage Jest --coverage - ≥ threshold
Python pytest-cov - - ≥ threshold
Go go test -cover - - ≥ threshold
Java JaCoCo - - ≥ threshold
Rust cargo tarpaulin - - ≥ threshold

---

Capability: Security

Secret Scanning

Language Required Optional Alternative Validation
TypeScript/JS Gitleaks TruffleHog - No secrets detected
Python Gitleaks TruffleHog - No secrets detected
Go Gitleaks TruffleHog - No secrets detected
Java Gitleaks TruffleHog - No secrets detected
Rust Gitleaks TruffleHog - No secrets detected

Dependency Scanning

Language Required Optional Alternative Validation
TypeScript/JS npm/pnpm audit Snyk OWASP DC No critical findings
Python pip-audit Safety - No critical findings
Go govulncheck - - No critical findings
Java OWASP DC - - No critical findings
Rust cargo audit - - No critical findings

SAST (Static Application Security Testing)

Language Required Optional Alternative Validation
TypeScript/JS Semgrep SonarQube CodeQL No critical/high findings
Python Semgrep SonarQube CodeQL No critical/high findings
Go Semgrep SonarQube CodeQL No critical/high findings
Java Semgrep SonarQube CodeQL No critical/high findings
Rust Semgrep - - No critical/high findings

DAST (Dynamic Application Security Testing)

Language Required Optional Alternative Validation
TypeScript/JS OWASP ZAP Burp Suite - No critical findings
Python OWASP ZAP Burp Suite - No critical findings
Go OWASP ZAP Burp Suite - No critical findings
Java OWASP ZAP Burp Suite - No critical findings
Rust N/A - - N/A

Container Scanning

Language Required Optional Alternative Validation
TypeScript/JS Trivy Grype - No critical findings
Python Trivy Grype - No critical findings
Go Trivy Grype - No critical findings
Java Trivy Grype - No critical findings
Rust Trivy Grype - No critical findings

---

Capability: Reliability

Logging

Language Required Optional Alternative Validation
TypeScript/JS Winston Pino Bunyan Structured logs output
Python structlog logging+JSON - Structured logs output
Go slog logrus - Structured logs output
Java Logback Log4j2 - Structured logs output
Rust env_logger tracing - Structured logs output

Metrics

Language Required Optional Alternative Validation
TypeScript/JS Prometheus client OpenTelemetry Datadog /metrics endpoint exposed
Python Prometheus client OpenTelemetry Datadog /metrics endpoint exposed
Go Prometheus client OpenTelemetry Datadog /metrics endpoint exposed
Java Prometheus client OpenTelemetry Datadog /metrics endpoint exposed
Rust Prometheus client OpenTelemetry - /metrics endpoint exposed

Health Checks

Language Required Optional Alternative Validation
TypeScript/JS Custom endpoints - - /health, /live, /ready respond 200
Python Custom endpoints - - /health, /live, /ready respond 200
Go Custom endpoints - - /health, /live, /ready respond 200
Java Custom endpoints - - /health, /live, /ready respond 200
Rust Custom endpoints - - /health, /live, /ready respond 200

---

Capability: Observability

Tracing

Language Required Optional Alternative Validation
TypeScript/JS OpenTelemetry Jaeger Zipkin Traces exported
Python OpenTelemetry Jaeger Zipkin Traces exported
Go OpenTelemetry Jaeger Zipkin Traces exported
Java OpenTelemetry Jaeger Zipkin Traces exported
Rust OpenTelemetry Jaeger - Traces exported

Monitoring

Language Required Optional Alternative Validation
TypeScript/JS Prometheus+Grafana Datadog New Relic Dashboards exist
Python Prometheus+Grafana Datadog New Relic Dashboards exist
Go Prometheus+Grafana Datadog New Relic Dashboards exist
Java Prometheus+Grafana Datadog New Relic Dashboards exist
Rust Prometheus+Grafana Datadog - Dashboards exist

Alerting

Language Required Optional Alternative Validation
TypeScript/JS Alertmanager PagerDuty Opsgenie Alerts configured
Python Alertmanager PagerDuty Opsgenie Alerts configured
Go Alertmanager PagerDuty Opsgenie Alerts configured
Java Alertmanager PagerDuty Opsgenie Alerts configured
Rust Alertmanager PagerDuty - Alerts configured

---

Capability: Performance

Frontend Performance

Language Required Optional Alternative Validation
TypeScript/JS Lighthouse WebPageTest - Scores ≥ 90
Python N/A - - N/A
Go N/A - - N/A
Java N/A - - N/A
Rust N/A - - N/A

Backend Performance

Language Required Optional Alternative Validation
TypeScript/JS k6 wrk Apache Bench Latency within SLA
Python k6 Locust wrk Latency within SLA
Go k6 wrk Apache Bench Latency within SLA
Java k6 wrk Apache Bench Latency within SLA
Rust k6 wrk Apache Bench Latency within SLA

Load Testing

Language Required Optional Alternative Validation
TypeScript/JS k6 Locust Artillery No regression under load
Python k6 Locust Artillery No regression under load
Go k6 Locust Artillery No regression under load
Java k6 Locust Artillery No regression under load
Rust k6 - - No regression under load

Benchmarking

Language Required Optional Alternative Validation
TypeScript/JS hyperfine benchstat - No significant drop
Python hyperfine benchstat - No significant drop
Go hyperfine benchstat - No significant drop
Java hyperfine benchstat - No significant drop
Rust hyperfine benchstat - No significant drop

---

Capability: Accessibility

WCAG Validation

Language Required Optional Alternative Validation
TypeScript/JS axe-core Lighthouse - No critical violations
Python N/A - - N/A
Go N/A - - N/A
Java N/A - - N/A
Rust N/A - - N/A

Accessibility Audit

Language Required Optional Alternative Validation
TypeScript/JS axe-core + manual - - All required checks pass
Python N/A - - N/A
Go N/A - - N/A
Java N/A - - N/A
Rust N/A - - N/A

---

Capability: Documentation

API Documentation

Language Required Optional Alternative Validation
TypeScript/JS OpenAPI (Swagger) - - Documented endpoints
Python OpenAPI (Swagger) - - Documented endpoints
Go OpenAPI (Swagger) - - Documented endpoints
Java OpenAPI (Swagger) - - Documented endpoints
Rust OpenAPI (Swagger) - - Documented endpoints

Architecture Documentation

Language Required Optional Alternative Validation
TypeScript/JS ADR Markdown - Decisions recorded
Python ADR Markdown - Decisions recorded
Go ADR Markdown - Decisions recorded
Java ADR Markdown - Decisions recorded
Rust ADR Markdown - Decisions recorded

---

Capability: AI/LLM

Evaluation

Language Required Optional Alternative Validation
TypeScript/JS N/A - - N/A
Python DeepEval Ragas - Scores meet threshold

Tracing

Language Required Optional Alternative Validation
TypeScript/JS LangSmith Langfuse - Traces captured
Python LangSmith Langfuse - Traces captured

Prompt Testing

Language Required Optional Alternative Validation
TypeScript/JS Promptfoo - - All variants pass
Python Promptfoo - - All variants pass

Guardrails

Language Required Optional Alternative Validation
TypeScript/JS N/A - - N/A
Python Guardrails AI - - No violations

Model Validation

Language Required Optional Alternative Validation
TypeScript/JS N/A - - N/A
Python DeepEval - - Drift < threshold

---

Language Coverage Summary

Language Coverage
TypeScript/JS All capabilities (25 rows)
Python All capabilities (25 rows)
Go All capabilities except Frontend Performance, WCAG, Accessibility Audit, AI/LLM (19 rows)
Java All capabilities except Frontend Performance, WCAG, Accessibility Audit, AI/LLM (19 rows)
Rust All capabilities except Frontend Performance, WCAG, Accessibility Audit, AI/LLM (18 rows)

---
