# Feedback Guide

Thank you for taking the time to review **AI Rule Learning MCP**. Specific feedback is much more
useful than a generic "nice project" comment, so this guide gives you a simple structure to follow.

You can copy the questions below into a GitHub issue, discussion, pull request comment, or direct
message to the maintainer.

---

## Quick Review Questions

### 1. Is the idea clear?

- What do you think the tool is supposed to do?
- Was the README clear enough to understand the purpose in under two minutes?
- Which part of the explanation was confusing, unclear, or too technical?

### 2. Does the tool solve a real problem?

- Have you experienced the problem this tool is trying to solve?
- Would persistent AI guardrails, memory, skills, or session feedback help your workflow?
- Is the problem urgent enough that you would install a tool to solve it?

### 3. What did you not like?

- Was anything misleading, overpromised, or hard to trust?
- Did any command, file-write behavior, or scheduler feature feel risky?
- Was anything missing from the setup or usage instructions?

### 4. What could be improved?

- What should be simpler?
- What should be documented better?
- What feature would make the tool more useful?
- What would make you trust the tool more?

### 5. Would you use it in your projects?

- Yes or no?
- Why or why not?
- If not today, what would need to change before you would try it?

---

## Suggested Review Format

```markdown
## Review: AI Rule Learning MCP

### First impression

<What did you think this project does after reading the README?>

### Is the idea clear?

<Yes/no/partly, and why.>

### Does it solve a real problem?

<Describe whether this problem exists in your workflow.>

### What did you not like?

<List confusing, risky, missing, or overcomplicated parts.>

### What could be improved?

<List concrete improvements.>

### Would you use it?

<Yes/no/maybe, and what would influence that decision.>

### Most important next step

<One thing the maintainer should do next.>
```

---

## Extra Questions for Developers

- Is the install flow clear enough?
- Are the CLI commands easy to understand?
- Are the MCP tools named clearly?
- Are the write paths and local storage behavior documented well enough?
- Would you prefer a dry-run mode before any file writes?
- Should generated rules require manual approval before injection?
- What tests, examples, or demos would make you more confident?

---

## Extra Questions for AI-Agent Users

- Which AI coding tools do you use most often?
- Would cross-agent memory or guardrails be useful to you?
- Have you ever had to repeat the same instructions to an AI assistant many times?
- Would you want this tool to run automatically, or only manually?
- What would make automatic rule injection feel safe?

---

## Maintainer Notes

When reviewing feedback, look for repeated patterns:

- unclear value proposition,
- unclear safety model,
- missing examples,
- confusing install/setup steps,
- concern about automatic config writes,
- concern about background scheduler behavior,
- requests for dry-run, approval, or rollback flows.

Prioritize improvements that reduce user surprise and make the tool easier to trust.
