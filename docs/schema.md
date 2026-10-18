# Schema Reference & Compatibility Specification

**Version**: 0.2.1  
**Effective Date**: 2026-10-18  
**Reference**: ARL-REM-2026-004, ARL-REM-2026-006, ARL-REM-2026-007

---

## 1. Overview

AI Rule Learning maintains a clean separation between:

1. **Local Storage Schema (`rules.jsonl`)**: Rich 28-field schema supporting complete lifecycle management, context triggers, actions, and the **Seven Mandatory Provenance Fields** (ARL-REM-2026-007).
2. **Community Telemetry Schema (Canonical 4-Field Format)**: Compact, strictly anonymized format used for relay transmission and k-anonymity aggregation.
3. **Curated Literature Catalog (`data/catalog_v1.json`)**: 130 static rules with academic/industry citations (`source` field).

---

## 2. Seven Mandatory Provenance Fields (ARL-REM-2026-007)

Every rule persisted to local storage (`rules.jsonl`) or generated via `sync_sessions` / `record_feedback` must include the following seven auditable provenance fields:

| Field Name           | Type             | Allowed Values                          | Semantic Role & Operational Mapping                                                     |
| :------------------- | :--------------- | :-------------------------------------- | :-------------------------------------------------------------------------------------- |
| `source_session_id`  | `string`         | non-empty string                        | Pseudonymous identifier of the local session or interaction where the gap was observed. |
| `extraction_version` | `string`         | semver string (`0.2.1`)                 | Exact engine version responsible for parsing and synthesizing the rule.                 |
| `extracted_at`       | `string`         | ISO 8601 UTC string                     | Precise timestamp when pattern extraction occurred.                                     |
| `review_status`      | `string`         | `"pending"`, `"approved"`, `"rejected"` | Formal governance review status. Governs whether rule can be injected or contributed.   |
| `reviewed_by`        | `string \| null` | operator ID or `null`                   | Identity of the user or operator who approved/rejected the rule. `null` while pending.  |
| `reviewed_at`        | `string \| null` | ISO 8601 UTC or `null`                  | Timestamp when approval or rejection occurred. `null` while pending.                    |
| `qa_report_id`       | `string`         | non-empty string                        | Audit report identifier (`qa_<hash8>`) verifying local safety and formatting checks.    |

### Lifecycle State Machine & Tool Behavior

```text
       extract_rules() / sync_sessions()
                      │
                      ▼
               ┌───────────────┐
               │    PENDING    │ ───► [COMMUNITY PROPAGATION SUPPRESSED]
               └───────┬───────┘
                       │
         ┌─────────────┴─────────────┐
         │ approve_rule              │ reject_rule
         ▼                           ▼
┌──────────────────┐        ┌──────────────────┐
│     APPROVED     │        │     REJECTED     │
│ (Active / Inject)│        │ (Inactive / Mute)│
└────────┬─────────┘        └──────────────────┘
         │
         ▼
[Eligible for Community Relay]
```

- **`approve_rule(rule_id)`**:
  - Transitions `review_status` $\to$ `"approved"`.
  - Sets `status` $\to$ `"active"`, `is_active` $\to$ `true`.
  - Records `reviewed_by = "local_admin"`, `reviewed_at = <now>`.
  - Makes rule eligible for active agent config injection and community contribution.
- **`reject_rule(rule_id, note)`**:
  - Transitions `review_status` $\to$ `"rejected"`.
  - Sets `status` $\to$ `"rejected"`, `is_active` $\to$ `false`.
  - Records `reviewed_by = "local_admin"`, `reviewed_at = <now>`, and attaches `review_note`.
  - Suppresses rule from both agent config injection and community relay transmission.

---

## 3. Canonical 4-Field Unified Telemetry Format

When rules or gap patterns are normalized for community contribution (`normalize_contribution_payload`), they map from local representations into the canonical 4-field structure:

| Canonical Field | Type   | Semantic Concept                                         | Local Schema Mapping                                               |
| :-------------- | :----- | :------------------------------------------------------- | :----------------------------------------------------------------- |
| `pattern`       | string | Sanitized trigger signal or friction phrase ($\le 120$c) | `gap_type`, `signal`, `trigger.keywords[0]`                        |
| `category`      | string | Failure taxonomy classification                          | `failure_category`, `category` (default: `robustness_consistency`) |
| `example`       | string | PII-scrubbed illustration or countermeasure ($\le 200$c) | `action.instruction`, `instruction`, `example`                     |
| `confidence`    | float  | Effectiveness score $[0.0, 1.0]$                         | `effectiveness_score`, `confidence` (default: `0.85`)              |

### Example Normalized Contribution Payload

```json
{
  "pattern": "explicit_correction",
  "category": "robustness_consistency",
  "example": "Always verify command line flags before proposing terminal execution.",
  "confidence": 0.92,
  "anonymous_id": "anon_a1b2c3d4e5f6",
  "source_hash": "a1b2c3d4e5f67890",
  "source_session_id": "a1b2c3d4e5f67890",
  "extraction_version": "0.2.1",
  "extracted_at": "2026-10-18T11:45:00Z",
  "review_status": "approved",
  "qa_report_id": "qa_a1b2c3d4"
}
```

---

## 4. Local Storage Schema Example (`rules.jsonl`)

The local persistence schema contains complete lifecycle metadata and all seven provenance fields:

```json
{
  "rule_id": "rul_941aa0198d1f",
  "name": "acknowledge-and-correct-immediately",
  "slot": "acknowledge-and-correct-immediately",
  "instruction": "Use parameterized queries",
  "action": {
    "instruction": "Use parameterized queries"
  },
  "trigger": {
    "keywords": ["wrong", "incorrect", "actually"]
  },
  "pattern": "wrong",
  "example": "Use parameterized queries",
  "category": "behavioral_alignment",
  "confidence": 0.6,
  "user_id": "anon_941aa0198d1f",
  "anonymous_id": "anon_941aa0198d1f",
  "source_hash": "941aa0198d1f27e9",
  "ttl_days": 365,
  "priority": 4,
  "priority_label": "HIGH",
  "failure_layer": 1,
  "failure_layer_label": "Model Behaviour",
  "failure_category": "behavioral_alignment",
  "failure_category_label": "Behavioural & Alignment",
  "gap_type": "explicit_correction",
  "instance_count": 1,
  "is_active": true,
  "status": "pending",
  "source": "local_detector",
  "created_at": "2026-10-18T11:45:35.976544",
  "source_session_id": "941aa0198d1f27e9",
  "extraction_version": "0.2.1",
  "extracted_at": "2026-10-18T11:45:35.976544",
  "review_status": "pending",
  "reviewed_by": null,
  "reviewed_at": null,
  "qa_report_id": "qa_941aa019",
  "effectiveness_score": 0.5,
  "times_triggered": 0,
  "suppression_count": 0,
  "last_fired_at": null
}
```
