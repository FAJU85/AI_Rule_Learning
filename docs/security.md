# Security Architecture & Threat Model

Version: 2.1.0
Status: Enforced
Target: AI Rule Learning MCP

---

## 1. Threat Model & Overview

AI Rule Learning injects behavioral guardrail rules into LLM system contexts
(e.g., `CLAUDE.md`, Cursor, Windsurf, Copilot configs). Because rules modify model
behavior, the rule ingestion and storage pipeline must be fortified against:

1. **Prompt Injection Attacks**: Malicious users or adversarial prompts attempting to
   inject override directives (e.g. "ignore previous instructions", "jailbreak mode",
   "override safety").
2. **Data Poisoning in Community Pools**: Malicious actors submitting toxic or subverted
   patterns to corrupt the collective intelligence.
3. **Storage Pollution**: Injected rules persisting to local disk where they could be
   backed up or synced.
4. **PII and Secret Exfiltration**: Unintentional persistence or transmission of API
   credentials, passwords, or personal data.

---

## 2. Multi-Layer Defenses

```text
┌────────────────────────────────────────────────────────┐
│  Client Write Path                                     │
│  1. Pre-persistence Prompt Injection Scan (Stage 1 & 2)│
│  2. Client-side PII Scrubbing (5 Categories)           │
│  3. Feedback Slot Disambiguation (4 Distinct Slots)    │
│  4. Local Disk Persistence (~/.ai-rule-learning/)      │
└──────────────────────────┬─────────────────────────────┘
                           │ HTTPS POST (opt-in only, no auth)
                           ▼
┌────────────────────────────────────────────────────────┐
│  Write Relay Boundary (Cloudflare Worker)              │
│  1. Per-IP Rate Limiting                               │
│  2. Payload Size Enforcement (max 64KB)                │
│  3. Server-side Injection Pattern Scan                 │
│  4. Server-side PII Pattern Scan                       │
│  5. Storage to Private R2 Bucket (unindexed)           │
└──────────────────────────┬─────────────────────────────┘
                           │ Scheduled Processing
                           ▼
┌────────────────────────────────────────────────────────┐
│  Aggregator Cron Worker                                │
│  1. K-Anonymity Verification (unique_sources ≥ 5)      │
│  2. Content Filtering (No code, no URLs, no base64)    │
│  3. Template Synthesis & Cryptographic Manifest Hash   │
│  4. Publish to Public CDN (templates.jsonl)            │
└────────────────────────────────────────────────────────┘
```

---

## 3. Two-Stage Prompt Injection Detection

The detection engine combines fast deterministic pattern matching with contextual
semantic analysis:

### Stage 1: Deterministic & Weighted Signal Analysis

- **Canonical Attack Matching**: Exact phrase matching for high-frequency attack vectors.
- **Regex Patterns**: Parameterized regexes capturing permutations such as:
  - `(ignore|disregard|forget|bypass|override) + (everything|all|previous|instructions|rules|safety)`
  - `(jailbreak|developer|god|dan|sudo|unrestricted) + mode`
  - `(no|without|zero) + restrictions`
  - `override + safety`
  - `exfiltrate`
- **Weighted Signal Threshold**: Individual indicators contribute fractional scores;
  any strong attack signal or compound score ≥ 0.8 triggers an immediate rejection.
- **Benign Developer Allowlist**: Specific legitimate developer instructions
  (e.g., "build instructions", "setup instructions") are explicitly preserved with
  zero false positives.

### Stage 2: Contextual Semantic Evaluation

- Triggered when inputs exhibit borderline confidence or suspicious authority-claiming
  vocabulary.
- Optional DeBERTa-based CPU sequence classifier or semantic heuristic intent scoring.
- **Graceful Degradation**: If external models or weights are unavailable, Stage 2
  degrades seamlessly to Stage 1 without throwing unhandled exceptions.

---

## 4. Write-Path Rejection (Defect F12c)

- Injection detection is executed **before** rule generation and persistence.
- Any attempt to record feedback containing prompt injection returns an explicit rejection:

```json
{
  "status": "Rejected",
  "reason": "Feedback or rule hint contains a prompt injection / override attempt",
  "rule": null
}
```

- **No File-Side Artifacts**: Rejected inputs are never written to `rules.jsonl`.
- **Read-Time Filtering**: Retained as defense in depth across all rule loading interfaces.

---

## 5. Slot Collision Prevention & Migration (Defect F11b)

The four documented feedback types map to four distinct, non-overlapping rule slots:

| Feedback Type         | Assigned Slot Identifier              | Failure Category         |
| :-------------------- | :------------------------------------ | :----------------------- |
| `correction`          | `acknowledge-and-correct-immediately` | `behavioral_alignment`   |
| `preference`          | `honor-user-preferences`              | `behavioral_alignment`   |
| `repeated_context`    | `remember-stated-context`             | `robustness_consistency` |
| `incomplete_response` | `complete-all-parts-of-request`       | `output_quality`         |

An automatic, idempotent one-shot migration runs on store access to re-tag legacy rules
without data loss.

---

## 6. Community Defense & K-Anonymity (Defects Q01–Q07)

- **Decoupled Architecture**: Public read path uses a high-performance CDN / local
  fallback chain requiring **zero credentials**.
- **Private Staging**: Raw contributions are held in private Cloudflare R2 storage;
  no user can read another's raw submission.
- **K-Anonymity (min_sources ≥ 5)**: No pattern or template is ever published unless
  observed independently across at least 5 distinct sources.
- **Strict Content Filtering**: The aggregator strips executable code patterns, URLs,
  base64 data, and overly long text blocks before template publication.
