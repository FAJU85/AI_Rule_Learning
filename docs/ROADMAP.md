# Roadmap

Status: active · Last updated: 2026-10-23

This roadmap records the agreed direction for `ai-rule-learning`. It is a
decision record, not a backlog: it says what the project is, what it will and
will not build, and in what order.

## North star

A **portable, auditable, local-first trust layer** for AI guardrail rules across
tools. The value is not a new learning algorithm — it is making a user's own
rules portable across Claude Code, Cursor, Windsurf, Copilot and Codex, with
consent, PII scrubbing, a review gate, and an audit trail that no single vendor
has an incentive to build (it crosses competitor lines).

## Operating principles

1. **Borrow every engine, build only the glue.** Embeddings, retrieval,
   clustering, and fine-tuning are commodity. Spend originality on portability,
   consent, and audit — not on reimplementing ML.
2. **Lightest thing that works.** No new heavy dependency unless a shipped
   feature earns it. Hundreds of short rules do not need a vector database.
3. **Optimise the session-to-session loop.** It is fully in our control.
   Within-session adaptation depends on client re-fetch behaviour we do not own
   (agents read their config files once at session start), so it is best-effort
   only, never the design target.
4. **Everything consent-gated, PII-scrubbed, reversible, and explainable.**

## Why not the obvious alternatives

- **Vector database:** reinventing a solved wheel for a corpus of a few hundred
  one-line rules. In-memory cosine is enough.
- **Fine-tuning as the main path:** the flagship targets (Claude, GPT, Copilot,
  Cursor) are closed-weights and cannot be fine-tuned; fine-tuning also breaks
  model-agnosticism, instant updates, and citeability. It is an optional tier,
  not the direction.
- **Custom ML (clustering, similarity) from scratch:** use `scikit-learn` /
  off-the-shelf when scale demands it; do not hand-roll research code.
- **Within-session hot-reload:** not ours to fix — clients do not re-read
  `CLAUDE.md` mid-session.

## Phases

### Phase 1 — Relevance selection (+ keep existing dedup)

The real bottleneck. `get_guardrail_rules` caps the user's own rules at 10 by
**priority only**, with no relevance — so as the corpus grows, newly learned or
lower-priority-but-relevant rules are starved and never injected.

- **Build:** a small, dependency-free similarity module (TF-IDF + cosine over
  short rule text — no vector DB). Wire it into `get_guardrail_rules` so that,
  when the caller supplies task context, local rules are ranked by relevance
  (critical rules always kept; priority as the tiebreak) instead of a flat
  priority cap. With no context, behaviour is unchanged.
- **Not changed:** duplicate detection already uses Jaccard token-set
  similarity (`store.suggest_duplicate_rules`); it is left as-is rather than
  churned.
- **Done when:** on a large synthetic rule set, relevance selection surfaces the
  task-relevant rules that the priority cap drops.

### Phase 2 — Harden the glue (the moat)

- Audit every injection target the way Cursor/Windsurf were fixed (Codex,
  global vs project, de-duplicate the path fan-out).
- Add `AGENTS.md` as a first-class target — it is becoming the cross-tool
  standard; ride it rather than fight it (also hedges the thin, time-bound moat).
- Surface provenance in injected output ("this rule is here because you said X")
  using the existing `why` tool.

### Phase 3 — Community "detect new patterns"

Built on Phase 1's similarity. Cluster contributed corrections (k ≥ 5 for
anonymity) into emergent templates. Borrow clustering (`scikit-learn`); build the
aggregation and governance. Only sensible once Phase 1 exists.

### Phase 4 — Optional fine-tuning tier (Unsloth)

Export the rules corpus as an SFT/DPO dataset; Unsloth trains a local
open-weights model. Separate opt-in tier, not core. Only after Phases 1–3 prove
the corpus is worth training on.

## Explicitly out of scope

Vector database · custom ML algorithms · within-session hot-reload · scipy /
cuml / hyperlearn integration · fine-tuning as the main path.

## Open items (tracked elsewhere, closed independently)

- Re-run the behaviour/verification harness to confirm M02 + R05 cleared.
- Cut the next release when ready (CHANGELOG `Unreleased` already staged).
- Rotate any previously exposed credentials.
