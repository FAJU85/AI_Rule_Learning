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

## 3. Analysis and Management UI Needs Replacement

### Management UI Problem

The current analysis and management experience is not good enough for real users. Users need a clear
interface for understanding rules, memory, skills, sync status, scheduler status, and risks.

A poor management UI makes the tool feel unsafe because users cannot easily see what changed or why.

### Management UI Proposed Solution

Create a first-party local management dashboard focused on trust and control.

Suggested sections:

| Section           | Purpose                                                              |
| ----------------- | -------------------------------------------------------------------- |
| Overview          | Show active rules, pending rules, sync status, and scheduler status. |
| Rules             | Review, approve, reject, edit, merge, or deactivate rules.           |
| Memory            | View, add, edit, or delete remembered facts and preferences.         |
| Skills            | View, create, update, delete, and test saved workflows.              |
| Injection targets | Show exactly which config files will be modified.                    |
| Activity log      | Show recent writes, syncs, approvals, rejects, and scheduler runs.   |
| Safety            | Show rollback, clear, dry-run, and export controls.                  |

### UX requirements

- Local-first by default.
- Clear dry-run mode before file writes.
- One-click rollback for injected sections.
- No hidden background behavior.
- Human-readable explanations for every generated rule.
- Copyable CLI commands for every UI action.

### Management UI Acceptance Criteria

- A user can answer “what did this tool change?” in under 30 seconds.
- A user can approve or reject a generated rule without editing files manually.
- A user can remove all injected sections from the UI.
- A user can see scheduler status and disable it.
- The UI does not depend on an external dataset-management interface.

---

## Recommended Priority

1. Add rule review and lifecycle states.
2. Add dry-run and rollback improvements.
3. Add a local management dashboard.
4. Add opt-in product metrics after privacy documentation is complete.
5. Use collected feedback and anonymous aggregate metrics to prioritize future features.
