# Full Project Audit

Date: 2026-10-23 · Package version: 0.2.6

This audit supersedes the 2026-07-13 snapshot (available in git history). It is a
current-state assessment, written to be honest rather than flattering: it records
what is shipped and tested, what is partial, and what is unbuilt or unvalidated.

## Executive summary

The project is a **portable, local-first trust layer** for AI guardrail rules:
it learns a user's corrections/preferences and writes them into the native config
of every AI coding tool on the machine, with PII scrubbing, a review gate, and an
audit trail.

Honest verdict in one line: **the delivery and governance layer is real and
well-tested; the autonomous-behavioural and community-intelligence pillars are
partially built and not yet independently validated.**

- **Proven:** cross-tool injection (Claude Code, Cursor, Windsurf, Copilot,
  Codex, AGENTS.md), faithful correction capture, PII scrubbing, safety gate,
  crash recovery, concurrent writes, and a measured behavioural lift from
  injected rules on a small model (+16 pts vs cold in the external v7.x harness).
- **Partial / unvalidated:** relevance selection ships but its real-world benefit
  depends on clients passing task context (unmeasured); community pattern
  detection has the clustering primitive but not per-cluster k-anonymity; the
  fine-tuning tier has an exporter but training is external and the corpus does
  not yet support true preference (DPO) data.

## Architecture

Single package, `ai_rule_learning_mcp` (20 modules), exposing **21 MCP tools**
plus a CLI. Local-first store with optional Cloudflare R2 sync.

| Area                         | Modules                                          | Status                                   |
| ---------------------------- | ------------------------------------------------ | ---------------------------------------- |
| MCP server + CLI             | `server.py`, `cli.py`                            | Stable                                   |
| Rule extraction              | `gap_detector.py`, `analyzer.py`, `providers.py` | Stable                                   |
| Storage + safety             | `store.py`, `injection.py`                       | Stable                                   |
| Injection (cross-tool)       | `injector.py`, `claude_md.py`                    | Stable (home/cwd coverage guarded)       |
| Catalog / community          | `catalog.py`, `community.py`                     | Stable; clustering added                 |
| Memory / skills              | `memory.py`, `skills.py`                         | Stable                                   |
| Scheduler / metrics          | `scheduler.py`, `metrics.py`                     | Stable                                   |
| **Relevance (new)**          | `similarity.py`                                  | Shipped — TF-IDF cosine, dependency-free |
| **Clustering (new)**         | `clustering.py`                                  | Shipped — single-linkage over signals    |
| **Fine-tuning export (new)** | `dataset.py`                                     | Shipped — SFT JSONL export               |
| **KPIs (new)**               | `kpi.py`                                         | Shipped — local-state snapshot           |

Design discipline (recorded in `docs/ROADMAP.md`): borrow ML engines, build only
the glue; no heavy dependencies (`torch`, `scikit-learn`, vector DB) in the
package; optimise the session-to-session loop, not client-owned within-session
behaviour.

## Test and CI status

- **mcp suite:** 475 passed, 2 skipped (39 test files).
- **root suite:** 430 passed @ **85% coverage** (29 test files).
- **Smoke test:** `test_smoke.py` — millisecond critical-path check.
- **E2E:** `test_e2e.py` — full user journeys over real files.
- **CI gate (every PR):** `ruff format --check` + `ruff check` (root; `mcp/` is
  excluded by design), `mypy src`, root `pytest`, `mcp/tests`, `compileall`,
  commit-lint, markdownlint, Gitleaks, dependency audit, semgrep.
- Behavioural benchmark is intentionally **not** in CI (needs a model + GPU); it
  runs in the external harness.

## Delivered this session (PRs, all merged)

| PR   | Change                                                                          |
| ---- | ------------------------------------------------------------------------------- |
| #281 | Single-Space HF deploy (no PRO requirement)                                     |
| #282 | Space build on Python 3.11 (matches package `requires-python`)                  |
| #283 | M02 (home flat-file injection) + R05 (store self-heals when its path is a file) |
| #284 | Phase 1 relevance selection + `ROADMAP.md`                                      |
| #285 | AGENTS.md as a first-class injection target                                     |
| #286 | Home/cwd coverage regression guard for all targets                              |
| #287 | Phase 3 community signal clustering                                             |
| #288 | Phase 4 fine-tuning dataset exporter                                            |
| #289 | Smoke test + KPI snapshot (doc + CLI)                                           |

## Open items (prioritised, honest)

| Item                              | Why it matters                                                                                                                                   | Where                          |
| --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------ |
| **Behavioural harness re-run**    | Gates both Phase 1's real-world value and whether Phase 4 training is worth it; the autonomous-improvement claim is still unvalidated post-fixes | External (GPU); user-run       |
| **Provenance in injected output** | "This rule is here because you said X" — finishes Phase 2; the `why` tool/evidence exists but isn't surfaced inline                              | In-repo (buildable)            |
| **Per-cluster k-anonymity**       | Completes Phase 3; needs per-source signal attribution the aggregator Worker does not emit                                                       | Cloudflare Worker (infra)      |
| **Before/after capture → DPO**    | Turns the SFT exporter into a real preference dataset                                                                                            | In-repo data-collection change |
| **0.2.7 release**                 | CHANGELOG `Unreleased` holds M02, R05, relevance, AGENTS.md, clustering, exporter, KPI, smoke                                                    | Maintainer-run                 |
| **Credential rotation**           | Previously-exposed secrets flagged earlier in development                                                                                        | Owner-run                      |

## Known limitations (unchanged truths)

- **Model-agnosticism vs fine-tuning:** fine-tuning applies only to open-weights
  models, not the flagship closed targets (Claude/GPT/Copilot/Cursor). It is an
  optional tier, not the main path.
- **Within-session adaptation is client-owned:** agents read their config once at
  session start and do not hot-reload, so mid-session learning reaches the
  current session only through the live MCP tool when a client re-queries. The
  product loop is session-to-session.
- **Thin, time-bound moat:** if an open cross-tool config standard wins (e.g.
  AGENTS.md), the "translate to N formats" value shrinks — hence AGENTS.md is now
  a first-class target rather than a competitor.
- **Clustering is lexical:** single-linkage TF-IDF can chain on common tokens at
  low thresholds; the default (0.5) avoids it. Higher quality would mean swapping
  in embeddings (a borrowed engine), not hand-tuning.

## Validation summary

| Gate                                      | Result                                               |
| ----------------------------------------- | ---------------------------------------------------- |
| Format / lint / type / build              | PASS                                                 |
| Unit + integration + e2e + smoke          | PASS (mcp 475, root 430)                             |
| Coverage                                  | 85% (≥ 80% threshold)                                |
| Security (Gitleaks / semgrep / dep audit) | PASS                                                 |
| Behavioural benchmark                     | Deferred to external harness (not re-run post-fixes) |
