# Project Analysis & Debugging Report

**Project:** AI Rule Learning MCP System (`ai-rule-learning`)
**Repository:** <https://github.com/FAJU85/AI_Rule_Learning>
**Reviewed commit:** `659905a` (`fix: enforce MCP SDK version and update rule management`)
**Review date:** 2026-10-19
**Target release:** `v0.3.0`
**Overall status:** **~80% complete for the v0.3.0 baseline; not release-safe as packaged**

---

## 1. Project Overview

### 1.1 What it is

AI Rule Learning MCP is a local Model Context Protocol (MCP) server and CLI that turns repeated
AI-session friction (corrections, repeated context, unsafe tool use) into persistent, injectable
guardrails. It selects at most 10 rules within a 500-token budget from a curated 130-rule literature
catalog, writes them into agent configuration files (`CLAUDE.md`, `.cursorrules`,
`.windsurfrules`, `.github/copilot-instructions.md`), and optionally contributes anonymised failure
telemetry to a Cloudflare R2/KV community pipeline.

### 1.2 Objectives (from PRD/SRE)

1. Automatically detect recurring agent mistakes and extract actionable rules.
2. Select context-relevant rules under hard caps: **≤10 rules / ≤500 tokens**.
3. Inject guardrails idempotently and reversibly into supported agent configs.
4. Operate with **zero credentials** for local use and community catalog consumption.
5. Preserve privacy through local-only rule storage, PII scrubbing and k-anonymity (`k ≥ 5`).
6. Publish a signed, immutable, citation-backed community catalog through Cloudflare edge services.

### 1.3 Scope

- **In scope:** local MCP server, CLI, memory, skills, rule lifecycle, config injection, scheduler,
  rule catalog/selection engine, Cloudflare relay + aggregator + R2/KV distribution, Hugging Face
  Space demo/dashboard.
- **Out of scope:** model training, multi-tenant SaaS, authenticated user accounts, relational
  database, billing.

### 1.4 Key deliverables

| Deliverable                                                 | State                                             |
| :---------------------------------------------------------- | :------------------------------------------------ |
| `ai-rule-learning-mcp` PyPI package with MCP server and CLI | Implemented, **wheel is incomplete (P0)**         |
| 21 MCP tools and lifecycle CLI                              | Implemented and tested                            |
| 130-rule cited catalog                                      | Implemented and verified (130 rules, 100% cited)  |
| Context-aware selector (≤10 rules / ≤500 tokens)            | Implemented; bypass in MCP path fixed             |
| Agent-config injector for 4 targets                         | Implemented and tested                            |
| Cloudflare relay/aggregator (Hono + Zod)                    | Source implemented; **deployed contract differs** |
| 7-field provenance + k-anonymity governance                 | Partially implemented; defaults/edge drift found  |
| Test suites and CI gates                                    | 782 Python tests + 7 space tests passing          |

### 1.5 Priority and status

- **Priority:** high for the local MCP/CLI surface (primary user value); medium for the community
  backend.
- **Status:** feature-complete for the documented local workflow, but **packaging and
  deployment-parity defects block a credible v0.3.0 release**.

---

## 2. Current Work Status

### 2.1 Accomplished

- Local MCP server exposing **21 tools** (`list_rules`, `approve_rule`, `reject_rule`, `edit_rule`,
  `merge_rules`, `record_feedback`, `sync_sessions`, `remember`, `recall`, `save_skill`,
  `list_skills`, `get_skill`, `get_guardrail_rules`, `why`, `analyze`, `review_rule_health`,
  `suggest_duplicate_rules`, `record_rule_outcome`, `install_scheduler`,
  `update_community_knowledge`, `list_providers`).
- CLI with sync/status/rules/memory/skills/scheduler/metrics commands and `--dry-run` coverage.
- Local JSONL persistence, PII scrubbing, injection scanning, atomic file writes, rule lifecycle.
- 130-rule static catalog with citations; verified average 23.88 words and 8 documented exceptions.
- Cloudflare relay and aggregator implementations plus legacy `worker.js` / `aggregator.js`.
- Python tests: **418 root + 364 MCP + 7 space = 789 passing**; 87% root coverage.
- Root CI (`ci.yml`) runs format, lint, mypy, both test suites and compileall.

### 2.2 In progress / incomplete

- Reconciling the **repository Cloudflare source** with the **live deployed workers**.
- Making the published MCP wheel self-contained (currently imports a missing top-level `src`).
- Validating live cron triggers, HMAC rollback and canary routing (documented as outstanding in
  SRE §8 / PRD §8).
- Owner-dashboard expansion and privacy-preserving adoption metrics (ROADMAP near-term).

---

## 3. Technology Stack

| Layer            | Technology                                                                        |
| :--------------- | :-------------------------------------------------------------------------------- |
| Language/runtime | Python 3.11 (package supports 3.10–3.12), Node.js 24 for tooling                  |
| MCP              | `mcp` SDK 1.30.0 (pinned `>=1.0.0,<2.0.0`)                                        |
| Data/validation  | Pydantic 2, `jsonschema`, JSON/JSONL                                              |
| Analytics (root) | NumPy, pandas, scikit-learn; optional OpenAI/Anthropic clients                    |
| UI/demo          | Gradio 5.29 (`space/app.py`), Plotly                                              |
| Edge             | Cloudflare Workers, TypeScript, Hono 4, Zod 3, R2, KV                             |
| Storage          | Local JSONL + JSON; no relational database                                        |
| Tooling          | pytest/pytest-cov, ruff, mypy, prettier, markdownlint, husky, commitlint, semgrep |
| CI/CD            | GitHub Actions (`ci.yml`, `publish-mcp.yml`, `deploy-space.yml`, `security.yml`)  |

---

## 4. Code Structure

```text
src/                      # Root "core" Python package (catalog, CLI, adapters, models)
├── adapters/             # Claude/OpenAI conversation adapters
├── cli/                  # Root CLI entry point
├── core/                 # Catalog selector, gap detector, interceptor, rule engine
├── models/               # Conversation and rule models
├── services/             # Analysis and validation services
└── utils/                # Embeddings, logging, sentiment

mcp/ai_rule_learning_mcp/ # Published MCP package (server, CLI, storage, injection)
├── server.py             # 21 MCP tools (1,762 lines)
├── cli.py                # CLI surface (667 lines)
├── store.py              # JSONL persistence, PII scrubbing, lifecycle (830 lines)
├── gap_detector.py       # Heuristic failure detection + rule generation
├── injection.py          # Two-stage prompt-injection detection
├── injector.py           # Delimited agent-config injection
├── community.py          # Relay/CDN client, k-anonymity merge, consent
├── memory.py / skills.py # Cross-session memory and skill library
├── scheduler.py          # LaunchAgent/systemd/cron scheduler
└── data/                 # Bundled offline rules

data/                     # 130-rule catalog, context schema, metrics, bundled rules
cloudflare/src/           # TypeScript relay, aggregator and Zod schemas
space/                    # Gradio dashboard (16k-line app.py)
tests/                    # Root test suite
mcp/tests/                # MCP test suite
docs/                     # Architecture, schema, security, privacy, runbooks
scripts/                  # Catalog build, blue/green deploy, session export
```

---

## 5. Data Stores and Schema

There is **no relational database**. Persistence is file/object based:

| Store                                | Location                                       | Purpose                                        |
| :----------------------------------- | :--------------------------------------------- | :--------------------------------------------- |
| `rules.jsonl`                        | `~/.ai-rule-learning/` and optional HF dataset | Rule records, lifecycle, provenance            |
| `memory.jsonl`                       | `~/.ai-rule-learning/`                         | Cross-session preferences/facts                |
| `skills/<slug>.md`                   | `~/.ai-rule-learning/skills/`                  | Reusable procedures                            |
| `processed.jsonl`                    | `~/.ai-rule-learning/`                         | Session de-duplication                         |
| `active_rules.json`                  | repo `data/` + user dir                        | Last selection with token metrics              |
| `catalog_v1.json`                    | repo `data/`                                   | Immutable 130-rule catalog                     |
| `arl-contributions` (R2)             | private                                        | Raw sanitized telemetry                        |
| `arl-templates` (R2)                 | public                                         | `templates.jsonl` + signed manifest            |
| `CONTRIBUTIONS_KV` / `RATE_LIMIT_KV` | Cloudflare KV                                  | Telemetry metadata (90-day TTL) / 60s counters |

`rules.jsonl` uses a 28-field local schema with seven mandatory provenance fields:
`source_session_id`, `extraction_version`, `extracted_at`, `review_status`, `reviewed_by`,
`reviewed_at`, `qa_report_id` (see `docs/schema.md`).

---

## 6. Debugging Findings

Severity: **P0** release-blocking, **P1** security/data-integrity, **P2** correctness/docs,
**P3** maintainability.

| ID   | Severity | Finding                                                                                                             | Status                     |
| :--- | :------- | :------------------------------------------------------------------------------------------------------------------ | :------------------------- |
| D-01 | P0       | Published MCP wheel omits the `src` package but `server.py`/`cli.py` import `src.core.catalog`                      | **Open**                   |
| D-02 | P1       | Pending/unapproved rules were injected into agent configs                                                           | **Fixed**                  |
| D-03 | P1       | Community k-anonymity default was 3, contradicting the documented `k ≥ 5` invariant                                 | **Fixed**                  |
| D-04 | P1       | Combined local+catalog selection could exceed 500 tokens; `active_rules.json` hard-coded `token_count: 300`         | **Fixed**                  |
| D-05 | P1       | TypeScript relay used stateful `/g` regexes with `.test()`, allowing intermittent PII bypass                        | **Fixed**                  |
| D-06 | P1       | Live relay contract diverges from repository source (`/api/contribute` + 202 vs `/contribute` + 201/7-field schema) | **Open**                   |
| D-07 | P1       | Admin/aggregate endpoints fail open when `ADMIN_KEY` is unset                                                       | **Open**                   |
| D-08 | P1       | Wheel omitted `data/bundled_rules.jsonl`, breaking zero-credential offline fallback                                 | **Fixed**                  |
| D-09 | P2       | Live-network test used an 8s timeout while `/aggregate` takes ~10s → deterministic failure                          | **Fixed**                  |
| D-10 | P2       | README scheduler section was triplicated/corrupted with unbalanced code fences                                      | **Fixed**                  |
| D-11 | P2       | Root dev instructions did not install the MCP package, so a fresh `pytest` failed collection                        | **Fixed**                  |
| D-12 | P2       | `npm ci` was used in CI without a committed `package-lock.json`                                                     | **Fixed (lockfile added)** |
| D-13 | P2       | Retention documentation conflicts: 30-day R2 purge vs 90-day KV TTL, no R2 lifecycle config                         | **Open**                   |
| D-14 | P2       | Cron schedule documented as every 6 hours, code says hourly                                                         | **Open**                   |
| D-15 | P2       | Architecture docs list catalog categories that do not match `catalog_v1.json`                                       | **Open**                   |
| D-16 | P2       | Three different versions coexist: root `0.1.0`, MCP `0.2.1`, target `0.3.0`                                         | **Open**                   |
| D-17 | P2       | k-anonymity trusts client-declared `source_hash`; one client can forge ≥5 “sources”                                 | **Open (design)**          |
| D-18 | P3       | Duplicate function bodies/imports in `space/app.py`                                                                 | **Open**                   |
| D-19 | P3       | Pydantic v1-style `class Config` emits deprecation warning                                                          | **Open**                   |
| D-20 | P3       | Documented consent revocation (`record_consent(consent=False)`, `arl consent --revoke`) is not implemented          | **Open**                   |
| D-21 | P3       | `write_rules_all` silently swallows all target-write exceptions                                                     | **Open**                   |
| D-22 | P3       | Root wheel contains top-level `core/`, `cli/`, etc. instead of `src/`; root `pyproject` declares no dependencies    | **Open**                   |
| D-23 | P3       | `app.py` performs runtime `pip install` and writes `/etc/pip.conf`                                                  | **Open**                   |

### 6.1 Reproduction evidence

#### D-01 — MCP wheel is not runnable from a clean install

```text
$ python -m build --wheel ./mcp && unzip -l ai_rule_learning_mcp-0.2.1-py3-none-any.whl
ai_rule_learning_mcp/*.py        # 15 modules
# no src/ directory

$ PYTHONPATH=/tmp/wheel python -c "await server._get_guardrail_rules(dry_run=True)"
ModuleNotFoundError: No module named 'src'
```

Imports at `mcp/ai_rule_learning_mcp/server.py:855`, `server.py:924` and `cli.py:590` make the
primary tool and `why`/`analyze` paths fail for every PyPI user. This is the highest-priority
release blocker.

#### D-02 — Pending rules reached agent configs

`gap_detector.generate_rules()` emitted `is_active: True` together with `review_status: "pending"`,
and `store.load_active_rules()` only checked `is_active`. A probe with 12 pending rules returned all
12 as injectable. Fixed by emitting `is_active: False` and adding a lifecycle gate in
`load_active_rules()`; `record_feedback()` still activates rules because it represents explicit
user approval.

#### D-03 — k-anonymity default

`community.build_community_templates()` and the MCP tool defaulted to `min_sources=3`, while
PRD/SRE/security docs require `k ≥ 5`. Fixed defaults to 5; explicit overrides remain possible.

#### D-04 — Token-budget and metric integrity

`_get_guardrail_rules()` combined up to 10 local rules with catalog rules but never re-checked the
500-token ceiling, and persisted `accumulated_tokens=300` unconditionally. A probe showed the
reported value was 300 while the actual estimate was 373. Fixed by measuring the formatted block and
trimming until `≤500`, then persisting the real count.

#### D-05 — Stateful PII regex (CWE-185 class)

All `PII_PATTERNS` in `cloudflare/src/relay/index.ts` use `/g` and were probed with `regex.test()`.
Node confirms the statefulness:

```text
1st: true 7
2nd: false 0
```

On a warm isolate the second request containing the same PII can skip the email pattern. Fixed by
resetting `regex.lastIndex = 0` before each probe.

#### D-06 — Deployment drift

| Check                   | Live endpoint                             | Repository TS source                 |
| :---------------------- | :---------------------------------------- | :----------------------------------- |
| Valid contribution      | `POST /api/contribute` → **202 Accepted** | `POST /contribute` → **201 Created** |
| Required provenance     | Not enforced (4-field payload accepted)   | 7-field Zod schema required          |
| `/api/health`           | 404                                       | Implemented                          |
| `/health` service field | `community-relay`                         | `ai-rule-learning-relay`             |
| PII / injection         | 400 rejections                            | 400 rejections                       |

The audit test suite targets the live legacy contract, not the TypeScript source, so CI can pass
while the v0.3.0 “7-field provenance” claim is not true in production.

#### D-07 — Fail-open admin authentication

`if (env.ADMIN_KEY && auth !== ...)` skips authentication when the secret is absent. The live
`POST /aggregate` succeeded without credentials. An unset secret must deny, not allow.

---

## 7. Fixes Applied in This Session

| File                                            | Change                                                                                                                                               |
| :---------------------------------------------- | :--------------------------------------------------------------------------------------------------------------------------------------------------- |
| `mcp/ai_rule_learning_mcp/gap_detector.py`      | Generated rules default to `is_active: False`, `status: pending`                                                                                     |
| `mcp/ai_rule_learning_mcp/store.py`             | `load_active_rules()` excludes pending/rejected/merged/stale/needs-review rules                                                                      |
| `mcp/ai_rule_learning_mcp/server.py`            | Explicit feedback approval activates rules; combined rule set is trimmed to ≤500 tokens; real token count persisted; k-anonymity default raised to 5 |
| `mcp/ai_rule_learning_mcp/community.py`         | Default `min_sources` raised from 3 to 5                                                                                                             |
| `mcp/pyproject.toml`                            | Added package-data for `data/*.jsonl` and `data/*.json`                                                                                              |
| `cloudflare/src/relay/index.ts`                 | Reset global-regex `lastIndex` before PII probes                                                                                                     |
| `mcp/tests/test_audit_verification_matrix.py`   | Aggregator timeout raised from 8s to 30s                                                                                                             |
| `mcp/tests/test_store.py`                       | Regression test: pending/rejected rules are not injectable                                                                                           |
| `mcp/tests/test_community_rag.py`               | Regression test: default threshold is k=5                                                                                                            |
| `mcp/tests/test_token_budget.py`                | Regression test: combined local rules respect 500 tokens                                                                                             |
| `mcp/tests/test_gap_detector.py`, `test_e2e.py` | Updated expectations to require approval before injection                                                                                            |
| `README.md`                                     | Rebuilt the corrupted scheduler section                                                                                                              |
| `requirements-dev.txt`                          | Added `-e ./mcp` so local `pytest` collection works                                                                                                  |
| `.prettierignore`, `.gitignore`                 | Excluded `.cline-home`, `.venv`, `mcp/dist`                                                                                                          |
| `package-lock.json`                             | Committed lockfile required by `npm ci` in CI                                                                                                        |

---

## 8. Verification Gate

All commands were executed from the repository root on 2026-10-19.

| Gate                 | Command                                | Result                                                 |
| :------------------- | :------------------------------------- | :----------------------------------------------------- |
| Format               | `ruff format --check .`                | **PASS** (96 files)                                    |
| Format (docs/config) | `npm run format:check`                 | **PASS**                                               |
| Lint                 | `ruff check .`                         | **PASS**                                               |
| Type check           | `mypy src`                             | **PASS** (24 files)                                    |
| Root tests           | `pytest`                               | **PASS** 418 tests, 87% coverage (threshold 80%)       |
| MCP tests            | `pytest -c /dev/null mcp/tests`        | **PASS** 364 tests                                     |
| Space introspection  | `pytest space/test_mcp_introspect.py`  | **PASS** 7 tests                                       |
| Cloudflare build     | `npm run build` (`tsc --noEmit`)       | **PASS**                                               |
| JS syntax            | `node --check worker.js aggregator.js` | **PASS**                                               |
| Wheel data           | inspect built wheel                    | `bundled_rules.jsonl` present                          |
| Wheel runtime        | import clean wheel                     | **FAIL** — `ModuleNotFoundError: src` (D-01)           |
| Space smoke          | `space/test_app_smoke.py`              | **SKIPPED** — Gradio not installed in this environment |

---

## 9. Dependencies, Constraints and Risks

### 9.1 External services and third-party dependencies

- **Cloudflare Workers, R2, KV** for telemetry/catalog; availability and IAM misconfiguration are
  the main external failure modes.
- **PyPI** distribution and **MCP SDK 1.x** compatibility (`<2.0.0` ceiling).
- **Hugging Face** optional backup/dataset sync and Space hosting; not required for local use.
- **LLM providers** (OpenAI/Anthropic) only for optional root analysis, not for MCP core.
- Runtime Python dependencies include pydantic, numpy/pandas, scikit-learn, Gradio (Space only).

### 9.2 Technical risks

1. **Broken distribution (D-01):** the headline MCP tools do not work for PyPI consumers.
2. **Deployment/source divergence (D-06):** security guarantees cannot be inferred from repo code.
3. **Fail-open admin auth (D-07):** unauthenticated aggregation/admin actions if `ADMIN_KEY` missing.
4. **Weak k-anonymity identity (D-17):** `source_hash` is self-asserted; quorum can be Sybil'd.
5. **Live-network unit tests:** 17 audit tests depend on external endpoints rather than mocks,
   making the suite non-hermetic and slow (~22s).
6. **Retention ambiguity (D-13):** legal/privacy documents disagree and R2 lifecycle rules are not
   codified in `wrangler.toml`.
7. **Dual implementation drift:** root `src/` and `mcp/` both implement catalog/detection logic.
8. **Generated artifacts tracked:** `active_rules.json` changes on every test run.

### 9.3 Constraints and requirements

- Python 3.10–3.12; development verified on 3.11.
- `mcp>=1.0.0,<2.0.0` is a hard compatibility ceiling.
- No credentials required for local operation or catalog consumption.
- Prompt-injection/PII rejection must occur before persistence/transmission.
- ≤10 rules and ≤500 tokens are hard injection invariants.
- 80% minimum root coverage; currently 87%.

---

## 10. Recommendations (Priority Order)

1. **Fix D-01 before any release:** vendor the catalog/selection core into the MCP wheel (with
   `catalog_v1.json`/`context_schema.json`) or publish a shared `ai-rule-learning-core` package and
   depend on it. Add a wheel-install smoke test to `publish-mcp.yml`.
2. **Reconcile Cloudflare source and deployment (D-06):** deploy the TypeScript implementation or
   delete it, align routes/status codes/provenance, and run contract tests against the deployed
   worker.
3. **Make admin auth fail closed (D-07):** require `ADMIN_KEY` for `/aggregate`, `/admin/approve`,
   `/admin/reject`; return 503/401 when unset.
4. **Prove independent sources (D-17):** sign contributions or derive source identity server-side;
   do not trust client `source_hash` for quorum.
5. **Unify retention policy (D-13):** set an R2 lifecycle rule for raw objects (30 days) and document
   KV 90-day TTL separately.
6. **Make tests hermetic:** gate live integration tests behind `ARL_LIVE_TESTS=1`; mock HTTP in unit
   suites.
7. **Reconcile docs/versions (D-14–D-16):** correct cron cadence, category list, and adopt one
   versioning scheme.
8. **Fix root packaging (D-22) and remove `src` coupling** so both distributions are installable.
9. **Implement consent revocation (D-20)** or remove the claim from `docs/privacy.md`.
10. **Clean up `space/app.py` (D-18)** and remove runtime `pip install` behavior (D-23).

---

## 11. Assumptions and Limitations

- The assessment treats `PRD.md` and `SRE.md` as the specification of record; where code and docs
  disagree, both are reported rather than silently reconciled.
- Live endpoint checks were read-only except for three small telemetry probes and one `/aggregate`
  call using test hashes.
- Gradio-dependent Space smoke tests were not executed because Gradio is not installed in the
  analysis environment.
- The live deployment could not be mapped to a specific commit; the observed contract is reported
  as-is.
- Completion percentage (~80%) is an estimate based on delivered features minus open P0/P1 defects.
