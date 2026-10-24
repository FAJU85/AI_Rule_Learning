"""Review-decision log — the ground-truth factory for rule quality.

Every human review decision on a *pending learned* rule is appended here with
full context (candidate text, originating utterance, trigger context, the
decision, and the edit distance to the approved text). After a dogfood period
this log is read directly to answer the only question that matters before we
build more: are the autonomously-learned rules good enough that a human keeps
them nearly verbatim (a *learner*), or are they rewritten every time (a
*suggestion engine*)?

Why edit distance. A low edit distance between the proposed rule and the one
the reviewer actually approves means the extractor is producing usable rules; a
high one means it is producing prompts a human has to rewrite. That single
number — read off a real review log, not asserted — is the gate.

Design note (edit distance vs. the anti-injection control). This module is
*pure instrumentation*. It records what the reviewer decided and, when they
supply a corrected instruction, the edit distance to it. It does **not** mutate
the rule store and does **not** relax ``_edit_rule``'s prohibition on
instruction mutation — that control protects catalog rules from prompt
injection and instruction drift, and this module leaves it fully intact.
Whether a reviewer's corrected text is ever *applied* to a stored rule is a
separate product decision, deliberately kept out of the measurement path. The
log is the ground-truth factory; it is not an edit channel.

No number produced here is a "quality score". The log reports raw counts and
the distribution of edit distances, with N always attached, so the reader can
judge the sample rather than trust a headline percentage (Goodhart).
"""

from __future__ import annotations

from datetime import UTC
from datetime import datetime
from statistics import median
from typing import Any

from . import store

REVIEW_LOG_FILE = "review_log.jsonl"

# A review decision is one of these. "edit" is an approve where the reviewer
# supplied a corrected instruction that differs from the candidate.
DECISIONS = ("approve", "edit", "reject")


def levenshtein(a: str, b: str) -> int:
    """Return the Levenshtein edit distance between two strings (pure Python).

    No dependency: a plain two-row dynamic-programming implementation, which is
    enough for rule-length strings and keeps the module offline and dependency-free.
    """
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            insert = current[j - 1] + 1
            delete = previous[j] + 1
            substitute = previous[j - 1] + (ca != cb)
            current.append(min(insert, delete, substitute))
        previous = current
    return previous[-1]


def normalized_edit_distance(a: str, b: str) -> float:
    """Edit distance scaled to ``[0.0, 1.0]`` by the longer string.

    0.0 means identical; 1.0 means nothing in common. Normalisation makes the
    number comparable across rules of different lengths.
    """
    longest = max(len(a), len(b))
    if longest == 0:
        return 0.0
    return round(levenshtein(a, b) / longest, 4)


def _source_utterance(rule: dict[str, Any]) -> str:
    """Best-effort originating utterance for a rule, from its evidence snippets."""
    evidence = rule.get("evidence")
    if isinstance(evidence, list) and evidence:
        return " | ".join(str(e) for e in evidence[:3])
    return ""


def _trigger_context(rule: dict[str, Any]) -> dict[str, Any]:
    """Trigger context for a rule, preferring explicit trigger_if then keywords."""
    trigger_if = rule.get("trigger_if")
    if isinstance(trigger_if, dict) and trigger_if:
        return trigger_if
    trigger = rule.get("trigger")
    if isinstance(trigger, dict) and trigger.get("keywords"):
        return {"keywords": trigger["keywords"]}
    return {}


def log_review_decision(
    rule: dict[str, Any],
    decision: str,
    approved_instruction: str = "",
    note: str = "",
) -> dict[str, Any]:
    """Append one review decision to the log and return the stored record.

    ``rule`` is the full rule record as stored (so provenance travels with the
    decision). ``decision`` is one of :data:`DECISIONS`. ``approved_instruction``
    is the text the reviewer settled on; when it differs from the candidate the
    decision is recorded as an edit and the edit distance is computed. It is
    logged only — never written back to the rule.
    """
    normalized = (decision or "").strip().lower()
    if normalized not in DECISIONS:
        raise ValueError(f"unsupported review decision: {decision!r} (expected one of {DECISIONS})")

    candidate = str(rule.get("instruction", "") or "")
    approved = (approved_instruction or "").strip()

    # An "approve" with a differing corrected instruction is really an edit.
    if normalized == "approve" and approved and approved != candidate:
        normalized = "edit"

    if normalized == "reject":
        edit_distance: int | None = None
        norm_distance: float | None = None
        approved_text = ""
    elif normalized == "edit":
        edit_distance = levenshtein(candidate, approved)
        norm_distance = normalized_edit_distance(candidate, approved)
        approved_text = approved
    else:  # clean approve
        edit_distance = 0
        norm_distance = 0.0
        approved_text = candidate

    record = {
        "logged_at": datetime.now(UTC).replace(tzinfo=None).isoformat(),
        "rule_id": rule.get("rule_id", ""),
        "decision": normalized,
        "candidate_instruction": candidate,
        "approved_instruction": approved_text,
        "edit_distance": edit_distance,
        "normalized_edit_distance": norm_distance,
        "source_utterance": _source_utterance(rule),
        "trigger_context": _trigger_context(rule),
        "source_session_id": rule.get("source_session_id", ""),
        "gap_type": rule.get("gap_type", ""),
        "extraction_version": rule.get("extraction_version", ""),
        "note": note,
    }

    # PII scrubbing and atomic append are handled by the store layer, exactly as
    # for rules — the review log is subject to the same local-first guarantees.
    existing = store._local_load(REVIEW_LOG_FILE)
    existing.append(record)
    store._local_save(REVIEW_LOG_FILE, existing)
    return record


def read_review_log() -> list[dict[str, Any]]:
    """Return all logged review decisions, oldest first."""
    return store._local_load(REVIEW_LOG_FILE)


def review_stats() -> dict[str, Any]:
    """Summarise the review log for the dogfood read-out.

    Returns raw counts and the edit-distance distribution with N attached. These
    are measurements, not a quality score: ``approval_rate`` is "kept nearly or
    exactly as proposed / total", and the edit-distance figures describe how far
    the reviewer had to move the text. A small ``total`` means the numbers are
    not yet trustworthy — the caller is expected to say so.
    """
    log = read_review_log()
    total = len(log)
    counts = {d: 0 for d in DECISIONS}
    for rec in log:
        d = rec.get("decision")
        if d in counts:
            counts[d] += 1

    kept = counts["approve"] + counts["edit"]  # anything not rejected was kept
    # Edit distances across every kept rule (clean approves contribute 0).
    kept_norm = [
        rec["normalized_edit_distance"]
        for rec in log
        if rec.get("decision") in ("approve", "edit") and isinstance(rec.get("normalized_edit_distance"), (int, float))
    ]
    # Distances on the edited subset only (where the reviewer actually changed text).
    edited_norm = [
        rec["normalized_edit_distance"]
        for rec in log
        if rec.get("decision") == "edit" and isinstance(rec.get("normalized_edit_distance"), (int, float))
    ]

    def _mean(xs: list[float]) -> float | None:
        return round(sum(xs) / len(xs), 4) if xs else None

    def _median(xs: list[float]) -> float | None:
        return round(float(median(xs)), 4) if xs else None

    return {
        "total_decisions": total,
        "counts": counts,
        # Fraction of reviewed rules that were kept (approved as-is or edited),
        # i.e. not rejected. Reported as a ratio with N, not a grade.
        "approval_rate": round(kept / total, 4) if total else None,
        "edit_rate": round(counts["edit"] / total, 4) if total else None,
        "reject_rate": round(counts["reject"] / total, 4) if total else None,
        # How far the approved text moved from the proposal (lower = better learner).
        "mean_normalized_edit_distance_kept": _mean(kept_norm),
        "median_normalized_edit_distance_kept": _median(kept_norm),
        "mean_normalized_edit_distance_edited": _mean(edited_norm),
        "n_kept": kept,
        "n_edited": len(edited_norm),
        # Honest caveat the reader must not drop.
        "sufficient_sample": total >= 20,
    }


def format_review_stats(stats: dict[str, Any] | None = None) -> str:
    """Render :func:`review_stats` as a compact, honest text summary."""
    if stats is None:
        stats = review_stats()
    total = stats["total_decisions"]
    if total == 0:
        return (
            "📋 Review log is empty — no review decisions recorded yet.\n"
            "   Approve/reject pending rules to build the ground-truth sample."
        )
    counts = stats["counts"]
    lines = [
        f"📋 Review decisions: {total}"
        + ("" if stats["sufficient_sample"] else "  ⚠️ small sample (<20) — not yet trustworthy"),
        f"   approve: {counts['approve']}  |  edit: {counts['edit']}  |  reject: {counts['reject']}",
    ]
    ar = stats["approval_rate"]
    if ar is not None:
        lines.append(f"   approval rate (kept, not rejected): {ar:.0%}  (n={total})")
    med = stats["median_normalized_edit_distance_kept"]
    mean = stats["mean_normalized_edit_distance_kept"]
    if med is not None:
        lines.append(
            f"   edit distance on kept rules — median {med:.2f}, mean {mean:.2f} "
            f"(0.0 = kept verbatim, 1.0 = fully rewritten)"
        )
    mean_edit = stats["mean_normalized_edit_distance_edited"]
    if mean_edit is not None:
        lines.append(f"   edit distance on the {stats['n_edited']} edited rules — mean {mean_edit:.2f}")
    lines.append("   Reading: low edit distance ⇒ the extractor is a learner; high ⇒ a suggestion engine.")
    return "\n".join(lines)
