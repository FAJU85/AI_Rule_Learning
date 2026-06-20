.agents/capabilities.md — Capability Definitions & Profile Matrix

Parent Document: AGENTS.md v2.1.0 (Layer 3)
Purpose: This file contains the complete capability definitions and canonical Project Profile Matrix referenced by AGENTS.md.
Standalone: This file should be readable independently of AGENTS.md.

---

Overview

This document defines all engineering capabilities organized into 9 groups. Each capability includes a description and validation criteria. The canonical Project Profile Matrix maps 21 project types to required, optional, or not-applicable capabilities.

Key: R/X = Required (X of X capabilities in the group must be implemented), O = Optional, N/A = Not Applicable

---

Capability Groups

1. Code Quality

Capability Description Validation
Formatting Automated code style enforcement No formatting violations
Linting Static analysis for bugs & style No lint errors
Type Safety Static type checking No type errors

2. Testing

Capability Description Validation
Unit Testing Test isolated logic units All unit tests pass
Integration Testing Test module interactions All integration tests pass
E2E Testing Test full user journeys Critical flows pass
Coverage Measure test coverage ≥ threshold

3. Security

Capability Description Validation
Secret Scanning Detect secrets in code No secrets detected
Dependency Scanning Find vulnerable dependencies No critical findings
SAST Static Application Security Testing No critical/high findings
DAST Dynamic Application Security Testing No critical findings
Container Scanning Scan container images No critical findings

4. Reliability

Capability Description Validation
Logging Structured application logging No console.log/print
Metrics Collection of key indicators Metrics endpoint responds
Health Checks Liveness/readiness endpoints All health endpoints OK

5. Observability

Capability Description Validation
Tracing Distributed transaction tracing Traces exported
Monitoring System & application monitoring Dashboards updated
Alerting Configurable alerts Alerts fire correctly

6. Performance

Capability Description Validation
Frontend Performance Lighthouse/Core Web Vitals Scores ≥ target
Backend Performance Latency/throughput benchmarks Within SLA
Load Testing Simulate traffic for scalability No regression
Benchmarking Compare performance versions No significant drop

7. Accessibility

Capability Description Validation
WCAG Validation Ensure accessibility standards No critical violations
Accessibility Audits Automated/manual audits All checks pass

8. Documentation

Capability Description Validation
API Documentation REST/GraphQL API docs All endpoints documented
Architecture Documentation Decision records, diagrams ADRs for major decisions

9. AI/LLM

Capability Description Validation
Evaluation Score model responses Scores meet threshold
Tracing Track LLM calls & prompts Traces captured
Prompt Testing Validate prompt variants All variants pass
Guardrails Enforce safety & compliance No violations
Model Validation Check model drift/performance Drift < threshold

---

Project Profile Matrix

Maps project types to required capabilities. R/X = Required (X of X capabilities in group), O = Optional, N/A = Not Applicable.

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

Legend

Notation Meaning
R/X Required — all X capabilities in the group must be implemented
O Optional — capability may be implemented based on project needs
N/A Not Applicable — capability is irrelevant to this project type

---

Profile Count Summary

Profile Count Details
Total Profiles 21
With All Required Backend API, Microservice, Telegram Bot (Production-Critical), Telegram Mini App, HF Inference Endpoint, AI Agent, Smart Contract, Data Pipeline, Trading Bot
With AI/LLM Required HF Model Training, HF Inference Endpoint, AI Agent
With Accessibility Required Frontend Web, Next.js, React, Mobile, Telegram Mini App, HF Space, AI Agent

---
