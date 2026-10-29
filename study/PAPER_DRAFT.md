# Draft paper sections (Results · Over-application · Threats to validity)

Draft prose for the pre-registered study. Numbers are from `RESULTS.md` /
`analyze_prereg.py` on the released data (`study/data/`). Pre-registration: osf.io/hy5a6.
Model under test: **deepseek-flash** (the alias the DeepSeek API returned for a `deepseek-chat`
request). This is a draft, not a final manuscript; wording is deliberately conservative.

---

## Results

We evaluated instruction adherence on 150 held-out single-function Python tasks (10 instruction
families × 15 tasks), each issued under six within-task conditions: no rules (A), a length-matched
irrelevant-text placebo (C), the tool's shipped defaults only (B0), the tool after natural-language
feedback (E), the tool after feedback with an explicit rule hint (B), and the ten instructions
supplied as hand-written plain text (D). Adherence was scored by a deterministic AST/token checker
(self-tested on 27 cases); invalid responses (unparseable code) were excluded from the paired tests
and examined separately.

Adherence rose sharply when rules were present. The no-rule baseline (A) passed 46.9% of tasks
(68/145 valid), statistically indistinguishable from the length-matched placebo (C, 44.0%),
confirming that merely adding text to the system prompt does not improve adherence. The tool's
shipped defaults alone (B0) reached 67.1%. The two learned conditions reached 94.7% (E) and 95.3%
(B), and the hand-written plain-text condition (D) reached 96.0%.

The pre-registered confirmatory family — H1 (E > A), H2 (E > C), H3 (E > B0), tested with exact
two-sided McNemar tests on tasks valid in both conditions and Holm-corrected across the three — was
supported in full. E exceeded A (94.5% vs 46.9%; 71 tasks fixed, 2 broken; Holm p = 1.7e-18), C
(94.0% vs 44.0%; 69 fixed, 2 broken; Holm p = 4.3e-18), and B0 (94.6% vs 67.1%; 41 fixed, 0 broken;
Holm p = 9.1e-13). H3 is the decisive contrast: it isolates the effect of _learning from feedback_
from the effect of the tool's shipped defaults, and the learned condition improved on the defaults
on 41 tasks while regressing on none. Learning from natural feedback added roughly 28 percentage
points over the defaults alone.

We pre-registered equivalence tests (±10-percentage-point margin, 90% bootstrap CI of the paired
difference) between the learned conditions and hand-written plain text. All three pairs were
equivalent: E vs D (−1.3 pts, 90% CI [−4.7, +2.0]), E vs B (−0.7, [−3.3, +2.0]), and B vs D (−0.7,
[−3.3, +2.0]). The tool therefore reaches the same adherence ceiling as a human writing the rules
out by hand; we do not claim it exceeds plain-text memory. Its advantage is that it produces that
memory automatically from feedback rather than requiring the user to author and maintain it.

Because two checkers (F07, pathlib; F09, ValueError) can be satisfied by over-application (see
below), we recomputed the primary contrasts on the remaining eight families. The effect was
essentially unchanged — E vs A (p = 4.4e-16) and, critically, E vs B0 (93.3% vs 65.5%; 33 fixed, 0
broken; p = 2.3e-10) — so the headline result is not an artefact of over-application.

All invalid responses were syntax errors (A = 5, B0 = 1, C = 16; none in B/D/E); the placebo
condition produced markedly more malformed code. Conclusions are unchanged under the pre-registered
sensitivity analysis that counts invalid responses as failures.

## Over-application

The adherence gains come with a measurable cost in spurious rule application, which the
pre-registered secondary measures were designed to detect. On tasks for which a given rule was not
the target, every rule-injecting condition — B, D, and E — raised `ValueError` in 100% of
non-validation responses (135/135), against 18% (23/130) with no rules. Indiscriminate validation
is thus a property of always-on instruction injection in general, not of the tool specifically: it
occurs just as strongly when the rules are supplied as hand-written plain text.

Spurious `pathlib` use was, by contrast, condition-dependent and worst for the tool's rule-hint
path: condition B imported `pathlib` in 71% (96/135) of non-file tasks, versus 7% (9/135) for plain
text and 31% (42/135) for natural-feedback learning. Mean function length fell from 25 non-blank
lines without rules to 10–13 with them. Over-application therefore inflates the F07 and F09 pass
rates and, more importantly, represents a real degradation in code appropriateness: functions that
validate inputs they were never asked to validate and import modules they do not use. Any deployment
of always-on rule injection should weigh this cost, and the tool's structured rule-hint formulation
appears to aggravate it relative to plain text.

## Threats to validity

This study has substantial limitations, several of which we declared before collecting data.

- **Single model, and an unstable alias.** All results are for one model family, and the DeepSeek
  API served `deepseek-flash` despite a `deepseek-chat` request on all 900 calls. Nothing here
  generalises to other models, and the specific model is a moving target.
- **Synthetic, single-function, syntactic tasks.** The task suite is small isolated functions and
  the rules are single-sentence, mostly syntactic constraints. Real codebases, multi-file work,
  multi-turn interaction, and semantic rules are untested. Results say nothing about long-term
  persistence of learned rules.
- **Checker confounding.** Two of ten checkers can be satisfied by over-application; we mitigated
  this with the eight-family robustness recomputation, but the primary metric as originally defined
  is partially confounded, and the over-application finding should be read alongside the adherence
  finding, not after it.
- **Author-run, with a conflict of interest.** The tool's developer designed the task suite,
  checkers, protocol, and the condition-E feedback sentences, and executed the study. The
  pre-registration (osf.io/hy5a6), the frozen and hashed harness, the released raw data, and the
  pre-specified analysis are intended to constrain researcher degrees of freedom, but an independent
  replication on an untouched task suite and independent checkers would materially strengthen the
  claims. No independent reviewer has yet been obtained.
- **Analysis executed outside the frozen script.** The registered harness's `analyze` did not
  implement the §4 confirmatory and equivalence tests; those were computed post-registration by a
  separate analyzer on the released data (deviation §9.2). The computation is open and reproducible,
  but it was not the exact code committed at registration.
- **Incomplete pre-registered measurements.** The run-to-run reliability subset (rep 1) was not
  collected, and the human-validation inter-rater agreement (κ) on a 10% sample has not yet been
  performed (deviations §9.3, §9.5). Both are needed before the report is complete.
- **Deterministic settings do not remove API non-determinism.** Temperature 0 reduces but does not
  eliminate run-to-run variation, and with the reliability subset missing we cannot quantify it for
  this run.
