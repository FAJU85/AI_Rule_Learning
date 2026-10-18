# AI Rule Learning System — Architecture Specification

**Version:** 0.3.0  
**References:** ARL-SPRINT-001, ARL-REM-2026-007, ARL-BLD-2026-001  
**Architecture:** Static Catalog + Dynamic Selection + Cloudflare R2 Community Backend

---

## 1. Architectural Overview

The AI Rule Learning System operates on a **Static Catalog + Dynamic Selection** paradigm. Rule content is curated from peer-reviewed literature and industry standards (`data/catalog_v1.json`). No rule instructions are dynamically generated from user conversations, eliminating prompt injection and PII leakage risks by design.

```text
┌────────────────────────────────────────────────────────────────────────┐
│                              LOCAL SYSTEM                              │
│                                                                        │
│   ┌────────────────────┐     Context Detection     ┌───────────────┐   │
│   │ 130-Rule Literature│ ────────────────────────> │ Selection     │   │
│   │ Catalog (Static)   │                           │ Engine        │   │
│   └────────────────────┘                           └───────┬───────┘   │
│                                                            │           │
│   ┌────────────────────┐     Delimited Injection           ▼           │
│   │ Agent Configs      │ <──────────────────────── 10 Rules / 500 Tok  │
│   │ CLAUDE.md, etc.    │                           active_rules.json   │
│   └────────────────────┘                                               │
└────────────────────────────────────┬───────────────────────────────────┘
                                     │ Direct HTTPS (Zero Credential)
                                     ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        CLOUDFLARE EDGE PLATFORM                        │
│                                                                        │
│   ┌────────────────────┐     Private Staging       ┌───────────────┐   │
│   │ Relay Worker       │ ────────────────────────> │ arl-learning- │   │
│   │ (Hono + Zod)       │                           │ raw (R2)      │   │
│   └────────────────────┘                           └───────┬───────┘   │
│                                                            │ Hourly    │
│   ┌────────────────────┐     Signed Catalog                ▼           │
│   │ Public Distribution│ <──────────────────────── │ Aggregator    │   │
│   │ arl-catalog (R2)   │                           │ Worker (Cron) │   │
│   └────────────────────┘                           └───────────────┘   │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Decoupling & Separation of Hugging Face

### 2.1 HF Dataset Dropped (Community Backend)

- **Status:** **REMOVED & DISCONTINUED.**
- **Rationale:** Relying on Hugging Face Datasets required users to maintain an active `HF_TOKEN`, introduced heavy dependencies (`huggingface_hub`, `datasets`), and created centralized security attack surfaces.
- **Replacement:** Cloudflare R2 (`arl-learning-raw` private bucket + `arl-catalog` public bucket) via edge Worker relay (`POST /contribute`) and aggregator cron. Reading public catalog templates requires **zero tokens and zero credentials**.

### 2.2 HF Spaces Kept (Public Demonstration)

- **Status:** **RETAINED AS STANDALONE DEMO.**
- **Repository Location:** `space/app.py` at `vooom/AI_Rule_Learning`.
- **Purpose:** Public Gradio web application for visual exploration of the 130-rule catalog, interactive selection simulation, and community transparency.
- **Enforcement:** Enforced by regression test `tests/test_hf_independence.py`. MCP core package (`mcp/ai_rule_learning_mcp/`) contains zero imports of `huggingface_hub`.

---

## 3. Local Runtime Engine

### 3.1 130-Rule Catalog

Located at `data/catalog_v1.json`. Divided into 10 failure categories:

1. `behavioral_alignment` (sycophancy, hallucinated apologies)
2. `instruction_drift` (language drift, parameter drift)
3. `hallucination` (invented APIs, fake CLI flags)
4. `reasoning_failure` (off-by-one, boundary math)
5. `code_quality` (missing error guards, resource leaks)
6. `security` (injection, path traversal, hardcoded secrets)
7. `context_exhaustion` (token bloat, missing summaries)
8. `tool_misuse` (unvalidated bash calls, malformed JSON)
9. `verbosity` (unsolicited prose before code)
10. `operational_discipline` (test before declare)

### 3.2 Dynamic Context Selection

- Detects language, framework, task type, and git changes.
- Greedily selects highest-priority matching rules.
- Enforces hard ceilings: **$\le 10$ rules** and **$\le 500$ real tokens**.
- Falls back to priority-5 universal rules on empty context.

### 3.3 Target Injector

Idempotently injects rules, memory, and skills into:

- Anthropic Claude Code: `CLAUDE.md`
- Cursor: `.cursorrules` / `.cursor/rules/`
- Windsurf: `.windsurfrules` / `.windsurf/rules/`
- GitHub Copilot: `.github/copilot-instructions.md`

---

## 4. Community Backend Architecture

- **Edge Relay:** TypeScript + Hono + Zod running on Cloudflare Workers.
- **Private Raw Staging:** Cloudflare R2 bucket `arl-learning-raw` with 30-day lifecycle expiration (GDPR Art. 5(1)(e)).
- **Public Catalog Distribution:** Cloudflare R2 bucket `arl-catalog` with HMAC-signed `manifest.json` and canonical `templates.jsonl`.
- **Scheduled Aggregator:** Executes every 6 hours (`0 */6 * * *`), enforcing $k \ge 5$ distinct source quorum and 12-test automated QA before catalog publication.
