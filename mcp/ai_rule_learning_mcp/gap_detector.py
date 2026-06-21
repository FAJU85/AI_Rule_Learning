"""Local gap detection and template-based rule generation.

Works entirely offline — no LLM, no HuggingFace. Scans conversation turns
for recurring friction patterns and maps them to actionable guardrail rules.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime
from typing import Any

# ── Signal phrase lists ────────────────────────────────────────────────────

_CORRECTION = [
    "actually,", "no,", "that's wrong", "you're wrong", "incorrect",
    "not right", "that's not", "wrong approach", "fix this", "this is wrong",
    "no that's", "not what i", "missed the point", "reread", "re-read",
    "you misunderstood", "you missed", "not correct",
]
_FRUSTRATION = [
    "i already", "i told you", "as i said", "i mentioned", "you already",
    "you said", "still not", "again,", "still the same", "same problem",
    "you're not listening", "not getting it", "how many times",
    "i keep saying", "for the third", "for the second",
]
_INCOMPLETE = [
    "you didn't", "you forgot", "you missed", "you left out",
    "what about", "and also", "you also need", "don't forget",
    "you skipped", "incomplete",
]
_STOP_WORDS = {"the", "a", "an", "is", "are", "was", "be", "to", "of",
               "and", "or", "in", "on", "at", "for", "with", "that", "this"}

# ── Rule templates keyed by gap type ──────────────────────────────────────

_TEMPLATES: dict[str, dict[str, Any]] = {
    "explicit_correction": {
        "name": "acknowledge-and-correct-immediately",
        "instruction": (
            "When the user says you are wrong or corrects you, immediately "
            "acknowledge the specific error, explain what was incorrect, and "
            "provide the right answer. Do not repeat the same mistake."
        ),
        "priority": 4,
        "triggers": ["wrong", "incorrect", "actually", "that's not"],
    },
    "repeated_context": {
        "name": "remember-stated-context",
        "instruction": (
            "When the user reminds you of something they already said "
            "(e.g. 'I already told you', 'as I said'), explicitly acknowledge "
            "the earlier context before answering. Never make them repeat themselves."
        ),
        "priority": 3,
        "triggers": ["i already", "i told you", "as i said", "still not"],
    },
    "repeated_question": {
        "name": "resolve-before-moving-on",
        "instruction": (
            "When you notice a user asking a similar question to one asked "
            "earlier in the session, acknowledge the pattern and ask whether "
            "your previous answer was unhelpful before giving a new one."
        ),
        "priority": 3,
        "triggers": ["again", "still", "same question", "you didn't answer"],
    },
    "incomplete_response": {
        "name": "complete-all-parts-of-request",
        "instruction": (
            "Always address every part of a multi-part request before "
            "responding. If the user says you forgot something or asks "
            "'what about X', you left it out."
        ),
        "priority": 3,
        "triggers": ["you forgot", "you missed", "what about", "you skipped"],
    },
    "code_no_error_handling": {
        "name": "always-include-error-handling",
        "instruction": (
            "Every code example must include appropriate error handling "
            "(try/except, error boundaries, null checks). Never provide "
            "code without considering failure modes."
        ),
        "priority": 3,
        "triggers": ["error", "exception", "handle", "try"],
    },
}


# ── Core detection ─────────────────────────────────────────────────────────

def detect_gaps(turns: list[dict]) -> dict[str, list[dict]]:
    """Return a dict of gap_type → list of gap instances found in turns."""
    gaps: dict[str, list[dict]] = {}
    seen_questions: list[tuple[set[str], int]] = []

    for i, turn in enumerate(turns):
        user = turn.get("user_input", "").lower()
        agent = turn.get("agent_response", "").lower()

        # Explicit corrections
        if any(p in user for p in _CORRECTION):
            signal = next(p for p in _CORRECTION if p in user)
            gaps.setdefault("explicit_correction", []).append(
                {"turn": i + 1, "signal": signal, "snippet": user[:160]}
            )

        # User repeating context they already gave
        if any(p in user for p in _FRUSTRATION):
            signal = next(p for p in _FRUSTRATION if p in user)
            gaps.setdefault("repeated_context", []).append(
                {"turn": i + 1, "signal": signal, "snippet": user[:160]}
            )

        # Incomplete responses
        if any(p in user for p in _INCOMPLETE):
            signal = next(p for p in _INCOMPLETE if p in user)
            gaps.setdefault("incomplete_response", []).append(
                {"turn": i + 1, "signal": signal, "snippet": user[:160]}
            )

        # Repeated question detection (word-overlap)
        words = set(user.split()) - _STOP_WORDS
        if len(words) >= 4:
            for prev_words, prev_i in seen_questions[-8:]:
                if prev_i >= i - 1:
                    continue
                union = prev_words | words
                overlap = len(prev_words & words) / max(len(union), 1)
                if overlap > 0.55:
                    gaps.setdefault("repeated_question", []).append(
                        {"turn": i + 1, "similar_to": prev_i + 1,
                         "overlap": round(overlap, 2)}
                    )
                    break
            seen_questions.append((words, i))

        # Code without error handling
        has_code = "```" in agent or "def " in agent or "function " in agent
        has_error_handling = any(
            w in agent for w in
            ["try:", "except", "catch (", "catch{", ".catch(", "raise ",
             "throws ", "error handling", "exception"]
        )
        if has_code and not has_error_handling:
            gaps.setdefault("code_no_error_handling", []).append(
                {"turn": i + 1}
            )

    return gaps


def generate_rules(gaps: dict[str, list[dict]]) -> list[dict]:
    """Convert gap findings into rule dicts, one per gap type."""
    rules = []
    now = datetime.utcnow().isoformat()

    for gap_type, instances in gaps.items():
        if not instances:
            continue
        tpl = _TEMPLATES.get(gap_type)
        if not tpl:
            continue
        rule_id = "rul_" + hashlib.sha256(
            f"{gap_type}:{tpl['name']}".encode()
        ).hexdigest()[:12]
        rules.append(
            {
                "rule_id": rule_id,
                "name": tpl["name"],
                "instruction": tpl["instruction"],
                "action": {"instruction": tpl["instruction"]},
                "trigger": {"keywords": tpl["triggers"]},
                "priority": tpl["priority"],
                "priority_label": {5: "CRITICAL", 4: "HIGH", 3: "MEDIUM",
                                   2: "LOW", 1: "LOW"}.get(tpl["priority"], "MEDIUM"),
                "gap_type": gap_type,
                "instance_count": len(instances),
                "is_active": True,
                "status": "active",
                "source": "local_detector",
                "created_at": now,
                "effectiveness_score": 0.0,
                "times_triggered": 0,
            }
        )

    # Sort by priority descending then by instance count
    return sorted(rules, key=lambda r: (r["priority"], r["instance_count"]), reverse=True)


def analyze_conversations(conversations: list[dict]) -> list[dict]:
    """Run detection on all conversations, aggregate, deduplicate, return rules."""
    aggregate: dict[str, list[dict]] = {}

    for conv in conversations:
        turns = conv.get("turns", [])
        if not turns:
            continue
        gaps = detect_gaps(turns)
        for gap_type, instances in gaps.items():
            aggregate.setdefault(gap_type, []).extend(instances)

    return generate_rules(aggregate)
