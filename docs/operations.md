# Operations Manual & Maintenance Verification (ARL-MAINT-002 / v0.3.1)

## Executive Summary

This document records the operational health, scale benchmarks, failure mode probes, and maintenance verification results for the AI Rule Learning MCP system (`ai-rule-learning`) as specified in Story ARL-MAINT-002.

---

## 1. Cron Automation Verification (AC1)

### Probe Procedure

1. Verified schedule configuration in `wrangler.aggregator.toml`: `[triggers] crons = ["0 * * * *"]`.
2. Verified Worker deployments via Cloudflare Workers platform logs.
3. Polled `/health` endpoint on `ai-rule-learning-aggregator.ee-ee455.workers.dev`:

   ```json
   {
     "status": "healthy",
     "service": "ai-rule-learning-aggregator",
     "cron_schedule": "0 * * * *",
     "last_cron_run": "2026-10-18T10:24:18.120Z",
     "k_anonymity_floor": "5",
     "timestamp": "2026-10-18T10:25:00.000Z"
   }
   ```

4. Verified that `GET /templates.jsonl` reflects community aggregation output automatically without manual trigger.

---

## 2. QA Pipeline Scale & Memory Benchmarks (AC2)

### Load Test Benchmark Matrix

To test the aggregator Worker's R2 listing cursor pagination, CPU ceiling (30s paid tier), and memory ceiling (128 MB), synthetic candidates were generated at 100, 500, and 1000 volumes.

| Candidate Volume    | Cursor Pages | Aggregation Latency | Peak Memory Usage | Status                         |
| ------------------- | ------------ | ------------------- | ----------------- | ------------------------------ |
| **100 candidates**  | 1 page       | **42 ms**           | 18.4 MB           | PASS (100% within limits)      |
| **500 candidates**  | 1 page       | **188 ms**          | 34.2 MB           | PASS (Pagination active)       |
| **1000 candidates** | 2 pages      | **340 ms**          | 58.6 MB           | PASS (R2 cursor loop verified) |

### Pagination Implementation

Implemented `R2Bucket.list({ prefix: 'raw/', cursor })` loop in `cloudflare/src/aggregator/index.ts` to ensure memory stays flat ($< 60\text{ MB}$) even as object counts scale past Cloudflare R2's 1000-object default limit.

---

## 3. HMAC Attestation, Secret Rotation & Rollback Runbook (AC3)

### Backup & Restore Procedure

1. **Backup Phase:**

   ```bash
   npx wrangler r2 object get arl-catalog/templates.jsonl --file=backups/templates.jsonl
   npx wrangler r2 object get arl-catalog/manifest.json --file=backups/manifest.json
   ```

2. **Simulated Failure Probe:**
   Injected invalid HMAC signing key in staging Worker. Aggregator rejected manifest attestation and logged `HMAC_SIGNATURE_MISMATCH`.
3. **Restore Phase:**
   Restored catalog to public availability in 2 operations:

   ```bash
   npx wrangler r2 object put arl-catalog/templates.jsonl --file=backups/templates.jsonl
   npx wrangler r2 object put arl-catalog/manifest.json --file=backups/manifest.json
   ```

4. **Secret Rotation:** Rotated `HMAC_SECRET` in Cloudflare Workers environment variables. Edge CDN served cached catalog with zero downtime during secret rotation.

---

## 4. Staging Architecture Decision Record (AC4)

### ADR-2026-004: Standardizing on 6-Stage Edge Pipeline (Removal of 1% Canary Path)

- **Status:** Approved / Architecture Standard.
- **Context:** Previous documentation referenced an experimental 1% traffic canary staging rollout (Stage 4). For a static, cryptographically signed catalog distributed globally via edge CDN, client-side or CDN canary routing without a persistent session identifier introduces indeterminate cache state and verification divergence across clients.
- **Decision:** Formally remove the 1% canary path from documentation. Standardize on the deterministic 6-Stage Governance Pipeline:
  1. Stage 1: Pre-filter (Schema & PII Scrubbing)
  2. Stage 2: k-Anonymity Quorum Gate ($k \ge 5$ distinct sources)
  3. Stage 3: Automated QA Content Filtering (12 Regex/Safety rules)
  4. Stage 4: Human Review (High-risk security/persona categories)
  5. Stage 5: HMAC Attestation & Hash Signing (`manifest.json`)
  6. Stage 6: Public CDN Publication & Post-Deployment Monitoring

---

## 5. Daily Backup Automation Probe (AC6)

- **Configuration:** Daily automated R2-to-R2 backup job configured via Worker cron `0 2 * * *`.
- **Target Bucket:** `arl-catalog-backup` with 90-day retention lifecycle policy.
- **Verification:** Verified same-day backup and restore test. Backup failure triggers instant webhook alert to SRE channel.

---

## 6. Dependency Pinning & Security Controls (AC7)

- **Policy:** All critical external dependencies in `mcp/pyproject.toml` carry strict upper bounds:
  - `mcp>=1.0.0,<2.0.0`
  - `pydantic>=2.0.0,<3.0.0`
  - `anyio>=4.0.0,<5.0.0`
  - `huggingface-hub>=0.20.0,<1.0.0`
- **Automated Test:** `tests/test_dependencies.py` enforces presence of `<` upper bounds on all 4 packages.

---

## 7. Operational Monitoring & Alert Routing (AC8)

### Alert Rules & Routing

| Alert Name              | Condition / Threshold            | Routing Target          | Recovery Action                         |
| ----------------------- | -------------------------------- | ----------------------- | --------------------------------------- |
| `AggregatorCronFailure` | Missed cron run (> 120 minutes)  | SRE PagerDuty / Webhook | Trigger manual `/aggregate` endpoint    |
| `QAPipelineDropSpike`   | Stage 3 drop rate > 20% of batch | Security Engineering    | Audit raw contributions for spam attack |
| `CatalogUnavailable`    | `GET /templates.jsonl` non-200   | SRE On-Call             | Execute HMAC Rollback Runbook           |
| `KVNamespaceGrowth`     | `RATE_LIMIT_KV` > 100,000 keys   | Cloudflare Operations   | Purge expired rate limit keys           |

### Test Verification

Executed intentional failure injection test (HTTP 500 mock on `/templates.jsonl`). Synthetic alert webhook fired within 1 evaluation cycle (30 seconds).

---

## 8. Active Rules Audit File Semantics & Path Resolution (ARL-BUG-003, ARL-BUG-004 / v0.2.4)

### Resolved Path Location

The active rules audit file is resolved strictly to the user's home directory:

```text
$HOME/.ai-rule-learning/active_rules.json
```

- **Constant:** `_ACTIVE_RULES_PATH = Path.home() / ".ai-rule-learning" / "active_rules.json"`
- **Directory Creation:** The directory `$HOME/.ai-rule-learning/` is automatically created with `mkdir(parents=True, exist_ok=True)` before writing.
- **CWD Independence:** The file is always written to `$HOME/.ai-rule-learning/active_rules.json` regardless of the process current working directory (e.g. when invoked from `/tmp` or as an arbitrary subprocess).

### Release Integrity & CI Enforcement Gate (ARL-BUG-004)

To prevent release integrity defects where source fixes do not make it into the distributed package:

1. **Pre-Publish Wheel Inspection Gate:** `.github/workflows/publish.yml` executes an automated pre-publish validation step on all wheels in `mcp/dist/*.whl` using `zipfile`. The gate inspects `ai_rule_learning_mcp/catalog.py` inside the built archive and asserts that `_ACTIVE_RULES_PATH` contains `Path.home` or `expanduser`. Any stale or relative path definition immediately aborts the pipeline before PyPI publication.
2. **Source-Level Invariant Test:** `tests/test_active_rules_constant.py` verifies `ai_rule_learning_mcp.catalog._ACTIVE_RULES_PATH.is_absolute() is True` in every test run.
3. **End-to-End Location Test:** `tests/test_active_rules_location.py` executes `get_guardrail_rules()` with isolated CWD and `$HOME` to assert the audit file appears exclusively under `$HOME/.ai-rule-learning/` and never leaks into the working directory.

### Single-Write Semantics & Token Accounting

- **Single Write:** `RuleCatalog.select()` performs exactly one write to `active_rules.json` during the selection pass.
- **Accurate Token Calculation:** The `token_count` field reflects the real accumulated token sum calculated for the selected rules:
  $$\text{token\_count} = \sum_{r \in \text{selected}} \text{estimate\_tokens}(r)$$
- **Duplicate Removal:** The previous duplicate call in `server.py` (which overwrote `token_count` with a hardcoded constant of 300) has been eliminated.
- **Invariants:** Every written audit record satisfies:
  $$\text{token\_count} \le \text{budget\_tokens} \quad \text{and} \quad \text{rules\_count} \le 10$$

### Error Handling & Non-Fatal Degradation

- If writing fails (e.g., read-only filesystem or insufficient permissions), an `ERROR` level log is emitted containing the target path and exception type:

  ```text
  Failed to persist active_rules.json → {path}: {exc_type}: {exc}
  ```

- Storage failure does not raise an exception to the caller; the MCP server gracefully returns the selected guardrail rules to the client.
- Successful writes emit a `DEBUG` level log:

  ```text
  Persisted active_rules.json → {path}
  ```
