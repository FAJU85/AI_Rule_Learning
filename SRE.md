# Site Reliability Engineering (SRE) Specification & Operations Manual

**Project Name:** AI Rule Learning MCP System (`ai-rule-learning`)  
**Document Version:** 1.0.0  
**Target Release:** v0.3.0  
**Status:** Approved / Active Production Baseline  
**Classification:** Reliability Architecture & Runbooks

---

## 1. System Architecture & Topology

```text
                                  ┌────────────────────────────────────────────────────────┐
                                  │                CLOUDFLARE EDGE PLATFORM                │
                                  │                                                        │
┌────────────────────────┐        │   ┌────────────────────┐      ┌────────────────────┐   │
│ Client Agent (Claude/  │ ──(1)─>│   │  arl-relay Worker  │─────>│ arl-learning-raw   │   │
│ Cursor) via MCP Server │        │   │  (POST /contribute)│      │  (Private R2 Raw)  │   │
└────────────────────────┘        │   └─────────┬──────────┘      └─────────┬──────────┘   │
            │                     │             │ RateLimit KV              │              │
            │                     │             ▼ (30 req/min)              │ Scheduled    │
            │                     │   ┌────────────────────┐                ▼              │
            ▼                     │   │ arl-rate-limit-kv  │      ┌────────────────────┐   │
┌────────────────────────┐        │   └────────────────────┘      │ arl-aggregator     │   │
│ Local Storage Engine   │        │                               │ (Stages 2-5 QA)    │   │
│ (rules.jsonl, 7-Field) │        │   ┌────────────────────┐      └─────────┬──────────┘   │
└────────────────────────┘        │   │  arl-catalog       │<───────────────┘              │
                                  │   │  (Public R2 + CDN) │  Signed manifest.json         │
                                  │   └─────────┬──────────┘  templates.jsonl              │
                                  └─────────────┼──────────────────────────────────────────┘
                                                │
                                       (2) GET  ▼
                                  ┌────────────────────────┐
                                  │ Consumer / Secondary   │ (Zero-credential HTTPS fetch)
                                  │ Local MCP Client Node  │
                                  └────────────────────────┘
```

The system operates across four primary operational tiers:

1. **Local Node (Tier 1):** Zero external dependency runtime. MCP server executes locally, reads/writes `rules.jsonl`, reads `data/catalog_v1.json`, patches local agent configurations.
2. **Edge Telemetry Ingestion (Tier 2):** Cloudflare Worker (`arl-relay`) built with TypeScript, Hono, and Zod, backed by KV rate limiting and private R2 raw storage.
3. **Edge Pipeline Aggregator (Tier 3):** Serverless scheduled worker (`arl-aggregator`) executing data cleansing, k-anonymity validation, and catalog publication.
4. **Public Distribution CDN (Tier 4):** Edge-cached public R2 bucket (`arl-catalog` / `arl-templates`) serving verifiable artifacts to clients.

---

## 2. Service Level Objectives (SLOs) & Service Level Indicators (SLIs)

### 2.1 SLI/SLO Matrix

| Service Component                | Service Level Indicator (SLI)                                                                                     | Target (SLO)          | Window          | Error Budget (30d)                  |
| -------------------------------- | ----------------------------------------------------------------------------------------------------------------- | --------------------- | --------------- | ----------------------------------- |
| **Local MCP Server**             | % of `initialize` and `tools/call` operations returning within 400ms without exception                            | **99.9%**             | Rolling 30 days | 0.1% (~43 minutes downtime/failure) |
| **Local Rule Selection**         | % of `cat.select()` operations satisfying $\le 10\text{ rules}$ AND $\le 500\text{ tokens}$ in $\le 50\text{ ms}$ | **99.99%**            | Rolling 30 days | 0.01% (~4.3 minutes)                |
| **Cloudflare Relay API**         | Ratio of HTTP non-5xx responses on `POST /contribute`                                                             | **99.95%**            | Rolling 30 days | 0.05% (~21.6 minutes)               |
| **Edge Latency**                 | $P_{95}$ latency on `/contribute` and `/health` endpoints                                                         | **$< 100\text{ ms}$** | Rolling 7 days  | N/A                                 |
| **Aggregator Cron**              | Scheduled execution completing successfully within 120 seconds                                                    | **99.0%**             | Rolling 30 days | 7 missed runs / month               |
| **Public Template Availability** | Successful zero-credential HTTPS GET requests to `templates.jsonl`                                                | **99.99%**            | Rolling 30 days | 0.01% (~4.3 minutes)                |

### 2.2 Error Budget Policy & Burn Rates

- **Burn Rate 14.4x (2% budget consumed in 1 hour):** Triggers P1 alert to on-call engineer; immediate triage required.
- **Burn Rate 6x (5% budget consumed in 6 hours):** Triggers P2 notification to engineering team; investigate during working hours.
- **Exhausted Error Budget:** Halts all non-reliability feature releases; developer focus shifts 100% to infrastructure stabilization, test harness hardening, and bug fixes.

---

## 3. Resilience, Fault Tolerance & Failure Modes

| Failure Scenario                      | Impact                                                   | Built-in Mitigation Mechanism                                                                                                                           | Recovery Action                                                                                   |
| ------------------------------------- | -------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| **Cloudflare R2 Outage**              | Telemetry ingestion halts; community rules cannot sync   | Local MCP server falls back transparently to bundled static catalog (`data/catalog_v1.json`). Local rule injection continues with zero disruption.      | Telemetry requests queue locally on client disk (`.pending_sync/`) with backoff retry.            |
| **Malformed Rule Contribution**       | Malicious injection or malformed JSON submitted          | Edge Relay enforces strict Zod schema validation, 64 KB ceiling, regex injection scan, and PII detection.                                               | Request rejected immediately with HTTP 400 Bad Request; zero write to R2.                         |
| **Sybil Attack / Poisoning**          | Attacker attempts to inject poisoned rule into community | Aggregator enforces minimum $k \ge 5$ distinct `source_hash` quorum, regex safety scans, and human/curated template synthesis.                          | Sybil payloads cluster with unique sources $< 5$ and are pruned during Stage 3 Content Filtering. |
| **Corrupted `rules.jsonl`**           | Local MCP startup crash or parse failure                 | Atomic file writes via temporary file rename (`rules.jsonl.tmp` $\to$ `rules.jsonl`). Corrupted lines quarantined to `rules.jsonl.bak`.                 | Fallback to empty local store + base catalog; alert emitted via CLI status.                       |
| **Agent Config File Lock / Conflict** | Git merge conflict or concurrent agent edit              | Invariant delimiter scanning (`<!-- AI-Rule-Learning:start -->`). If markers are broken or unparseable, write is aborted without touching user content. | Abort write, log warning, leave original file unmodified.                                         |

---

## 4. Monitoring, Telemetry & Observability Architecture

### 4.1 Local Node Observability

- **Structured Logging:** Standard Python `logging` formatted as structured JSON to `stderr` or rotating local log (`~/.ai-rule-learning/logs/mcp.log`). Console/stdout is strictly reserved for clean JSON-RPC 2.0 frames.
- **Audit Ledger:** Every rule change (approval, rejection, creation) appends a verifiable entry in `rules.jsonl` with timestamps and reviewer IDs.

### 4.2 Cloudflare Edge Observability

- **Cloudflare Logpush & Workers Analytics Engine:** Captures every invocation of `arl-relay` and `arl-aggregator`.
- **Metrics Tracked:**
  - `contributions_received_total` (counter by status: 201, 400, 413, 429, 500)
  - `payload_bytes_distribution` (histogram)
  - `rate_limit_drops_total` (counter)
  - `aggregator_candidates_processed` vs `aggregator_templates_published`
  - `manifest_hash_generation_duration_ms`

### 4.3 Live Reference Endpoints

- **Relay Worker Health:** `GET https://ai-rule-learning-relay.ee-ee455.workers.dev/health`
- **Aggregator Worker Health:** `GET https://ai-rule-learning-aggregator.ee-ee455.workers.dev/health`
- **Public Catalog Templates:** `GET https://ai-rule-learning-aggregator.ee-ee455.workers.dev/templates.jsonl`
- **Published PyPI Package:** `https://pypi.org/project/ai-rule-learning-mcp/0.2.1/`

---

## 5. Deployment, Rollout & Blue-Green Architecture

### 5.1 Cloudflare Edge Deployment

Edge workers utilize dual-environment staging via `wrangler`:

1. **Staging / Canary (`development`):** Deploy to staging worker URL. Integration tests execute live HTTP validation.
2. **Production (`production`):** Zero-downtime deployment via `wrangler deploy --env production`. Cloudflare edge automatically propagates versioned worker bundles across global PoPs in $< 5\text{ seconds}$.

### 5.2 MCP Package Release Flow

- **Package:** `ai-rule-learning-mcp` published to PyPI.
- **Dependency Invariant:** Must strictly pin `mcp>=1.0.0,<2.0.0` to avoid FastMCP 2.0 breaking changes.
- **CI Pre-publish Gate:** Automated test `tests/test_default_install.py` runs in clean virtual environments across Python 3.10, 3.11, and 3.12, verifying unconstrained pip install.

---

## 6. Incident Management & Disaster Recovery Runbooks

### Runbook 1: Cloudflare Edge Ingestion Alert (HTTP 5xx Spike on `/contribute`)

1. **Diagnosis:** Check Cloudflare Dashboard $\to$ Workers $\to$ `arl-relay` $\to$ Real-Time Logs.
2. **Determine Cause:**
   - Case A: R2 bucket permission error (e.g., expired API credentials or incorrect binding).
   - Case B: Edge KV quota exhaustion.
3. **Mitigation:**
   - If binding failure: Re-run `npx wrangler deploy --env production`.
   - If KV failure: Increase KV namespace quota or temporarily route contributions to memory-buffer mode.
4. **Local Fallback:** Clients automatically back off exponentially; no data is lost as clients retain local `rules.jsonl`.

### Runbook 2: Injected Malicious / Poisoned Rule in Community Catalog

1. **Trigger:** Security team or automated integrity monitor flags anomalous entry in `templates.jsonl`.
2. **Immediate Remediation:**
   - Execute emergency catalog rollback:

     ```bash
     wrangler r2 object put arl-catalog/templates.jsonl --file=backups/templates_v0.2.1.jsonl
     wrangler r2 object put arl-catalog/manifest.json --file=backups/manifest_v0.2.1.json
     ```

   - Purge Cloudflare Edge Cache for templates distribution URL.
3. **Post-Mortem Investigation:**
   - Query private `arl-learning-raw` raw bucket for objects matching the malicious pattern.
   - Extract source hashes and add them to Edge KV blocklist (`BLOCKED_SOURCES_KV`).
   - Audit Aggregator regex and LLM synthesis filters.

### Runbook 3: Local Configuration Corruption / Delimiter Mutilation

1. **Symptom:** User reports agent config file (`CLAUDE.md`, `.cursorrules`) has duplicated or truncated rule blocks.
2. **Recovery Procedure:**

   ```bash
   ai-rule-learning clear --all
   ai-rule-learning status
   ai-rule-learning sync --dry-run
   ai-rule-learning sync
   ```

3. **Verification:** Inspect git diff (`git diff CLAUDE.md`) to verify clean, atomic delimiter insertion.

---

## 7. Security & Compliance Controls

- **Zero Unscrubbed Data Retention:** Raw contributions in `arl-learning-raw` are automatically purged after 30 days via R2 Object Lifecycle Policies (GDPR Article 5(1)(e)).
- **Cryptographic Attestation:** Every published template catalog contains a signed SHA-256 hash in `manifest.json`. Local clients verify this hash against the downloaded `templates.jsonl` prior to merging into local caches.
- **Local Secret Isolation:** The MCP server process runs under the executing user's privilege and never executes `sudo` or accesses external system directories outside the working project and `~/.ai-rule-learning`.

---

## 8. Operational Constraints & Production Boundaries (v0.3.0)

1. **Scheduled Cron Trigger Verification:** The aggregator cron schedule (`0 */6 * * *`) relies on Cloudflare Workers scheduled event triggers. In automated headless environments, live triggers must be continuously monitored via Cloudflare Logs beyond manual `/aggregate` and `/trigger-manual` endpoints.
2. **Automated QA Pipeline Scale:** The 12-test automated QA pipeline in the aggregator has been exercised and verified on synthetic corpus and mock R2 boundaries. Live community telemetry under high concurrency and real-world multi-client edge traffic is required to observe long-tail rule synthesis.
3. **HMAC Attestation Rollback:** Cryptographic HMAC attestation of `manifest.json` and `templates.jsonl` is active. However, emergency rollback from an active compromised release to a previous digest has been rehearsed in local staging and needs full automated failover verification during live drills.
4. **1% Traffic Canary Staging:** Canary deployment routing (Stage 4) isolates experimental rules to private staging. Production edge routing with weighted DNS/Cloudflare routing will be formally evaluated as community contributor volume scales.
5. **The 8 Out-of-Scope Catalog Rules:** While 122 of the 130 catalog rules (93.8%) strictly adhere to the 20–40 word envelope (averaging 23.9 words), 8 rules (`logical_fallacy_avoidance`, `regex_efficiency_and_safety`, `async_concurrency_correctness`, `dead_code_and_unused_import_elimination`, `semantic_versioning_compliance`, `iso8601_timestamp_format`, `respectful_boundary_enforcement`, `no_false_intimacy`) are concise imperatives ranging between 16 and 19 words. They are documented, fully cited, and scheduled for minor phrasing expansion in v0.3.1.
