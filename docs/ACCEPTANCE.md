# Acceptance Specification — Tiered Enforcement ("LLM as compiler")

- **Status:** PROPOSED — pre-registration draft. To be frozen (git tag + hashes) before the
  Tier-1 build begins. Nothing in this file may be relaxed after freeze without a logged
  deviation (§10).
- **Draft date:** 2026-10-30
- **Owner:** repository owner (tool author)
- **Conflict of interest:** the author built the tool under test. Every gate below is written
  so the tool **cannot grade itself** (§2), and the corpus, oracle and thresholds are fixed
  before the modified tool exists.

This spec answers one question: _after we rebuild extraction and enforcement, how do we know
the tool fulfils its objectives, in a sound manner?_ It defines falsifiable gates, not a
narrative. If the gates are green the claims hold; if any is red the claim is withdrawn.

---

## 0. Why this exists

Two internal records already establish, with evidence, that the shipped tool does **not** yet
meet its vision:

- `docs/DECISION-2026-10-21-learning-architecture-vs-beacon.md`: the autonomous path scored
  like no rules at all (`auto` = `cold`), while costing the most tokens.
- The 2026-10-30 enforcement audit: of 10 representative rule families, **2** reach an
  implemented deterministic checker; the rest fall to the text-injection channel or a dead
  `pending` state. The pre-registered effectiveness study found learned rules (E) statistically
  **equivalent** to pasting the instruction as plain text (D) — i.e. the "learning" adds
  nothing over plain injection, because nothing is compiled.

The rebuild's thesis (owner's words): _use the LLM as a compiler, not a runtime — infer once,
export the logic, run it without further inference; if a task is solved the same way twice, the
second time must be zero-token._ This spec is the bar that thesis must clear.

---

## 1. Objectives under test

The owner's three stated objectives, each made measurable here:

1. **O1 — Extraction.** Generate correct, faithful rules from conversation flows and
   corrections (§5, gate G1).
2. **O2 — Application.** Apply those rules so they causally change behaviour, in the current
   conversation and in new conversations, without collateral damage (§5, gate G2).
3. **O3 — Cost.** The injection/enforcement path adds no per-use token cost for compiled rules
   (§5, gate G3).

Cross-cutting: **O4 — Soundness.** The evidence for O1–O3 is itself trustworthy (§5, gate G4).

---

## 2. The non-negotiable principle

The tool is never allowed to grade itself. Every verdict ("rule created", "applied",
"enforced", "compliant") is produced by an **oracle outside the tool**, run on the actual
artefact the model emitted:

- The oracle is the deterministic AST/token checker family already self-tested in
  `study/arl_study.py` (27/27 checker cases at freeze) and κ-validated against a human
  (`study/kappa/`). It is extended, under the same discipline, to each new tier.
- The tool's own success strings (for example `✅ Created … will apply to every future
session`) are **not** evidence and are never counted.
- Any gate computed by code the tool ships must be reproduced by an independent script in
  `acceptance/` that reads only released raw data (mirroring `study/analyze_prereg.py`).

---

## 3. The rule corpus

Gates are measured over fixed, released corpora so results are reproducible and cannot be
cherry-picked after the fact.

- **Catalog corpus:** the 130 rules in `data/catalog_v1.json`. Each rule is assigned, before
  the build, to exactly one tier (§4) with a written justification. The owner's target split
  is ~85 / 30 / 15 (Tier 1 / 2 / 3); the _actual_ split is an output of the build, reported as
  found, not forced to that ratio.
- **Extraction corpus (`acceptance/corpus/extraction.jsonl`):** held-out
  `(conversation_snippet → gold_rule[s])` pairs authored by someone other than the tool's
  rule-generation code, covering: clean corrections, messy/real corrections, multi-part
  corrections (must yield ≥2 rules), context-specific rules (for example "lazy-import because
  of a circular dependency"), and a **negative set** — pure acknowledgements ("thanks", "got
  it") that must yield **zero** rules.
- **Behavioural corpus:** the 150 held-out tasks × 10 families already frozen in the
  effectiveness study, reused unchanged so O2 is comparable to the registered baseline.

---

## 4. Tiers and the routing invariant

Three enforcement tiers, in order of preference (compile as much as possible down to Tier 3):

1. **Tier 1 — compile-time enforcement.** Rule is expressed as a deterministic check (AST pass,
   `ruff`/`mypy`/`bandit` selector, or a synthesised `semgrep`/AST rule) run in a
   post-generation hook, pre-commit and CI. Zero system-prompt tokens; the check re-runs
   forever at no main-model inference cost. Violations are reported to the model to correct
   (correction tokens are counted separately, §5 G3).
2. **Tier 2 — runtime classifier.** Rule not statically checkable but detectable in output by a
   cheap classifier (regex first; a learned classifier only once outcome data justifies it),
   run in a `PostToolUse` hook. Zero main-model tokens.
3. **Tier 3 — behavioural prompt rule.** Genuinely behavioural rule injected into the system
   prompt, within a declared token budget.

**Routing invariant (hard requirement):** every rule lands in exactly one tier that _actually
does something_. The count of rules in a "classified structural but not implemented" or
otherwise dead state must be **0**. A rule the compiler is unsure about degrades to Tier 3
(injected), never to silence. This invariant is gate G4.1 and is checked on 100% of the catalog
corpus.

---

## 5. Acceptance gates

Each gate lists what is measured, how, and the committed pass threshold (§6). All thresholds
are fixed before freeze; a gate that misses its threshold fails, and the corresponding claim is
not made.

### G1 — Extraction (O1)

Measured on the extraction corpus (§3), tool output compared to gold by an independent grader.

- **G1.1 Precision** — of rules generated, fraction that are correct and actionable.
- **G1.2 Recall** — of gold rules present, fraction the tool produces.
- **G1.3 Faithfulness** — rule content matches intent with no dropped clause; multi-part
  feedback yields the expected number of distinct rules. Scored by a human; inter-annotator
  Cohen's κ reported.
- **G1.4 Negative-set purity** — fraction of pure acknowledgements that (correctly) yield **no**
  rule. The current tool fails this (it stored "ugh you did it again" as a rule); it is a hard
  gate.
- **G1.5 No garbage persistence** — no rule whose body is a non-directive complaint is written
  to any agent config.

### G2 — Application (O2)

Measured on the behavioural corpus (§3) with the registered design (conditions A / C / B0 / E /
D, paired, exact McNemar + Holm), extended with the contrasts below.

- **G2.1 Causal gain** — adherence under learned rules exceeds the length-matched **placebo**
  (not just the no-rules baseline), Holm-significant across the confirmatory family.
- **G2.2 Net of over-application** — the score is _target-task adherence gain_ **minus**
  _spurious application on off-target tasks_ (pathlib on non-file tasks, ValueError on
  non-validation tasks, code-length collapse). A rule set may not "win" by spraying. Both
  components have thresholds.
- **G2.3 Compile-vs-prompt ablation** — for the same Tier-1 rules, compiled enforcement is
  compared to prompt-injection-only. Compiling must **beat** injection (break the E≡D
  equivalence) on enforceable families; if it does not, Tier 1 is not earning its complexity.
- **G2.4 Persistence** — a **fresh** session loads the compiled/injected rules and adherence
  holds (new-conversation claim), measured separately from within-session correction.
- **G2.5 Model generality** — G2.1–G2.4 hold on **≥2 model families**, including one frontier
  model. Any claim is otherwise scoped in writing to the single model tested.

### G3 — Cost (O3)

Measured by direct token accounting instrumented in the harness, not estimated.

- **G3.1 Hard zero at use time** — rules in Tier 1 and Tier 2 add **0** system-prompt tokens
  and require **0** main-model inference to _evaluate_ the rule. Verified by diffing the prompt
  and counting eval calls; must be exactly zero.
- **G3.2 Bounded Tier-3 budget** — total Tier-3 prompt tokens ≤ the declared budget, and flat
  as the catalog grows (measured at N = 10, 50, 100 active rules).
- **G3.3 Amortised compile** — any inference used to _compile_ a rule is paid once per rule and
  does not recur per use; reported as cost-per-rule.
- **G3.4 Correction cost disclosed** — tokens the model spends regenerating after a Tier-1
  violation are measured and reported as a separate line. "Zero-token" refers to evaluation,
  never to correction; this gate exists to keep that distinction honest.

### G4 — Soundness (O4)

- **G4.1 Routing invariant** — 0 rules in a dead/pending state across the catalog corpus (§4).
- **G4.2 Synthesised-check validation** — every auto-generated check passes the rule's own
  positive/negative examples before activation; precision/recall of each generated check
  reported. An unvalidated check is never activated.
- **G4.3 Adversarial handling** — for the adversarial/messy/conflicting slice of the corpus,
  every rule is shown to be enforced, injected, or explicitly declined — never silently
  dropped.
- **G4.4 External oracle** — all G1–G2 verdicts come from the independent oracle (§2), checker
  self-test reproduced, human κ ≥ threshold.
- **G4.5 Pre-registration + openness** — this spec is frozen (tag + hashes) before the build;
  raw data for every gate is released; an independent reviewer of the corpus and checkers is
  named, or its absence is disclosed.

---

## 6. Committed thresholds

Frozen at pre-registration. These are the numbers the build is held to; they are set to be
_failable_.

| Gate | Metric                       | Pass threshold                                                            |
| ---- | ---------------------------- | ------------------------------------------------------------------------- |
| G1.1 | Extraction precision         | ≥ 0.90                                                                    |
| G1.2 | Extraction recall            | ≥ 0.85                                                                    |
| G1.3 | Faithfulness (human), κ      | κ ≥ 0.80                                                                  |
| G1.4 | Negative-set purity          | = 1.00 (no rule from any acknowledgement)                                 |
| G2.1 | Causal gain vs placebo       | Holm-significant, p < 0.05, positive paired diff                          |
| G2.2 | Over-application cap         | spurious application ≤ 10% on off-target tasks                            |
| G2.3 | Compile beats prompt         | compiled adherence − injected adherence ≥ +10 pts on enforceable families |
| G2.4 | Fresh-session adherence      | within ±5 pts of same-session                                             |
| G2.5 | Model generality             | gates hold on ≥ 2 model families                                          |
| G3.1 | Tier-1/2 use-time tokens     | = 0 prompt tokens AND 0 eval inferences                                   |
| G3.2 | Tier-3 budget                | ≤ 500 prompt tokens, flat across N = 10/50/100                            |
| G4.1 | Routing invariant            | = 0 rules in dead/pending state                                           |
| G4.2 | Synthesised-check validation | 100% pass own examples before activation                                  |
| G4.4 | Checker self-test            | reproduced (no regression vs 27/27 baseline)                              |

---

## 7. Harness layout

Reuses the study scaffolding; new code lives under `acceptance/` and is held to the repo gate
(`ruff format --check`, `ruff check`, `mypy`, `pytest`, coverage ≥ 80%).

| Path                                 | Role                                                         |
| ------------------------------------ | ------------------------------------------------------------ |
| `acceptance/corpus/extraction.jsonl` | Held-out extraction pairs incl. negative set (§3)            |
| `acceptance/corpus/tiering.json`     | Per-catalog-rule tier assignment + justification (§4)        |
| `acceptance/run_extraction.py`       | Drives the real tool, scores G1 against gold via the oracle  |
| `acceptance/run_application.py`      | Reuses `study/` design; adds G2.2/G2.3/G2.4/G2.5 contrasts   |
| `acceptance/token_audit.py`          | Instruments G3 token accounting (prompt + eval + correction) |
| `acceptance/check_routing.py`        | Asserts G4.1 routing invariant over the catalog              |
| `acceptance/validate_checks.py`      | Asserts G4.2 for every synthesised check                     |
| `acceptance/scorecard.py`            | Aggregates all gates into one pass/fail scorecard            |

---

## 8. Falsifiability statement

This spec is only meaningful if the tool can fail it. It can:

- G1.4 fails today (acknowledgements become rules).
- G4.1 fails today (8/10 families are dead or soft).
- G2.3 fails today (E ≡ D: compiling adds nothing, because nothing compiles).

A green scorecard therefore represents real movement, not a restatement of the current state.
If, after the build, any gate cannot be made green, the honest outcome is to narrow the claim
(for example, "Tier-1 enforcement for N families on model X") rather than to weaken the gate.

---

## 9. Build sequencing

The first increment is scoped so its acceptance is a strict subset of the gates above.

1. **Phase 1 — Tier 1 for real.** Implement the detectors already registered as `pending`
   (`no_print`, `no_else`, `type_hints`, `snake_case`, `short_funcs`, `pathlib`, `single_block`),
   mostly thin wrappers over `ruff`/`mypy` already in the dependency set. Add validate-before-
   activate (G4.2) and the routing-invariant guarantee (G4.1). Target: deterministic coverage
   from 2/10 → 8/10 families. Acceptance subset: G4.1, G4.2, G4.4, G3.1, and G2.3 on the newly
   implemented families.
2. **Phase 2 — Extraction rebuild.** Decomposition of multi-part feedback, the negative-set
   gate, and faithful distillation. Acceptance subset: G1.*.
3. **Phase 3 — Tier 2 + generality.** Regex classifiers, then learned ones only where outcome
   data supports it; second model family. Acceptance subset: G2.5, remaining G2/G3.

Each phase is merged only when its acceptance subset is green and reproduced by `acceptance/`.

---

## 10. Deviation log

Filled after freeze. Any change to §4–§6 after the pre-registration tag is recorded here with
date and rationale; a new tool major version is a new acceptance run, not an edit to this one.

- _(none yet — pre-freeze draft)_
