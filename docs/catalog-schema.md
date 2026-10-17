# Rule Catalog Schema & Context Specification

**Specification Version**: 1.0.0  
**Reference Document**: ARL-REM-2026-005  
**Data Files**: `data/catalog_v1.json`, `data/context_schema.json`

---

## 1. Overview

The Maximum-Capacity Rule Catalog (`data/catalog_v1.json`) provides a deterministic, vetted repository of behavioral alignment rules, secure coding guardrails, and quality constraints. To eliminate indirect prompt injection vulnerabilities, rules are extracted from published literature and industry standards rather than generated dynamically at runtime.

The catalog is governed by a strict JSON schema and operates with context-based activation. Every rule is evaluated against structured conversation features rather than unconstrained free text.

---

## 2. Catalog JSON Structure

The primary catalog file is formatted as a single JSON object containing catalog metadata and an array of validated rules:

```json
{
  "$schema": "./catalog.schema.json",
  "version": "1.0.0",
  "total_rules": 130,
  "categories": [
    "code_quality",
    "format_compliance",
    "hallucination",
    "instruction_drift",
    "persona_and_tone",
    "reasoning_failure",
    "security",
    "sycophancy",
    "task_completeness",
    "verbosity"
  ],
  "rules": [ ... ]
}
```

---

## 3. Individual Rule Schema

Every rule within `rules` contains the following fields:

| Field Name    | Type      | Required | Description                                                                                  |
| :------------ | :-------- | :------- | :------------------------------------------------------------------------------------------- |
| `gap_type`    | `string`  | Yes      | Unique identifier in `snake_case` naming the observed failure mode.                          |
| `category`    | `string`  | Yes      | One of the 10 enumerated taxonomy categories.                                                |
| `source`      | `string`  | Yes      | Verifiable citation string containing a standard DOI, arXiv ID, CWE ID, or vendor guide URL. |
| `instruction` | `string`  | Yes      | Actionable imperative instruction, constrained to at most two sentences.                     |
| `trigger_if`  | `object`  | Yes      | Key-value mapping of conversation features that activate the rule.                           |
| `exclude_if`  | `object`  | No       | Key-value mapping of features that suppress activation even if `trigger_if` matches.         |
| `priority`    | `integer` | Yes      | Integer rating from 1 (lowest) to 5 (critical/highest), used for selection ordering.         |

### Example Rule Definition

```json
{
  "gap_type": "unverified_api_reference",
  "category": "hallucination",
  "source": "Ji et al. (2023), ACM Comput. Surv. 55(12), DOI:10.1145/3571730, arXiv:2202.03629",
  "instruction": "Only reference standard library APIs and documented third-party functions that exist in the targeted version. If unsure of an API signature, explicitly state the assumption instead of guessing.",
  "trigger_if": {
    "task_type": "code_generation",
    "language": "python"
  },
  "exclude_if": {
    "task_type": "general_chat"
  },
  "priority": 5
}
```

---

## 4. Context Schema & Permitted Keys (`data/context_schema.json`)

To prevent arbitrary or unvalidated attributes, the `trigger_if` and `exclude_if` objects may reference **only** the following six keys. Free-form text values are forbidden; each value must belong to the schema enumeration:

### Permitted Keys and Enumerations

1. **`language`**
   - Permitted values: `"python"`, `"typescript"`, `"javascript"`, `"go"`, `"rust"`, `"java"`, `"csharp"`, `"cpp"`, `"bash"`, `"sql"`, `"agnostic"`, `"any"`
2. **`task_type`**
   - Permitted values: `"code_generation"`, `"code_review"`, `"debugging"`, `"architecture"`, `"refactoring"`, `"documentation"`, `"explanation"`, `"security_audit"`, `"testing"`, `"general_chat"`, `"any"`
3. **`framework`**
   - Permitted values: `"fastapi"`, `"react"`, `"nextjs"`, `"node"`, `"django"`, `"flask"`, `"express"`, `"pytest"`, `"tailwind"`, `"none"`, `"any"`
4. **`recent_patterns`**
   - Permitted values: `"user_correction"`, `"negative_feedback"`, `"repeated_query"`, `"verbose_output"`, `"code_error"`, `"hallucination_detected"`, `"drift_detected"`, `"sycophancy_detected"`, `"unverified_claim"`, `"unhandled_exception"`, `"missing_import"`, `"injection_attempt"`, `"none"`, `"any"`
5. **`context_length`**
   - Permitted values: `"short"`, `"medium"`, `"long"`, `"extended"`, `"extreme"`, `"any"`
6. **`user_style`**
   - Permitted values: `"concise"`, `"verbose"`, `"technical"`, `"skeptical"`, `"authoritative"`, `"exploratory"`, `"casual"`, `"demanding"`, `"any"`

---

## 5. Three Independent Validation Checks

Every rule included in the catalog must pass three independent automated gates before merge:

1. **Citation Check**:
   - The `source` field must resolve to a recognized academic or industry source containing a verifiable identifier (e.g., DOI, arXiv number, CWE clause, OWASP Top 10 identifier, or official vendor documentation URL).
2. **Syntax Check**:
   - The rule must adhere strictly to JSON typing.
   - `gap_type` must be unique across the catalog and formatted in lowercase `snake_case`.
   - `category` must match one of the 10 permitted taxonomy categories.
   - `instruction` must be written in the imperative voice and contain no more than two sentences.
   - `trigger_if` and `exclude_if` keys must strictly exist in the context schema.
   - All trigger and exclude values must match defined enum options.
3. **Contradiction Check**:
   - Two rules sharing the same trigger envelope (e.g., identical `task_type` and `language`) must not mandate opposing actions (such as contradictory polarities on the same target behavior).

---

## 6. Activation Engine Logic

The runtime activation engine (`src.core.catalog.RuleCatalog.activate`) matches rules against session context dictionaries:

$$\text{Activated}(R, C) \iff \Big(\forall k \in \text{keys}(\text{trigger\_if}_R): \text{trigger\_if}_R[k] \in \{C[k], \text{"any"}\}\Big) \land \neg \Big(\exists k \in \text{keys}(\text{exclude\_if}_R): \text{exclude\_if}_R[k] \in \{C[k], \text{"any"}\}\Big)$$

Matching rules are sorted by `priority` in descending order.
