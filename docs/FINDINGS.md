# Durable findings

Short, load-bearing conclusions that must survive even while larger write-ups
(e.g. the competitive analysis) stay frozen. These are the constraints any future
contributor — or any "let's just…" proposal — has to answer to.

## Learner validity (2026-10-28, maintenance Block 1)

1. **The effectiveness pilot's condition E was invalid: it ran on `0.2.4`, which contains
   no `distill_directive` at all.** Verified by pulling `0.2.4` from PyPI. So "E ≈ B0 ⇒ the
   tool doesn't learn" is not evidence about the learning algorithm — that version has none.
   PyPI timeline: `0.2.4` (2026-10-19) and latest `0.2.6` (2026-10-22) both predate the distill
   hardening (#291, 2026-10-24) and Tier-A (#292); neither is published.

2. **Even with distill (0.2.6 / `main`), the learner does not extract usable rules from
   realistic natural feedback.** Full `record_feedback` round-trip on `main` for corrective
   feedback ("You added comments again. I never want comments…") injects the _complaint
   sentence_ as an active rule ("You added comments and docstrings again.") — not an imperative
   directive. distill only works on feedback that is already near-imperative
   ("you forgot to X" → "Always X", "I prefer X" → "Prefer X", "we use X" → "Use X"). On this
   realistic corpus, true directive-extraction ≈ 0/10, so a re-run of E would still ≈ B0.

3. **distill bug:** truncates on dotted code tokens — "You used os.path again" → "You used os.",
   "You used .format()" → "You used." (splits on the first period, including inside identifiers).

4. **`record_feedback` creates rules `active` immediately**, bypassing both the review queue and
   the Tier-A approve-time gate (#292). The feedback path is not review-gated at all.

5. **Verdict:** the learner is largely vestigial for realistic feedback (a cosmetic reformatter
   for already-imperative phrasing). The demonstrated value remains auto-injection of _authored_
   rules (pilot B ≈ D). This supports the enforcement + authored-injection pivot (Rec 4) over
   investing further in natural-language rule learning. A paid re-run of E is low-value until
   distill is either fixed to extract directives or the claim is scoped to imperative feedback.

## Gate reconciliation (2026-10-28, maintenance Block 5)

The system has three rule-vetting gates on **different axes** — not three copies of one gate:

- **Content-safety** (injection / exec / unsafe phrases) is genuinely duplicated in three places:
  `store._is_safe_rule` (`_UNSAFE_PHRASES` + `is_prompt_injection`), the dashboard's
  `_check_rule_safety` (`_UNSAFE_PHRASES` + length floor), and the aggregator's `isValidSignal`
  (exec/url/base64 regex). The `_UNSAFE_PHRASES` list is copied across client and Space. →
  **Canonicalise one content-safety function; have the Space import it rather than re-declare.**
- **Structural hygiene** (directive / traceable / non-trivial / length) lives only in Tier-A
  (`rule_schema.py`). It is **net-new**, complementary to the safety gates, and is the right home
  for the Rec-4 "inspectable / AST" enforcement channel. Keep it; reposition it as enforcement,
  not a learning-quality score.
- **Conflict detection** exists twice: dashboard `_detect_rule_conflicts` (keyword Jaccard) and
  Tier-A `find_conflicts` (opposite-polarity + shared terms). → **Pick one method.**

**Coverage gap:** `record_feedback` writes rules `active` immediately (trusted path), so they
bypass the dashboard review queue _and_ the Tier-A approve-time gate. Only the autonomous-learn
path is review-gated. Decide whether the feedback path should also pass structural hygiene.

**review_log** (edit-distance, #292) is the only net-new piece versus the dashboard's existing
Review Queue. → Integrate edit-distance into the dashboard queue; do not ship a parallel CLI.

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
