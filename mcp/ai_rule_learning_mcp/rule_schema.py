"""Tier-A rule schema — deterministic, post-hoc structural hygiene.

This is the *structural* gate, not a quality score. It answers one yes/no
question about a rule's *shape*: is this a well-formed, directive, traceable,
non-trivial instruction? It says nothing about whether the rule is *good* — that
is the human reviewer's job (see :mod:`review_log`) and, eventually, a
behavioural gate once a real corpus exists.

Two deliberate boundaries, both load-bearing:

1. **No specificity scoring.** An earlier specificity classifier was discarded
   for miscalibration (word-boundary false negatives — see ``docs/FINDINGS.md``).
   Tier-A therefore checks only *triviality* (a pure platitude or acknowledgement
   is rejected), never a graded "how specific" number. We do not report
   "% passing schema" as a quality metric — that would invite Goodharting the
   validator instead of improving rules.

2. **Zero tolerance, applied at injection time.** Every rule that is about to be
   activated/injected must pass Tier-A. A structural failure is a hard stop, not
   a warning — malformed rules never reach an agent config.

The "imperative" check is calibrated against the verified catalog
(``catalog_v1.json``): its directive heads are drawn from the 130 curated rules
plus the deterministic ``distill_directive`` outputs, so the verified corpus
passes 100% by construction. A test enforces that invariant.

The skill-unit schema (:class:`SkillUnit`) is defined here but **not yet
populated** — a schema-in-waiting. ``verification_step`` is optional/nullable on
purpose: when real data shows rules carry a checkable verification step, the
promotion from Tier-A rule to skill-unit becomes data-triggered, not a guess.
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import field_validator
from pydantic import model_validator

# Directive sentence heads, lowercased. Calibrated to the verified catalog's
# first words plus the imperative forms emitted by distill_directive
# ("Always …", "Use …", "Prefer …", "Always include …"). A test asserts that
# every catalog instruction's head is in this set, so the set and the corpus
# cannot silently drift apart.
_DIRECTIVE_HEADS: frozenset[str] = frozenset(
    {
        # from catalog_v1.json (130 curated rules)
        "when",
        "do",
        "never",
        "provide",
        "avoid",
        "maintain",
        "always",
        "validate",
        "verify",
        "check",
        "emit",
        "preserve",
        "structure",
        "adhere",
        "treat",
        "write",
        "sanitize",
        "use",
        "format",
        "implement",
        "include",
        "only",
        "recommend",
        "confine",
        "map",
        "omit",
        "state",
        "limit",
        "assume",
        "restrict",
        "refrain",
        "if",
        "call",
        "refuse",
        "re-anchor",
        "retrieve",
        "prioritize",
        "answer",
        "remain",
        "reuse",
        "break",
        "enumerate",
        "double-check",
        "distinguish",
        "identify",
        "systematically",
        "trace",
        "add",
        "ensure",
        "match",
        "properly",
        "remove",
        "follow",
        "require",
        "deliver",
        "update",
        "respond",
        "acknowledge",
        "enforce",
        "frame",
        "decline",
        # from distill_directive outputs
        "prefer",
    }
)

# Whole-instruction platitudes / acknowledgements that carry no directive content.
# Triviality rejection, not specificity scoring.
_TRIVIAL_WHOLE: frozenset[str] = frozenset(
    {
        "thanks",
        "thank you",
        "ok",
        "okay",
        "got it",
        "sounds good",
        "noted",
        "be careful",
        "be mindful",
        "do better",
        "try harder",
        "pay attention",
        "be consistent",
        "do your best",
        "use best practices",
    }
)

_WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9'-]*")
_MIN_INSTRUCTION_LEN = 10
_MAX_INSTRUCTION_LEN = 2000
_MIN_WORDS = 2


def _first_head(instruction: str) -> str:
    """Lowercased first directive token, keeping internal hyphens (e.g. 're-anchor')."""
    stripped = instruction.strip()
    if not stripped:
        return ""
    first = stripped.split()[0]
    # keep internal hyphens, drop surrounding punctuation
    cleaned = re.sub(r"^[^A-Za-z]+|[^A-Za-z-]+$", "", first)
    return cleaned.lower()


def is_directive(instruction: str) -> bool:
    """True when the instruction opens with a recognised directive head."""
    return _first_head(instruction) in _DIRECTIVE_HEADS


def is_trivial(instruction: str) -> bool:
    """True when the instruction is a pure platitude/acknowledgement or too thin."""
    norm = re.sub(r"[.!?\s]+$", "", instruction.strip().lower())
    if norm in _TRIVIAL_WHOLE:
        return True
    return len(_WORD_RE.findall(instruction)) < _MIN_WORDS


class RuleHygiene(BaseModel):
    """Tier-A structural-hygiene schema for a single rule.

    Construction validates the rule; a structural violation raises
    ``pydantic.ValidationError``. This checks *shape*, never *merit*.
    """

    model_config = ConfigDict(extra="ignore")

    instruction: str
    gap_type: str = Field(min_length=1)
    rule_id: str = ""
    # Traceability can come from either a learning provenance id or a citation.
    source_session_id: str = ""
    source: str = ""

    @field_validator("instruction")
    @classmethod
    def _well_formed(cls, v: str) -> str:
        text = v.strip()
        if not text:
            raise ValueError("instruction is empty")
        if len(text) < _MIN_INSTRUCTION_LEN:
            raise ValueError(f"instruction too short (<{_MIN_INSTRUCTION_LEN} chars)")
        if len(text) > _MAX_INSTRUCTION_LEN:
            raise ValueError(f"instruction too long (>{_MAX_INSTRUCTION_LEN} chars)")
        if "\x00" in text:
            raise ValueError("instruction contains control characters")
        return text

    @model_validator(mode="after")
    def _hygiene(self) -> RuleHygiene:
        if is_trivial(self.instruction):
            raise ValueError("instruction is trivial (platitude/acknowledgement or too few words)")
        if not is_directive(self.instruction):
            raise ValueError(
                f"instruction is not directive — head {_first_head(self.instruction)!r} "
                "is not a recognised directive verb"
            )
        if not (self.source_session_id.strip() or self.source.strip()):
            raise ValueError("rule is not traceable (needs source_session_id or source citation)")
        return self


def check_rule(rule: dict[str, Any]) -> list[str]:
    """Return a list of Tier-A violations for *rule* (empty list = passes).

    Non-raising counterpart to :class:`RuleHygiene`, for reporting over a corpus.
    """
    try:
        RuleHygiene.model_validate(_coerce(rule))
    except Exception as exc:  # pydantic.ValidationError or ValueError
        return _explain(exc)
    return []


def validate_rule(rule: dict[str, Any]) -> RuleHygiene:
    """Validate one rule, raising ``ValidationError`` on any structural violation."""
    return RuleHygiene.model_validate(_coerce(rule))


def validate_injected_rules(rules: list[dict[str, Any]]) -> tuple[bool, dict[str, list[str]]]:
    """Zero-tolerance gate for rules about to be injected/activated.

    Returns ``(ok, failures)`` where ``ok`` is True only when *every* rule passes
    and ``failures`` maps each failing rule's id (or index) to its violations.
    Callers must refuse to inject when ``ok`` is False.
    """
    failures: dict[str, list[str]] = {}
    for idx, rule in enumerate(rules):
        problems = check_rule(rule)
        if problems:
            key = str(rule.get("rule_id") or f"#{idx}")
            failures[key] = problems
    return (not failures, failures)


def _coerce(rule: dict[str, Any]) -> dict[str, Any]:
    """Pull the hygiene-relevant fields out of a rule record (dict or nested action)."""
    instruction = rule.get("instruction")
    if not instruction:
        action = rule.get("action")
        if isinstance(action, dict):
            instruction = action.get("instruction", "")
    return {
        "instruction": instruction or "",
        "gap_type": rule.get("gap_type", "") or "",
        "rule_id": rule.get("rule_id", "") or "",
        "source_session_id": rule.get("source_session_id", "") or "",
        "source": rule.get("source", "") or "",
    }


def _explain(exc: Exception) -> list[str]:
    """Flatten a pydantic/validation error into a list of human-readable messages."""
    errors = getattr(exc, "errors", None)
    if callable(errors):
        out = []
        for e in exc.errors():  # type: ignore[attr-defined]
            msg = e.get("msg", "")
            out.append(msg.replace("Value error, ", "").replace("Assertion failed, ", ""))
        return out or [str(exc)]
    return [str(exc)]


# ── Conflict detection (set-level, coarse) ───────────────────────────────────
# "Non-conflicting" is a property of a rule *set*, not a single rule, so it lives
# outside RuleHygiene. This is a deliberately coarse detector: it flags direct
# always/never contradictions about the same object. It is a tripwire, not a
# theorem prover, and is reported separately from the per-rule hygiene gate.

_POLARITY_RE = re.compile(r"\b(never|do not|don't|avoid|refrain from)\b", re.IGNORECASE)
_STOPWORDS = frozenset(
    {
        "the",
        "a",
        "an",
        "to",
        "of",
        "and",
        "or",
        "in",
        "on",
        "for",
        "with",
        "always",
        "never",
        "do",
        "not",
        "don't",
        "avoid",
        "use",
        "prefer",
        "ensure",
    }
)


def _content_terms(instruction: str) -> set[str]:
    return {w.lower() for w in _WORD_RE.findall(instruction) if w.lower() not in _STOPWORDS and len(w) > 2}


def find_conflicts(rules: list[dict[str, Any]]) -> list[tuple[str, str, str]]:
    """Return coarse (rule_id_a, rule_id_b, reason) contradictions within a set.

    Flags pairs that share the same ``gap_type`` and substantial content overlap
    but opposite polarity (one prohibits, the other does not). Coarse by design.
    """
    conflicts: list[tuple[str, str, str]] = []
    enriched = []
    for idx, r in enumerate(rules):
        c = _coerce(r)
        instr = c["instruction"]
        if not instr:
            continue
        enriched.append(
            {
                "id": str(r.get("rule_id") or f"#{idx}"),
                "gap_type": c["gap_type"],
                "neg": bool(_POLARITY_RE.search(instr)),
                "terms": _content_terms(instr),
            }
        )
    for i in range(len(enriched)):
        for j in range(i + 1, len(enriched)):
            a, b = enriched[i], enriched[j]
            if a["gap_type"] and a["gap_type"] != b["gap_type"]:
                continue
            if a["neg"] == b["neg"]:
                continue
            overlap = a["terms"] & b["terms"]
            if len(overlap) >= 2:
                conflicts.append((a["id"], b["id"], f"opposite polarity on shared terms {sorted(overlap)[:4]}"))
    return conflicts


# ── Skill-unit schema-in-waiting ─────────────────────────────────────────────
# Defined now, populated later. A rule becomes a skill-unit when the data shows
# it carries a concrete, checkable verification step. We do NOT invent that step;
# verification_step stays None until a real rule supplies one. This is boundary
# (b) from the agreed sequence: ship Tier-A rules now, keep the skill shape ready.


class SkillUnit(BaseModel):
    """The eventual skill-unit shape. Schema-in-waiting — intentionally unpopulated.

    ``verification_step`` is optional/nullable so that promotion from a Tier-A
    rule to a skill-unit is data-triggered: when rules start arriving with a
    checkable step, this field fills in and the promotion path turns on. Until
    then it is ``None`` and no code depends on it.
    """

    model_config = ConfigDict(extra="ignore")

    rule_id: str
    instruction: str
    gap_type: str
    trigger_context: dict[str, Any] = Field(default_factory=dict)
    # Schema-in-waiting field: stays None until data justifies populating it.
    verification_step: str | None = None
    source_session_id: str = ""
    source: str = ""
