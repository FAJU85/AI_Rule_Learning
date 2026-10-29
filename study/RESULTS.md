# Results — DeepSeek instruction-adherence study (ai-rule-learning-mcp 0.2.7)

Computed **after** registration (osf.io/hy5a6) from the released raw data in `study/data/`,
using `study/analyze_prereg.py`. The frozen harness's own `analyze` under-implemented §4 (it
printed only _each-condition-vs-A_); `analyze_prereg.py` implements the pre-registered §4 tests
(H1–H3 McNemar + Holm-over-3, the three ±10-pt equivalence TOSTs) and is logged as a deviation
in `PROTOCOL.md` §9. All numbers below are reproducible with `python study/analyze_prereg.py`.

**Model actually served:** `deepseek-flash` on all 900 calls (the API returned `deepseek-flash`
although `deepseek-chat` was requested). Read every result as a result about **deepseek-flash**.

## Per-condition adherence (rep 0, 150 tasks each)

| Cond                           | Pass    | Rate  | Wilson 95%     | Invalid |
| ------------------------------ | ------- | ----- | -------------- | ------- |
| A — no rules                   | 68/145  | 0.469 | [0.390, 0.550] | 5       |
| C — length-matched placebo     | 59/134  | 0.440 | [0.359, 0.525] | 16      |
| B0 — tool defaults only        | 100/149 | 0.671 | [0.592, 0.741] | 1       |
| E — learned, natural feedback  | 142/150 | 0.947 | [0.898, 0.973] | 0       |
| B — learned, with `rule_hint`  | 143/150 | 0.953 | [0.907, 0.977] | 0       |
| D — plain-text 10 instructions | 144/150 | 0.960 | [0.915, 0.982] | 0       |

Invalids are all `syntax_error` (A=5, B0=1, C=16); none empty/no-code. Conclusions are unchanged
under the invalid-as-fail sensitivity analysis.

## Confirmatory family (§4; exact two-sided McNemar on tasks valid in both; Holm over the 3)

| Hypothesis    | Rates (paired) | fix / break | McNemar p | Holm p  | Verdict       |
| ------------- | -------------- | ----------- | --------- | ------- | ------------- |
| **H1** E > A  | 0.945 vs 0.469 | 71 / 2      | 5.7e-19   | 1.7e-18 | **supported** |
| **H2** E > C  | 0.940 vs 0.440 | 69 / 2      | 2.2e-18   | 4.3e-18 | **supported** |
| **H3** E > B0 | 0.946 vs 0.671 | 41 / 0      | 9.1e-13   | 9.1e-13 | **supported** |

All three hold under Holm. **H3 is the load-bearing one** — it isolates the learning from the
shipped defaults (41 tasks fixed, 0 broken): learning from natural feedback adds ~28 points over
defaults alone.

## Equivalence (§4; paired difference, 90% bootstrap CI, margin ±10 pts)

| Pair   | diff (y−x) | 90% CI         | Verdict        |
| ------ | ---------- | -------------- | -------------- |
| E vs D | −1.33      | [−4.67, +2.00] | **equivalent** |
| E vs B | −0.67      | [−3.33, +2.00] | **equivalent** |
| B vs D | −0.67      | [−3.33, +2.00] | **equivalent** |

The learned tool (E and B) matches hand-written plain-text memory (D) within the pre-set margin.
Per §4 we do **not** claim the tool is "better than" D — the confirmatory contrasts are E/B/D vs
A/C/B0, not vs each other. The honest claim is **parity with plain-text memory, reached
automatically**.

## Robustness — excluding the two confounded families

F07 (pathlib) and F09 (ValueError) checkers are confounded by over-application (see below), so the
primary was recomputed on the other 8 families:

| Cond | Rate (8 families) |
| ---- | ----------------- |
| A    | 0.417             |
| C    | 0.387             |
| B0   | 0.655             |
| E    | 0.933             |
| B    | 0.942             |
| D    | 0.950             |

- E > A (no F07/F09): fix=61, break=2, p=4.4e-16
- **E > B0 (no F07/F09): fix=33, break=0, p=2.3e-10**
- E > C (no F07/F09): fix=59, break=2, p=1.6e-15

The effect — including H3 — survives removing the confounded families, so it is **not** an artefact
of over-application.

## Over-application (secondary; valid responses, tasks where the rule is NOT the target)

| Cond  | pathlib imported (non-F07) | ValueError raised (non-F09) | mean non-blank lines |
| ----- | -------------------------- | --------------------------- | -------------------- |
| A     | 0/130                      | 23/130                      | 25.3                 |
| B0    | 0/134                      | 57/134                      | 23.1                 |
| C     | 0/119                      | 35/121                      | 27.8                 |
| **B** | **96/135 (71%)**           | **135/135**                 | 13.3                 |
| D     | 9/135                      | 135/135                     | 9.7                  |
| E     | 42/135 (31%)               | 135/135                     | 10.5                 |

Two distinct phenomena:

1. **Indiscriminate ValueError** (135/135 on non-validation tasks) appears in **every** rule-
   injecting condition — B, D **and** E, including plain text. This is a property of always-on
   instruction injection, **not** specific to the tool.
2. **Pathlib over-application is tool-specific and worst for B** (96/135) — the `rule_hint` path —
   versus plain text D (9/135). E (natural feedback) is intermediate (42/135).

Mean function length collapses from ~25 lines (A) to ~10–13 (B/D/E). So the adherence gain carries
a real code-quality cost, mostly intrinsic to the inject-into-every-prompt paradigm, with B's
pathlib spraying attributable to the tool's structured-rule formulation.

## Learn-phase note (from `study/data/learn_log*.json`)

`record_feedback` bound all 10 family feedbacks into ~4 generic catalog slots
(`acknowledge-and-correct-immediately`, `honor-user-preferences`, `remember-stated-context`,
`complete-all-parts-of-request`), several flagged `slot_occupied_with_different_content` with
hash-suffixed duplicates. The injected rule _text_ still carried 9–10/10 of the specific
instructions (per the learn step), so the generic naming is cosmetic for this study, but it is
worth reporting as tool behaviour.

## Bottom line

On deepseek-flash, the tool's learned rules raise instruction adherence from **47% → 95%**; the
**learning genuinely beats the shipped defaults (H3)**, robust to the over-application confound;
and the tool performs **on par with hand-written plain-text memory**. The headline caveat is
over-application, most of which is intrinsic to always-on injection rather than unique to the tool.
Scope: one model family (deepseek-flash), synthetic single-function tasks, single-sentence mostly
syntactic rules, author-run. No claims about other models, languages, multi-turn use, or
persistence.
