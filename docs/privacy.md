# Privacy & Data Protection Policy (GDPR / CCPA)

**Version**: 2.2.0  
**Status**: Enforced  
**Target**: AI Rule Learning MCP  
**Effective Date**: 2026-04-16

---

## 1. Local-First Architecture

AI Rule Learning is built on a **privacy-first, local-first architecture**.
All learning, rule formulation, memory persistence, and guardrail enforcement
happen on the user's local machine inside `~/.ai-rule-learning/`.

- **Zero-Account Onboarding**: No tokens, logins, or API keys are required to use
  the MCP server, load guardrails, or receive community updates.
- **Client-Side Pre-persistence Scrubbing**: Personal Identifiable Information
  (PII) is detected and redacted **before** any rule or memory touches disk.
- **Opt-In Telemetry Only**: Telemetry sharing is strictly opt-in (`contribute: false` by default).

---

## 2. Multi-Layer PII Scrubbing Engine (`scrub_pii`)

PII scrubbing (`scrub_pii`) is applied on the write path (prior to disk storage
and HTTP transmission) and at the Cloudflare Relay Worker boundary (server-side defense in depth).

The engine automatically matches and redacts:

- **Email addresses** (`[EMAIL_REDACTED]`)
- **Absolute filesystem paths** across Linux (`/home/...`), macOS (`/Users/...`), and Windows (`C:\Users\...`) (`[PATH_REDACTED]`)
- **API keys, bearer tokens, and credentials** (`sk-...`, `ghp_...`, `hf_...`, `AKIA...`, `Bearer ...`) (`[TOKEN_REDACTED]`)
- **Passwords and secrets** (`password=...`, `secret:...`) (`[SECRET_REDACTED]`)
- **IPv4 and IPv6 addresses** (`[IP_REDACTED]`)
- **Social Security Numbers (SSNs)** (`[SSN_REDACTED]`)
- **Phone numbers** (`[PHONE_REDACTED]`)

---

## 3. GDPR Data Retention Policy & TTL (GDPR Art. 5(1)(e) — Storage Limitation) — CO01

We enforce strict data retention limits across local storage and cloud relay infrastructure:

- **Local Storage Retention**:
  - Local rules (`rules.jsonl`), memory (`memory.jsonl`), and skills (`skills.jsonl`) remain under the user's sole local control on their device until pruned or deleted.
  - Stale rules that have not been triggered within **90 days** (`STALE_DAYS = 90`) are flagged by `review_rules` / `arl health` for archival or removal.
- **Cloudflare Relay & KV Storage Retention (TTL)**:
  - Anonymized community contribution records stored in Cloudflare Workers KV (`CONTRIBUTIONS` namespace) are written with a mandatory hardware-enforced **Time-To-Live (TTL) of 90 days** (`expirationTtl: 7776000` seconds). After 90 days, individual contribution keys are automatically and permanently purged.
  - Ephemeral rate-limiting counters in KV expire automatically after **60 seconds** (`expirationTtl: 60` seconds).

---

## 4. Data Residency & International Transfers (GDPR Chapter V, Art. 44–49) — CO02

- **Local Processing Residency**: All primary data processing and storage (`~/.ai-rule-learning/`) resides **100% on the user's local device** in the user's jurisdiction.
- **Cloudflare Edge & KV Residency**: When optional community sync or contribution is used, requests are processed by Cloudflare Workers edge nodes and stored in Cloudflare Workers KV (with primary storage in EU/US regions under Cloudflare's Data Processing Addendum and Standard Contractual Clauses (SCCs)). Because contributed payloads contain exclusively anonymized statistical counters (`gap_type`, `severity`, `language`, `count`) and zero personal data, no PII crosses jurisdictional boundaries.

---

## 5. Lawful Basis & Explicit Consent Tracking (GDPR Art. 6(1)(a) & Art. 7) — CO03

Community contribution is disabled by default (`ARL_CONTRIBUTE=false`). When a user explicitly opts in by setting `ARL_CONTRIBUTE=true` or passing `contribute=True`, an explicit consent audit record is written to `~/.ai-rule-learning/consent.json` containing:

- `consented`: `true`
- `timestamp`: ISO-8601 UTC timestamp of the consent event
- `trigger`: The tool or command that initiated the opt-in contribution
- `fingerprint`: Deterministic SHA-256 fingerprint of the consent event

Consent may be revoked at any time via `record_consent(consent=False)` or `arl consent --revoke`.

---

## 6. Right to Erasure & Subject Rights (GDPR Art. 17)

- **Local Data Erasure**: Run `rm -rf ~/.ai-rule-learning/` or `arl clear` to delete all local rules, sessions, and memory.
- **Agent Instruction Files**: Run `arl clear` (or `remove_rules_all`) to strip all injected rule blocks from Claude Code, Cursor, Windsurf, GitHub Copilot, and OpenAI Codex.
