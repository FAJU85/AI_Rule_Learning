# Durable findings

Short, load-bearing conclusions that must survive even while larger write-ups
(e.g. the competitive analysis) stay frozen. These are the constraints any future
contributor — or any "let's just…" proposal — has to answer to.

## Strategy / architecture

1. **Per-rule behavioural validation is structurally unreachable for single-user
   corpora.** Detecting a ~28%→38% compliance shift per rule needs on the order of
   hundreds of paired observations; a single user generates far fewer trigger-firings
   per rule. Only _aggregate_ gates (pooled across rules/users) are statistically
   reachable, and only once a real multi-week, multi-user corpus exists. Do not
   promise per-rule "proven helpful" for an individual user.

2. **Coarse `gap_type` aggregation was lossy by construction.** The extractor's unit
   was the gap category, not the user's utterance, so distinct corrections collapsed
   into one rule. Fixed (one rule per distinct distilled directive), but the lesson
   stands: the unit of extraction must be the correction, not the bucket.

3. **Offline / no-LLM is a hard product constraint, not a preference.** `gap_detector`
   states it outright ("works entirely offline — no LLM, no HuggingFace") and
   `docs/privacy.md` makes local-first the product promise. This _closes_ LLM-based
   extraction, even in the nightly cron (the constraint protects offline/privacy, not
   latency). Therefore rule _structure_ must come from the output shape or the human
   reviewer — **not** a model. The standard rebuttal "just use a local model" is
   already answered: it breaks local-first and reintroduces the heavy dependency the
   project deliberately refused.

## Measurement

1. **A rule-quality _number_ is not yet defensible.** A first-pass specificity
   classifier was discarded for miscalibration (word-boundary false negatives). A
   trustworthy metric needs a human-labelled calibration set; replay-based behavioural
   scoring is blocked at current N (see finding 1). Until then, the honest posture is
   human-in-the-loop curation, where the human is the validation layer and the review
   log is the ground-truth factory.

## Bugs fixed (2026-10-24)

- **Traceability:** `source_session_id` was `hash(gap_type:slot)` — identical across
  rules, matching no real session. Now an anonymised hash of the real originating
  session, so the review log is analysable.
- **`distill_directive`:** fixed ungrammatical "forgot to X" output, added a
  noise-rejection gate (pure acknowledgements like "thanks" no longer become rules —
  the rule-bloat root cause), and preference→imperative conversion.
- **Output unit:** distinct corrections now become distinct, individually-traceable
  rules instead of being merged by `gap_type`.
