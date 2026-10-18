# AI Rule Learning System — Threat Model & Security Architecture

**Version:** 0.3.0  
**Methodology:** STRIDE + Zero-Trust Edge Security Model  
**References:** ARL-SPRINT-001, ARL-REM-2026-007, SEC-01..05

---

## 1. System Assets & Security Boundaries

```text
[ UNTRUSTED ]
   External Developer Sessions / Public Telemetry Submissions
        │
        │ Boundary 1: Client Pre-Filter (Regex PII + Prompt Injection Scanners)
        ▼
[ TRUSTED LOCAL ]
   Local MCP Server, rules.jsonl (7-Field Provenance), Agent Configs (CLAUDE.md)
        │
        │ Boundary 2: Edge Relay (64 KB ceiling, IP Rate-Limit, Zod Provenance Validation)
        ▼
[ PROTECTED EDGE ]
   Cloudflare Relay Worker ──> Private R2 Raw Bucket (arl-learning-raw, 30-day TTL)
        │
        │ Boundary 3: Governance Pipeline (k >= 5 Quorum, 12-Test QA, Human Review)
        ▼
[ VERIFIED PUBLIC ]
   Public R2 Bucket (arl-catalog) ──> HMAC Signed manifest.json + templates.jsonl
```

---

## 2. Threat Analysis (STRIDE)

| Threat Category            | Attack Vector                                                         | Impact                                                       | Architectural Mitigation                                                                                                                                                           | Verification                 |
| -------------------------- | --------------------------------------------------------------------- | ------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------- |
| **Spoofing**               | Attacker impersonates legitimate developer node with fake session IDs | Submits fraudulent feedback to skew rule confidence          | Strict 7-field provenance validation (`source_session_id`, `source_hash`, `qa_report_id`). Minimum $k \ge 5$ distinct source hashes required for quorum.                           | `test_sec_04`, `test_sec_05` |
| **Tampering**              | Attacker attempts to modify canonical rule text via `edit_rule`       | Injects poisoned instructions into local/team agent rulesets | Rule instruction field is strictly immutable. `edit_rule` rejects any `instruction` argument with an explicit error. Only priority and activation metadata can be updated.         | `test_gap_04`                |
| **Repudiation**            | Operator denies reviewing or approving an unvetted rule               | Lack of accountability for faulty guardrail injection        | Mandatory provenance fields `reviewed_by` and `reviewed_at` written atomically to `rules.jsonl` on approval/rejection.                                                             | `test_sec_04`                |
| **Information Disclosure** | Developer session logs contain API keys, passwords, or PII            | Secret leakage to telemetry buckets                          | Dual-layer PII scrubber (`scrub_pii()` on client, edge regex scanner on relay). Relay rejects any payload containing raw email, IP, bearer token, or home directory with HTTP 400. | `test_f12c`, AC3 test        |
| **Denial of Service**      | Flooding edge relay with massive payloads                             | Cloudflare Worker CPU exhaustion, R2 storage exhaustion      | Hard 64 KB content-length ceiling dropped with HTTP 413. Sliding-window per-IP rate limiter (30 req/min, 100/day) backed by Edge KV.                                               | Relay rate-limit test        |
| **Elevation of Privilege** | Indirect prompt injection in user prompts or feedback                 | Agent executes arbitrary commands or bypasses safety filters | Two-stage injection detector (`scan_injection`). In addition, rule instructions are static and drawn exclusively from peer-reviewed literature catalog (`data/catalog_v1.json`).   | `test_f12b`, `test_f13b`     |

---

## 3. Seven-Stage Governance Defense Pipeline

1. **Stage 1 (Pre-Filter):** Client-side PII scrubbing and prompt injection detection.
2. **Stage 2 (Quorum Gate):** Minimum 5 distinct source hashes, 3 extractors, over at least 7 days before candidate evaluation.
3. **Stage 3 (Automated QA):** 12 deterministic test suites verifying syntax, absence of eval/exec/network calls, and character limits.
4. **Stage 4 (Staging):** 1% traffic canary staging to detect regressions.
5. **Stage 5 (Human Review):** Mandatory human sign-off for high-risk categories (`security`, `tool_misuse`). Low-risk categories (`verbosity`) can auto-promote upon passing QA.
6. **Stage 6 (HMAC Promotion):** Cryptographic HMAC signing of canonical `manifest.json` with SHA-256 digest of `templates.jsonl`.
7. **Stage 7 (Post-Deployment Monitoring):** Continuous tracking of rule effectiveness and community suppression flags.
