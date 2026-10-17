# Schema Reference & Compatibility Specification

**Version**: 0.2.0  
**Effective Date**: 2026-04-16  
**Reference**: ARL-REM-2026-004 (Sections 7.1, 7.2, 11.1)

---

## 1. Overview

AI Rule Learning maintains a clean separation between:

1. **Local Storage Schema (`rules.jsonl`)**: Rich 21-field schema supporting complete lifecycle, triggers, actions, and audit provenance.
2. **Community Telemetry Schema (Canonical 4-Field Format)**: Compact, strictly anonymized format used for relay transmission and k-anonymity aggregation.

---

## 2. Anonymity Mechanism (C1.5)

To guarantee that community contributions remain untraceable to individual users, the system implements deterministic, irreversible anonymization:

- **`anonymous_id` (Canonical Anonymity Field)**: A pseudo-anonymous identifier formatted as `anon_<hash12>`, deterministically derived from a one-way salt and installation fingerprint. It carries zero hardware, network, username, or IP characteristics.
- **`source_hash`**: A one-way SHA-256 hash of the local session identifier used solely by the aggregator to enforce k-anonymity across distinct sessions (`unique_sources >= 5`).

Both `anonymous_id` and `source_hash` are validated on contribution.

---

## 3. Canonical 4-Field Unified Rule Format (C1.6)

When rules or gap patterns are normalized for contribution (`normalize_contribution_payload`), they map from local representations into the canonical 4-field structure:

| Canonical Field | Type   | Semantic Concept                                    | Local Schema Mapping                                               |
| :-------------- | :----- | :-------------------------------------------------- | :----------------------------------------------------------------- |
| `pattern`       | string | Sanitized trigger signal or friction phrase (≤120c) | `gap_type`, `signal`, `trigger.keywords[0]`                        |
| `category`      | string | Failure taxonomy classification                     | `failure_category`, `category` (default: `robustness_consistency`) |
| `example`       | string | PII-scrubbed illustration or countermeasure (≤200c) | `action.instruction`, `instruction`, `example`                     |
| `confidence`    | float  | Effectiveness score $[0.0, 1.0]$                    | `effectiveness_score`, `confidence` (default: `0.85`)              |

### Example Normalized Payload

```json
{
  "pattern": "explicit_correction",
  "category": "robustness_consistency",
  "example": "Always verify command line flags before proposing terminal execution.",
  "confidence": 0.92,
  "anonymous_id": "anon_a1b2c3d4e5f6",
  "source_hash": "a1b2c3d4e5f67890"
}
```

---

## 4. Reserved Names & Slot Deduplication (FS04)

The feedback engine assigns rules into structured slots to maintain a compact, high-impact guardrail footprint.

When distinct feedback entries share a general feedback category (such as `correction`) or involve platform-reserved identifiers (such as `CON`, `PRN`, `AUX`, `NUL`), the engine:

1. Identifies differing instruction content (`prev_instruction != new_instruction`).
2. Derives a deterministic cryptographic sub-slot suffix (`<slot>-<hash8>`).
3. Stores each distinct instruction independently so that $n = 4$ distinct entries remain distinct and no user-authored hint is silently dropped.

---

## 5. Local Storage Schema (`rules.jsonl`)

The local persistence schema retains full backwards compatibility:

```json
{
  "rule_id": "rule-c7f8a1e2",
  "name": "verify-cli-flags",
  "slot": "acknowledge-and-correct-immediately-a1b2c3d4",
  "instruction": "Always verify CLI flags before execution.",
  "priority": 3,
  "severity": 1,
  "is_active": true,
  "trigger": { "keywords": ["correction", "wrong"] },
  "action": { "instruction": "Always verify CLI flags before execution." },
  "evidence": { "gap_type": "explicit_correction" },
  "effectiveness_score": 0.85,
  "created_at": "2026-04-16T12:00:00Z"
}
```
