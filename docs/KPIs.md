# KPIs

How we measure whether the tool is doing its job. Every KPI is computed from
**local state only** — the rule store, the agent configs detected on the machine,
and the opt-in metrics log. Nothing here requires network access or sends data.

See it at any time:

```bash
ai-rule-learning kpi          # human-readable snapshot
ai-rule-learning kpi --json   # machine-readable
```

The command reports the current value; the **targets** below are the goals to
steer by, not thresholds the tool enforces.

## Rules — is the corpus growing and governed?

| KPI                    | Meaning                                      | Target                                 |
| ---------------------- | -------------------------------------------- | -------------------------------------- |
| `rules.total`          | All rules in the store                       | grows with use                         |
| `rules.active`         | Rules currently trusted and injected         | most of total                          |
| `rules.pending_review` | Autonomously learned rules awaiting approval | reviewed promptly; not left to pile up |

## Quality — is the corpus clean and effective?

| KPI                         | Meaning                                                  | Target                 |
| --------------------------- | -------------------------------------------------------- | ---------------------- |
| `quality.duplicate_pairs`   | Likely-duplicate rule pairs still present                | **0** (merge them)     |
| `quality.stale`             | Active rules with no recent activity (≥90 days)          | low; retire or refresh |
| `quality.needs_review`      | Rules that kept firing but scored low on effectiveness   | **0** (fix or retire)  |
| `quality.avg_effectiveness` | Mean effectiveness score over rules with trigger history | **≥ 0.5**, trending up |

## Reach — are rules actually reaching the user's tools?

| KPI                        | Meaning                                                | Target                             |
| -------------------------- | ------------------------------------------------------ | ---------------------------------- |
| `reach.agents_detected`    | AI tools whose configs were found on this machine      | informational                      |
| `reach.agents_injected`    | Of those, how many currently carry the guardrail block | —                                  |
| `reach.injection_coverage` | injected ÷ detected                                    | **100%** — the portability promise |

## Usage — is the tool being exercised? (opt-in)

Only populated when the owner has enabled metrics (`ai-rule-learning metrics on`);
otherwise these read `n/a`.

| KPI                  | Meaning                                     | Target        |
| -------------------- | ------------------------------------------- | ------------- |
| `usage.events`       | Count of recorded CLI/tool events           | informational |
| `usage.success_rate` | Share of recorded operations that succeeded | **≥ 0.95**    |

## Not covered here

- **Behavioural lift** (does an injected rule change model output?) is measured by
  the external benchmark harness, not this snapshot — it needs a model and a GPU.
  See `docs/benchmarks.md`. That remains the honest, separate measure of whether
  the rules work, as opposed to whether they are delivered.
