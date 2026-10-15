# Privacy & Data Protection Policy

Version: 2.1.0
Status: Enforced
Target: AI Rule Learning MCP

---

## 1. Overview & Principles

AI Rule Learning is built on a **privacy-first, local-first architecture**.
All learning, rule formulation, memory persistence, and guardrail enforcement
happen on the user's local machine inside `~/.ai-rule-learning/`.

- **Zero-Account Onboarding**: No tokens, logins, or API keys are required to use
  the MCP server, load guardrails, or receive community updates.
- **Client-Side Pre-persistence Scrubbing**: Personal Identifiable Information
  (PII) is detected and redacted **before** any rule or memory touches disk.
- **Opt-In Telemetry Only**: Telemetry sharing is strictly opt-in (`contribute: false` by default).

---

## 2. What Is Collected (When Opted-In)

When community telemetry is explicitly enabled, only high-level structural gap
metadata is transmitted:

1. **Gap Category & Type**: Abstract friction labels (e.g. `explicit_correction`,
   `user_preference`, `repeated_context`, `incomplete_response`).
2. **Frequency Counts**: Aggregate counters of occurrences within a session.
3. **Turn Number**: Position within the conversation where the friction occurred.
4. **Scrubbed Trigger Phrase**: Short, sanitized trigger signals (truncated to 120 chars)
   with all PII replaced by tokens.
5. **Session Hash**: A one-way SHA-256 hash of the session identifier used solely
   for deduplication.

---

## 3. What Is NEVER Collected or Stored

- **No Raw Conversation Text**: Full prompts, system prompts, or agent completions
  are never shared.
- **No User Code or File Contents**: Application code, scripts, and repository contents
  remain local.
- **No User Identity or Accounts**: No usernames, emails, IP addresses, or personal
  account details are associated with contributions.
- **No File Paths or Filenames**: Absolute paths, home folders, and project names are redacted.
- **No Secrets, Tokens, or API Keys**: Passwords, PATs, cloud keys, and tokens are blocked.

---

## 4. Multi-Layer PII Scrubbing Engine

PII scrubbing (`scrub_pii`) is applied at both the client boundary (prior to disk storage
and transmission) and at the Cloudflare Relay Worker boundary (server-side defense in depth).

The engine automatically matches and redacts:

| PII Category               | Pattern Matched                                         | Replacement Token |
| :------------------------- | :------------------------------------------------------ | :---------------- |
| **Email Addresses**        | RFC-compliant email expressions                         | `[EMAIL]`         |
| **Home & User Paths**      | `/home/*`, `/Users/*`, `C:\Users\*`                     | `[HOME]`          |
| **System Paths**           | Absolute filesystem paths (`/var/*`, `/etc/*`, etc.)    | `[PATH]`          |
| **IPv4 Addresses**         | Standard IPv4 octet addresses                           | `[IP]`            |
| **IPv6 Addresses**         | Full and abbreviated IPv6 addresses                     | `[IP]`            |
| **Phone Numbers**          | International and domestic phone formats                | `[PHONE]`         |
| **API Keys & Credentials** | `hf_`, `sk-`, `ghp_`, `gho_`, `github_pat_`, AWS, Slack | `[TOKEN]`         |

---

## 5. Community Architecture & Staging

Unlike public repository models where contributions are published immediately to web indices,
AI Rule Learning uses a **private staging pipeline**:

1. **Write Relay (Cloudflare Worker)**: Validates payload size (≤64KB), scans for PII and
   injection patterns, and writes valid payloads to a **private, unindexed R2 storage bucket**.
2. **Aggregator Worker (Cron)**: Periodically processes the private staging bucket.
3. **K-Anonymity Enforcement**: Patterns are published to the public CDN only when verified
   across **5 or more independent sources** (`min_sources >= 5`).
4. **Data Minimization & Deletion**: Raw staging contributions are ephemeral and eligible
   for routine lifecycle pruning.

---

## 6. Compliance

The data processing pipeline is designed to comply with:

- **GDPR (Regulation (EU) 2016/679)**: Data minimization, purpose limitation, and privacy by design.
- **CCPA / CPRA**: No sale of personal data; zero personal identifier linkage.
