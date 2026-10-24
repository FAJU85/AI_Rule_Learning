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

## Instrumentation / schema (2026-10-24)

1. **Edit distance is captured without relaxing the anti-injection control.** The
   dogfood metric needs the distance between the proposed rule and the one the
   reviewer approves, but `_edit_rule` prohibits instruction mutation (catalog
   rules are static, to block prompt injection and drift). These are reconciled by
   keeping the review log _pure instrumentation_: `approve_rule` accepts an optional
   `approved_instruction` that is logged (candidate vs. approved edit distance) but
   **never written back to the rule**. Whether a reviewer's corrected text is ever
   _applied_ to a stored rule is a separate product decision, deliberately left out
   of the measurement path. The log is the ground-truth factory, not an edit channel.

2. **Tier-A is a structural gate, not a quality score.** The Pydantic validator
   (`rule_schema.py`) checks shape only — well-formed, directive, non-trivial,
   traceable — with zero tolerance at the approval/injection boundary: a malformed
   candidate is refused activation and stays pending. It deliberately does **not**
   score specificity (the earlier specificity classifier was discarded for
   miscalibration) and we do not report "% passing schema" as a quality number —
   that would invite Goodharting the validator instead of improving rules. The
   directive-head set is calibrated to the 130-rule verified catalog (which passes
   100%, enforced by a test) plus the deterministic `distill_directive` outputs.

3. **The skill-unit shape is a schema-in-waiting.** `SkillUnit` is defined with a
   nullable `verification_step` but is not populated. Promotion from Tier-A rule to
   skill-unit stays data-triggered: the field fills in only when real rules start
   carrying a checkable verification step, rather than being invented now.

## Bugs fixed (2026-10-24)

- **Traceability:** `source_session_id` was `hash(gap_type:slot)` — identical across
  rules, matching no real session. Now an anonymised hash of the real originating
  session, so the review log is analysable.
- **`distill_directive`:** fixed ungrammatical "forgot to X" output, added a
  noise-rejection gate (pure acknowledgements like "thanks" no longer become rules —
  the rule-bloat root cause), and preference→imperative conversion.
- **Output unit:** distinct corrections now become distinct, individually-traceable
  rules instead of being merged by `gap_type`.
