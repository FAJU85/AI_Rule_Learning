# Protocol: Effectiveness of AI Rule Learning MCP on instruction adherence (DeepSeek)

**Status:** FROZEN FOR REGISTRATION — §1 hashes filled; checker selftest reproduced (27/27) at freeze. Not yet registered. Registration = commit + git tag (or OSF upload) of this file together with `arl_study.py` BEFORE running `MODE="main"`. The timestamp of that tag/upload is the registration date; do not edit dates by hand.
**Draft date:** 2026-10-29
**Conflict of interest:** the author developed the tool under test. Task suite, checkers and this protocol were fixed before main-study data exist. An independent reviewer of the task suite and checkers is recommended and, if obtained, named here: ________ (none obtained as of this freeze)

## 1. Frozen artefacts

| Item                   | Value                                                                                                                                                                           |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Tool                   | ai-rule-learning-mcp **0.2.7** (PyPI)                                                                                                                                           |
| Wheel sha256           | 70d0d70bbc964b3cd8765c7c72ee8952239eed8dfd7e39398a2f4d48a56e2b8e (verified against PyPI + independent recompute)                                                                |
| MCP SDK                | mcp 1.30.0 (via `mcp<2`)                                                                                                                                                        |
| Study script           | arl_study.py, sha256 of the registered version: **ef282a95f5d65eef31e4118437bc19be0d1a6cce32f3fda9271dcabc4fd42948** (matches the pre-edit candidate `ef282a95…2948`; verified) |
| Runnable wrapper       | COLAB_ONE_CELL.py (one-cell Colab runner that emits `arl_study.py` from its `SRC` literal), sha256: d83607c96413b949fbfbe1406ec1947a1f0e10d8ab661b6ec9b868610b1baaea            |
| Model                  | DeepSeek API, requested `deepseek-chat`, temperature 0, max_tokens 2500; the model name the API returns is logged per call (pilot returned `deepseek-flash`)                    |
| Seed for task sampling | 20261028                                                                                                                                                                        |

Any change to the above after registration = deviation, logged in §9; a new tool version = new study.

## 2. Design

150 held-out tasks (10 instruction families × 15 tasks; each task = one Python function request). Every task is run under 6 conditions (within-task, paired), one call each (rep 0):

- **A** no rules · **B0** tool defaults only (no learning) · **B** tool after feedback WITH `rule_hint` · **E** tool after natural-language feedback only (no hint) · **C** length-matched irrelevant text · **D** the 10 instructions as plain text.
  Learning phase uses a clean HOME per condition; no API key is passed to the tool process. The injected text is the tool's own `get_guardrail_rules` output.
  Reliability subset: 30 tasks (seeded) get a second call per condition (rep 1) to estimate run-to-run variability at temperature 0. Rep 1 is not used in confirmatory tests.

## 3. Outcome

Primary: binary instruction adherence per task from a deterministic AST/token checker (selftested on 27 cases). Invalid responses (empty, API error, no parseable code) are excluded from the paired test and reported per condition; sensitivity analysis counts them as fail.
Secondary: over-application measures on tasks where the rule is not the target (pathlib imported on non-F07 tasks, ValueError raised on non-F09 tasks, functions per response, non-blank lines).
Validation: a human reviews a random 10% of responses (≥15, seeded) and reports checker agreement (Cohen's κ). Checker bugs found are reported; not silently fixed after data collection.

## 4. Hypotheses and tests (confirmatory family, Holm over the 3)

- **H1** E > A in adherence (exact two-sided McNemar on tasks valid in both).
- **H2** E > C.
- **H3** E > B0 (the learning, not the shipped defaults, causes the gain).
  Exploratory/secondary (unadjusted CIs, labelled exploratory): B vs A, D vs A, B vs B0, per-family rates (n=15 each), over-application contrasts.
  **Equivalence (pre-set margin ±10 percentage points, 90% CI of the paired difference):** E vs D, E vs B, B vs D. Interpretation: if the CI lies inside ±10 pts, the tool matches hand-written plain-text memory; otherwise we state inconclusive. We do NOT claim the tool is "better than" D unless the confirmatory CI excludes 0.
  Effect size reported as paired difference with Wilson/bootstrap CI. A cluster-robust logit (clusters = task spec) is secondary; models with separation are not interpreted.

## 5. Sample size

Pilot (two runs, n=20 tasks, deleted from the main data): A≈40%, E≈90%. Simulation (exact McNemar, task-level random effect sd=1): ≥0.93 power for a 25-point gain from 65% with 60 tasks; 150 tasks leave margin for invalid responses and for the equivalence analysis (paired SE ≈ 0.03 if ~10% of pairs are discordant — an assumption checked on the data, not a result).

## 6. Stopping and analysis rules

One data collection, one analysis, no interim looks. All 900 calls run unless the API fails; failures are retried (resumable), never replaced by edited tasks. All raw responses are released.

## 7. Limitations declared in advance

One model family (DeepSeek), one vendor alias that may change; synthetic single-function tasks; rules are single-sentence and mostly syntactic; the feedback sentences (condition E) were written by the author; the tool's defaults exist in B0 and may overlap with some instructions (prose-before-code); deterministic settings do not remove API non-determinism; developer-author bias. Results do not support claims about other models, languages, multi-turn use or long-term persistence.

## 8. Security note (separate, not part of this study)

Functional/security findings observed so far with 0.2.4/0.2.7 (data files created with mode 0644; invalid `feedback_type` accepted; one injection-style rule was not served) come from the verification suite, not this experiment, and are reported separately.

## 9. Deviation log

(empty — fill during and after the run)

## 10. Paper outline (no results)

Introduction · Related work (agent memory, instruction persistence, MCP tooling) · The tool and what "learning" means in 0.2.7 · Method (this protocol) · Results (confirmatory, then exploratory) · Over-application · Threats to validity · Reproducibility package · COI.
