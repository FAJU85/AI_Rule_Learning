# Decision Record — AI Rule Learning's learning architecture, and its comparison to Beacon

- **Date:** 2026-10-21
- **Status:** Proposed (awaiting owner ratification)
- **Author:** Engineering review session (3-day investigation)
- **Scope:** What `ai-rule-learning` (ARL) is, measured against its own goals and against
  `asymptote-labs/agent-beacon`; and a recommendation on direction.

> This record is deliberately unflattering. Its purpose is to state, with evidence, where
> the project does and does not meet its stated vision, so the owner can decide direction
> from facts rather than hope.

---

## 1. The vision this is measured against

The owner defined the fundamental problem the tool exists to solve:

- The user corrects the LLM in **every** session.
- There is **no per-session memory**; rules must be **manually re-injected** every session.
- Manual injection **consumes tokens**.
- **New patterns** keep appearing.

And five axes for what "better" means: (1) less complex to build, (2) less complex for the
user, (3) better results for the user, (4) solving a fundamental problem, (5) improving UX.

**Vision, restated as five pillars:** (P1) learns your corrections automatically; (P2)
remembers across sessions; (P3) ends manual re-injection; (P4) low/zero token cost; (P5)
genuinely better and simpler.

---

## 2. What was done in the investigation

- Fixed CI/CD red→green (PR #271) and migrated storage HF→Cloudflare R2 (PR #272);
  scrubbed hard-coded secrets. _(Scaffolding, not product value.)_
- Ran a real, independent QA harness (owner-authored): installs the published PyPI wheel,
  verifies its SHA against PyPI, drives the real MCP server over stdio, and benchmarks a
  real LLM with a **length-matched placebo control**.
- Reproduced the learning pipeline **locally and deterministically** (no LLM, no network)
  to isolate the mechanism.

---

## 3. Evidence — what ARL actually does

### 3.1 The autonomous learning loop does not work

Phase C behavioural benchmark (OpenRouter `gpt-4o-mini`, one task family, small N):

| Condition                              | Input tokens | Rule compliance |
| -------------------------------------- | ------------ | --------------- |
| cold (no rules)                        | 0            | 3/12            |
| **manual** (4-line hand-written note)  | **102**      | **12/12**       |
| placebo (length-matched filler)        | 435          | 3/12            |
| **mcp** (tool's rule text)             | **409**      | **12/12**       |
| **auto** (tool's _auto-learned_ rules) | **494**      | **3/12**        |

Three facts:

1. Good rule text works, and not as a length artifact (`mcp` 12/12 vs `placebo` 3/12 at
   equal length).
2. ARL is **dominated by a 4-line manual note** (`manual` 12/12 at 102 tok = `mcp` 12/12 at
   409 tok). When the user supplies the rule, the tool adds no quality and costs ~4× the
   tokens — the opposite of P4.
3. **`auto` = `cold`** (3/12). The autonomous path performs like no rules at all, while
   costing the most tokens (494).

### 3.2 Root cause, proven in code

`gap_detector.generate_rules()` (`mcp/ai_rule_learning_mcp/gap_detector.py:566`):

```python
clean_instruction = scrub_pii(str(tpl.get("instruction", "")))  # text is 100% from the template
```

The user's actual correction (`instances`) only sets `instance_count`/`confidence`. **The
user's words never enter the rule.** The "learner" is a classifier into ~20 fixed buckets
that emits boilerplate.

Deterministic local reproduction: a session containing four specific corrections (type
hints + `-> dict`; `?` params not f-strings; return `{'ok':True,'data':row}`; no prose)
produced four generic rules — "acknowledge-and-correct-immediately",
"always-include-error-handling" (never requested), "complete-all-parts-of-request",
"remember-stated-context" — **none** of which mention the four actual constraints. This is
why `auto = cold`, independent of the benchmark.

### 3.3 Related defects

- **Bundled seed rules occupy user slots; repeated corrections proliferate.** The package
  ships 12 always-active rules (`data/bundled_rules.jsonl`) keyed to the same slots users
  record into, so there is **no true empty state**. A correction to an occupied slot with
  _different_ content is **not dropped**: `record_feedback` appends it as a new suffixed rule
  (`<slot>-<hash>`, `server.py:1138`) and returns `SlotOccupied`, and a user-supplied
  `rule_hint` is preserved. The real cost is proliferation — repeated corrections to one
  category pile up as near-duplicate slots instead of updating a canonical rule; benchmark
  F11 failed because a second correction raised the on-disk count 3→4, not because content
  was lost. (Corrects an earlier draft of this record that said "dropped".)
- **Delivery injects all active rules every session** (token-heavy; P4 regression).
- **Doc drift:** server exposes 21 tools; docs/tests referenced 12.

### 3.4 What genuinely works

Persist → auto-inject across sessions (P2, P3 for rules already captured) works and
survives restart. Automatic PII scrubbing works (F19: 0/4 secrets leaked). Injection
preserves the user's own `CLAUDE.md` content (F09/F21). This is ~40% of the vision, and it
is the 40% that functions.

---

## 4. Beacon (`asymptote-labs/agent-beacon`) — how it solves the same problem

Investigated by reading the owner's fork `FAJU85/agent-beacon_faju85` directly.

- **Fork status:** clean, unmodified mirror, _behind_ upstream (`99c7090` vs `77e3f98`).
  Every commit author is asymptote-labs + their bots; **no owner commits**. "Building on
  beacon" = tracking upstream; there is nothing in the fork to preserve.
- **Extraction (the part ARL fails):** _not an algorithm — a prompt._ An external evaluator
  returns **probabilities only** ("it does not say what the lesson is. You write the lesson,
  from the trace, and the user approves it"). The **LLM drafts the lesson from the real
  trace events**, must **cite event numbers**, and is constrained by a rubric
  (`lesson-quality.md`: five kinds; an explicit "Not a memory" list). A human approves each
  one ("Silence is not approval"); dedup via `supersede`.
- **Storage:** clean 3-stage SQLite lifecycle — `evaluations → candidates → memories`
  (`cli/beacon/internal/learning/store.go`), pure-Go `modernc.org/sqlite`.
- **Delivery:** **recall on demand** (local `beacon memory list -q` / MCP
  `get_memory_context`), "at most once per task" — token-frugal. Optionally **promote** a
  memory to a skill the harness auto-loads only when its description matches.
- **Capture:** per-harness hooks (`session_start/end`, `prompt_submit`, `compaction`, …)
  → local log; cross-harness via OpenTelemetry. Requires a **local endpoint daemon**.
- **What leaves the machine:** only the optional evaluator call, as a **bounded projection**
  (`maxProjectionEvents=80`, `maxProjectionText=1200`) to `api.typesafe.ai` / `api.subq.ai`.
  Evaluator is **optional** (a "without an evaluator" path exists) and **pluggable** (point
  at your own endpoint). Recall and candidate-creation are fully local.

---

## 5. Head-to-head

| Dimension                  | Beacon                                                     | ARL                                  |
| -------------------------- | ---------------------------------------------------------- | ------------------------------------ |
| Learns the _specific_ rule | ✅ LLM drafts from trace, cited                            | ❌ template, discards input          |
| Human review before trust  | ✅ mandatory                                               | ❌ auto `is_active`                  |
| Storage                    | ✅ 3-stage SQLite + supersede                              | ⚠️ JSONL; collisions spawn near-dups |
| Delivery / token cost      | ✅ recall on demand                                        | ❌ inject all rules every session    |
| Capture                    | ✅ cross-harness OTel+hooks (daemon)                       | ⚠️ reads Claude JSONL on demand      |
| Auto PII scrub (outbound)  | ⚠️ bounded projection + human gate                         | ✅ automatic scrubber                |
| External dependency        | ⚠️ default evaluator = paid 3rd-party (optional/pluggable) | ✅ none (R2 now)                     |
| Maturity                   | ✅ high                                                    | ⚠️ 0.2.4, small                      |
| Zero-infra minimalism      | ❌ runs a daemon                                           | ✅ (its one real edge)               |

**ARL's only surviving advantages:** zero-daemon minimalism (P2/P5 for one harness) and
automatic outbound PII scrubbing. Everything that makes it a _learning_ tool, beacon does
better — and does it with a markdown prompt + SQLite, i.e. _less_ code, not more
(ARL invested a Python classifier precisely where beacon invested a prompt).

---

## 6. Options

- **A. Adopt beacon** as the memory layer; retire ARL's learner. Accept the local capture
  daemon and the optional evaluator.
- **B. Lean ARL + beacon's method.** Keep ARL deliberately minimal (zero-daemon, one
  harness, auto PII scrub), but replace `generate_rules`' template classifier with beacon's
  approach (LLM drafts from the session + rubric + human approve).
- **C. Keep building ARL as-is.** Not recommended; the evidence shows the core claim unmet.

---

## 7. Recommendation

**Do not rebuild beacon's brain inside a weaker body.** Rebuilding LLM-drafted,
rubric-bound, human-approved, evidence-cited extraction inside ARL is re-deriving beacon
with less maturity.

- If running a local daemon is acceptable → **Option A.** Highest result for least new work.
- If zero-infrastructure is a hard requirement → **Option B**, and own the narrow niche
  beacon over-serves (solo dev, one harness, no daemon). Borrow beacon's _method_ wholesale;
  keep ARL's auto PII scrubber.
- **Regardless of A/B/C, the real defect is autonomous extraction, not storage.** The manual
  `record_feedback` path preserves the user's `rule_hint`; the autonomous `sync` path
  (`generate_rules`) is what discards content and makes `auto == cold`. Secondary cleanup:
  slot collisions should update a canonical rule instead of spawning near-duplicate suffixed
  slots.

---

## 8. Honest notes on process

- Early in the investigation the reviewer oscillated (proposed a SQLite layer, then
  retracted it). The correction was the owner's discipline: _objectives → test against
  objectives → QA → then solutions_. The lesson retained: with this project the default move
  is **subtract and verify**, not add.
- An earlier claim that beacon was an "enforcement / zero-token / rubric-gate" tool was
  **wrong** and is corrected here: beacon is an observability-first memory layer.

---

## 9. Caveats on the evidence

- Phase C ran on **one model** (`gpt-4o-mini`), **small N**, **one task family**; the
  red-team came back empty (evaluator-key quota), so "rules resist pressure" is **unproven**.
- The `auto = cold` conclusion rests on the **deterministic local proof** (Section 3.2), not
  the benchmark, and is therefore high-confidence.
- Beacon internals were read from the fork; its skills are upstream-authored. The 1,100 Go
  files of OTel/SDK plumbing were not exhaustively read (not decision-relevant).

---

## 10. Open questions for the owner

1. Is running a **local capture daemon** acceptable? (Decides A vs B.)
2. Is dependence on an **external evaluator** acceptable, or must learning be fully local?
3. What is ARL's **reason to exist** if beacon is adopted — the zero-infra niche, or nothing?
