# Product Gaps and Improvement Plan

This document captures current product risks and the next improvements needed to make AI Rule
Learning MCP more useful for real users.

---

## 1. Unknown User Adoption

### Adoption Problem

People may be installing or trying the tool, but the project currently has no reliable way to answer:

- How many people use it?
- Which commands are used most?
- Where do users fail during setup?
- How many users return after first install?

Without this, roadmap decisions are based on guesses instead of evidence.

### Principles

Any adoption measurement must be:

- opt-in,
- transparent,
- privacy-preserving,
- easy to disable,
- documented before it ships.

### Adoption Proposed Solution

Add an opt-in local metrics system that can answer basic product questions without collecting raw
conversation content, prompts, code, secrets, file paths, or personal data.

Suggested metrics:

| Metric                          | Why it matters                                           |
| ------------------------------- | -------------------------------------------------------- |
| install or first-run event      | Understand whether packaging and onboarding are working. |
| command usage counts            | See which CLI/MCP features are valuable.                 |
| setup failure category          | Find confusing or broken setup paths.                    |
| rule count buckets              | Understand whether users are actually generating rules.  |
| scheduler enabled yes/no        | Understand whether automation is trusted.                |
| anonymous version and OS bucket | Prioritize compatibility work.                           |

### Adoption Acceptance Criteria

- Metrics are disabled by default unless the maintainer explicitly chooses otherwise.
- Users can inspect exactly what would be sent before enabling metrics.
- Users can disable metrics with one command or environment variable.
- No raw conversation text or memory content is collected.
- Documentation explains the data model and retention policy.

---

## 2. Tool Does Not Learn Enough From Users

### Learning Problem

The tool can create and store rules, but the learning loop is still too passive. Users need a clear
way to teach the system which rules are useful, wrong, noisy, duplicated, or missing.

### Learning Proposed Solution

Build an explicit feedback loop around generated rules:

1. Show newly generated rules in a pending state.
2. Ask users to approve, reject, edit, or merge rules.
3. Track whether approved rules actually prevent repeated mistakes.
4. Detect stale or low-value rules.
5. Suggest improvements when similar feedback appears repeatedly.

### CLI example

```bash
ai-rule-learning rules pending
ai-rule-learning rules approve <rule-id>
ai-rule-learning rules reject <rule-id>
ai-rule-learning rules edit <rule-id>
ai-rule-learning rules merge <rule-id> <rule-id>
ai-rule-learning rules outcome <rule-id> --worked
ai-rule-learning rules outcome <rule-id> --failed
```

### Product behavior

Rules should have clear lifecycle states:

| State          | Meaning                                          |
| -------------- | ------------------------------------------------ |
| `pending`      | Generated but not trusted yet.                   |
| `approved`     | User reviewed and accepted it.                   |
| `rejected`     | User rejected it.                                |
| `active`       | Injected into supported agent configs.           |
| `stale`        | No longer useful or not triggered recently.      |
| `needs_review` | Conflicting, duplicated, or low-confidence rule. |

### Learning Acceptance Criteria

- Users can review rules before injection.
- Users can give positive or negative feedback on rule quality.
- The tool can summarize which rules are working and which are not.
- Rules can be edited without manually changing JSONL files.
- Rejected rules are not regenerated repeatedly without new evidence.

---

## 3. Owner Dashboard and Control Panel Needs Focus

### Management UI Problem

The project is deployed as a Hugging Face Space where the interface acts as an owner-only dashboard
and control panel. That dashboard is not part of the normal user installation path: end users use the
CLI/MCP tool locally, do not need a dashboard, and cannot obtain a private control panel by hosting
the package on their own machine.

The owner dashboard still needs to clearly show project state, rule quality, feedback patterns, sync
health, scheduler status, and operational risks so the maintainer can manage the tool safely.

### Management UI Proposed Solution

Improve the existing Hugging Face Space control panel as a private owner/admin interface focused on
trust, observability, and maintenance.

Suggested owner-only sections:

| Section           | Purpose                                                               |
| ----------------- | --------------------------------------------------------------------- |
| Overview          | Show aggregate rule, sync, scheduler, and system health.              |
| Rules             | Review, approve, reject, edit, merge, or deactivate shared templates. |
| Feedback patterns | Summarize opt-in, anonymized feedback signals and rule gaps.          |
| Releases          | Track package versions, CI status, and deployment readiness.          |
| Activity log      | Show recent admin actions, syncs, approvals, rejects, and failures.   |
| Safety            | Show rollback, dry-run, export, and emergency disable controls.       |

### UX requirements

- Owner-only access; no public user control panel is exposed.
- Clear separation between owner/admin controls and normal CLI/MCP user behavior.
- Clear dry-run mode before admin-triggered writes or remote updates.
- No hidden background behavior.
- Human-readable explanations for every generated or promoted rule/template.
- Copyable CLI commands for user-support and maintenance actions.

### Management UI Acceptance Criteria

- The owner can answer “what changed in the system?” in under 30 seconds.
- The owner can approve or reject generated shared templates without editing files manually.
- The owner can inspect sync, scheduler, release, and feedback-pattern health.
- The dashboard does not imply that end users receive or need their own control panel.
- Normal users can still use the CLI/MCP tool without dashboard access.

---

## Recommended Priority

1. Add rule review and lifecycle states.
2. Add dry-run and rollback improvements.
3. Improve the private owner-only Hugging Face Space dashboard.
4. Add opt-in product metrics after privacy documentation is complete.
5. Use collected feedback and anonymous aggregate metrics to prioritize future features.
