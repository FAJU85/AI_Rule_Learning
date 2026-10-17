# Privacy & GDPR Compliance Documentation

**Project**: AI Rule Learning MCP (`ai-rule-learning-mcp`)
**Version**: 0.2.0
**Effective Date**: 2026-04-16

---

## 1. Local-First Privacy Architecture

`ai-rule-learning-mcp` is designed as a **local-first** system. By default:

- All conversation parsing, gap detection, rule generation, memory storage, and skill management happen **100% locally** on your machine.
- Local data is stored in `~/.ai-rule-learning/` (or `$ARL_HOME`).
- No conversation transcripts, code snippets, file paths, or personal identifiers leave your machine during normal operation.
- Network connections only occur when you explicitly invoke community features (`sync_community`, `contribute_rules`, `record_consent`) or configure optional HuggingFace dataset backup (`HF_TOKEN` + `ARL_DATASET`).

---

## 2. Write-Path PII Scrubbing (`scrub_pii`)

Before any rule, feedback hint, session summary, or community contribution is written to disk (`~/.ai-rule-learning/rules.jsonl`) or transmitted over the network, `scrub_pii(text: str) -> str` is automatically applied to redact sensitive categories:

- **Email addresses** (`[EMAIL_REDACTED]`)
- **Absolute filesystem paths** across Linux (`/home/...`), macOS (`/Users/...`), and Windows (`C:\Users\...`) (`[PATH_REDACTED]`)
- **Bearer tokens, API keys, and secret tokens** (`sk-...`, `ghp_...`, `hf_...`, `AKIA...`, JWTs, `Bearer ...`) (`[TOKEN_REDACTED]`)
- **Password / secret assignments** (`password=...`, `secret:...`, `api_key=...`) (`[SECRET_REDACTED]`)
- **IPv4 and IPv6 addresses** (`[IP_REDACTED]`)
- **Social Security Numbers (SSNs)** (`[SSN_REDACTED]`)
- **Phone numbers** (`[PHONE_REDACTED]`)

---

## 3. GDPR Compliance & Data Protection

### 3.1 Lawful Basis & Explicit Consent (GDPR Art. 6(1)(a) & Art. 7) — `CO03`

Community telemetry contribution is **strictly opt-in** (`ARL_CONTRIBUTE=false` by default) and requires **explicit, informed, affirmative consent** before any network transmission can occur:

1. Calling `contribute_rules` or `contribute_gaps` without prior recorded consent is blocked and returns a consent required notice.
2. Users must explicitly grant consent via the `record_consent(consent=True)` tool (or `arl consent --grant`), which logs an auditable timestamped record in `~/.ai-rule-learning/consent.json`.
3. Users may withdraw consent at any time via `record_consent(consent=False)` (or `arl consent --revoke`), which immediately disables community contributions and records the withdrawal timestamp.

### 3.2 Data Minimization & Anonymization (GDPR Art. 5(1)(c))

When community contribution is enabled and consented to, only **4 aggregate statistical fields** are transmitted per gap pattern:

- `gap_type` (enum: `incomplete_response`, `context_loss`, `repetition`, `correction`, `preference`, `scope_creep`, `hallucination`, `security_risk`)
- `severity` (float `[0.0, 1.0]`)
- `language` (string, e.g., `python`, `typescript`, `general`)
- `count` (integer `[1, 10000]`)

Plus an irreversibly salted one-way hash (`source_hash`) for deduplication. Zero prompt text, zero code, and zero user identifiers are included.

### 3.3 Data Retention Policy & TTL (GDPR Art. 5(1)(e) — Storage Limitation) — `CO01`

We enforce strict data retention limits across both local storage and cloud relay infrastructure:

- **Local Storage Retention**:
  - Local rules (`rules.jsonl`), memory (`memory.jsonl`), and skills (`skills.jsonl`) remain under the user's sole local control on their device until pruned or deleted.
  - Stale rules that have not been triggered within **90 days** (`STALE_DAYS = 90`) are flagged by `review_rules` / `arl health` for archival or removal.
  - Processed conversation tracking hashes (`processed_ids.txt`) retain only short cryptographic hashes and can be purged at any time.
- **Cloudflare Relay & KV Storage Retention (TTL)**:
  - Anonymized community contribution records stored in Cloudflare Workers KV (`CONTRIBUTIONS` namespace) are written with a mandatory hardware-enforced **Time-To-Live (TTL) of 90 days** (`expirationTtl: 7776000` seconds). After 90 days, individual contribution keys are automatically and permanently purged.
  - Ephemeral rate-limiting counters in KV expire automatically after **60 seconds** (`expirationTtl: 60` seconds).

### 3.4 Data Residency & International Transfers (GDPR Chapter V, Art. 44–49) — `CO02`

- **Local Processing Residency**: All primary data processing and storage (`~/.ai-rule-learning/`) resides **100% on the user's local device** in the user's jurisdiction.
- **Cloudflare Edge & KV Residency**: When optional community sync or contribution is used, requests are processed by Cloudflare Workers edge nodes and stored in Cloudflare Workers KV (with primary storage in EU/US regions under Cloudflare's Data Processing Addendum and Standard Contractual Clauses (SCCs) where applicable). Because contributed payloads contain exclusively anonymized statistical counters (`gap_type`, `severity`, `language`, `count`) and no personal data, no PII crosses jurisdictional boundaries.
- **Optional HuggingFace Dataset Sync**: If the user configures `HF_TOKEN` and `ARL_DATASET`, data residency is governed by the user's HuggingFace Hub account region (US or EU region selection).

### 3.5 Right to Erasure / Right to be Forgotten & Subject Rights (GDPR Art. 15, Art. 17, Art. 20)

- **Right to Erasure (Art. 17)**:
  - **Local Data**: Run `rm -rf ~/.ai-rule-learning/` or use `delete_rule`, `forget`, and `delete_skill` tools to erase specific records immediately.
  - **Injected Agent Files**: Run `arl clear` (or `inject_rules` with empty rules) to strip all injected blocks from `CLAUDE.md`, `.cursor/rules/`, `.windsurf/`, `.github/copilot-instructions.md`, and `.codex/instructions.md`.
  - **Consent & Telemetry**: Revoke consent via `record_consent(consent=False)`.
- **Right of Access & Portability (Art. 15 & Art. 20)**:
  - All local records are stored in human-readable, portable JSON Lines (`.jsonl`) and JSON (`.json`) formats inside `~/.ai-rule-learning/` and can be inspected or exported at any time via `list_rules`, `list_memory`, and `list_skills`.
