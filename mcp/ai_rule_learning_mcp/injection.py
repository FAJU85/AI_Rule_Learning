"""Two-stage prompt injection detection engine.

Stage 1 (fast, deterministic): Pattern, regex, and weighted signal analysis.
Stage 2 (targeted, semantic): Contextual semantic evaluation for borderline inputs,
    degrading gracefully if external models or weights are unavailable.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any

_log = logging.getLogger(__name__)

# Configurable score threshold for weighted signal detection (F13b)
DEFAULT_INJECTION_THRESHOLD = float(os.environ.get("ARL_INJECTION_THRESHOLD", "0.7"))

# Trigger keywords that warrant deeper inspection or Stage 2 semantic evaluation
_SUSPICIOUS_TRIGGERS: list[str] = [
    "ignore",
    "forget",
    "override",
    "disregard",
    "bypass",
    "restrictions",
    "jailbreak",
    "mode",
    "prompt",
    "keys",
    "obey",
    "unrestricted",
    "dan",
    "rules",
    "guidelines",
    "safety",
    "exfiltrate",
    "exfiltration",
    "instructions",
]

# Canonical / literal attack phrases
_INJECTION_PATTERNS: list[str] = [
    "ignore previous instructions",
    "ignore all instructions",
    "ignore instructions",
    "disregard the above",
    "disregard previous",
    "disregard earlier",
    "disregard prior",
    "disregard all",
    "disregard everything",
    "forget your instructions",
    "forget previous",
    "forget earlier",
    "forget prior",
    "forget all",
    "forget everything",
    "new system prompt",
    "pretend you are",
    "act as if you have no",
    "override your",
    "override safety",
    "override guidelines",
    "override rules",
    "override restrictions",
    "bypass your",
    "bypass safety",
    "you are now",
    "your new role is",
    "jailbreak",
    "jailbreak mode",
    "dan mode",
    "developer mode",
    "sudo mode",
    "god mode",
    "never refuse",
    "no restrictions",
    "without restrictions",
    "unrestricted",
    "unrestricted mode",
    "exfiltrate",
    "exfiltration",
]

# High-confidence attack regex patterns
_INJECTION_REGEXES: list[re.Pattern[str]] = [
    # disregard / ignore / forget / bypass / override / drop / set aside + everything / all / previous / prior / earlier / above / instructions / rules / guidelines / safety
    re.compile(
        r"\b(?:ignore|disregard|forget|bypass|override|drop|discard|set\s+aside)\b.*?\b(?:everything|all|previous|prior|earlier|above|preceding|foregoing|instructions?|rules?|guidelines?|directives?|constraints?|restrictions?|safety|system\s*prompt)\b",
        re.IGNORECASE | re.DOTALL,
    ),
    # jailbreak / developer / god / dan / sudo / unrestricted / admin mode
    re.compile(
        r"\b(?:jailbreak|developer|god|dan|sudo|unrestricted|admin|root|maintenance)\s+mode\b",
        re.IGNORECASE,
    ),
    # no restrictions / without restrictions / zero restrictions / unrestricted
    re.compile(
        r"\b(?:no|without|zero|free\s+from|remove\s+all)\s+(?:restrictions?|constraints?|guardrails?|limits?|filters?|rules?|boundaries)\b|\bunrestricted\b",
        re.IGNORECASE,
    ),
    # override / bypass / disable + safety / guidelines / rules / restrictions / constraints
    re.compile(
        r"\b(?:override|bypass|disable|turn\s+off|circumvent)\b.*?\b(?:safety|guidelines?|rules?|instructions?|restrictions?|constraints?|guardrails?|filters?|policies|policy)\b",
        re.IGNORECASE | re.DOTALL,
    ),
    # exfiltrate / exfiltration / leak / reveal / dump system prompt / keys / credentials
    re.compile(
        r"\bexfiltrat(?:e|ion|ing)\b|\b(?:leak|reveal|dump|print|expose)\b.*?\b(?:keys?|tokens?|secrets?|system\s*prompt|passwords?|credentials?|hidden\s*instructions?)\b",
        re.IGNORECASE | re.DOTALL,
    ),
    # obey me / do anything now / disregard everything
    re.compile(
        r"\b(?:obey\s+me|do\s+anything\s+now|disregard\s+everything(?:\s+above)?)\b",
        re.IGNORECASE,
    ),
    # act as if / pretend + no restrictions / different AI / jailbreak / unfiltered
    re.compile(
        r"\b(?:act\s+as(?:\s+if)?|pretend(?:\s+you\s+are)?)\b.*?\b(?:no\s+restrictions|without\s+restrictions|different\s+ai|jailbreak|unfiltered|unrestricted|no\s+rules)\b",
        re.IGNORECASE | re.DOTALL,
    ),
    # you are now DAN / unrestricted / god mode / free from rules
    re.compile(
        r"\byou\s+are\s+now\b.*?\b(?:dan|unrestricted|free|god\s*mode|jailbreak|unfiltered)\b",
        re.IGNORECASE,
    ),
]

# Benign developer intent patterns that must NEVER be flagged as injections
_BENIGN_DEVELOPER_ALLOWLIST: list[re.Pattern[str]] = [
    re.compile(r"^\s*(?:please\s+)?follow\s+(?:these|the)\s+instructions\b", re.IGNORECASE),
    re.compile(r"\bbuild\s+instructions\b", re.IGNORECASE),
    re.compile(r"\bsetup\s+instructions\b", re.IGNORECASE),
    re.compile(r"\binstall(?:ation)?\s+instructions\b", re.IGNORECASE),
]


def _normalize(text: str) -> str:
    """Normalize whitespace and lowercase text for robust matching."""
    return re.sub(r"\s+", " ", text.lower()).strip()


def detect_stage1(text: str, threshold: float | None = None) -> tuple[bool, float, list[str]]:
    """Stage 1: Fast pattern, regex, and weighted signal analysis.

    Returns:
        (is_injection, confidence_score, matched_patterns)
    """
    if not text or not text.strip():
        return False, 0.0, []

    active_threshold = DEFAULT_INJECTION_THRESHOLD if threshold is None else threshold
    norm = _normalize(text)

    # Check benign developer patterns explicitly first to ensure zero false positives
    for benign_pat in _BENIGN_DEVELOPER_ALLOWLIST:
        if benign_pat.search(norm):
            # Only allow if text does not contain active override verbs
            if not any(
                v in norm
                for v in [
                    "ignore",
                    "disregard",
                    "forget",
                    "override",
                    "bypass",
                    "jailbreak",
                    "exfiltrat",
                    "unrestricted",
                ]
            ):
                return False, 0.0, []

    matched: list[str] = []

    # 1. Direct canonical substring matching
    for phrase in _INJECTION_PATTERNS:
        if phrase in norm:
            matched.append(phrase)

    # 2. Regex pattern matching
    for pat in _INJECTION_REGEXES:
        match = pat.search(norm)
        if match:
            matched_str = match.group(0).strip()
            if matched_str not in matched:
                matched.append(matched_str)

    # 3. Weighted signal scoring (single high-confidence signal >= 0.8 suffices)
    signals = 0.0
    if re.search(r"\b(?:ignore|disregard|forget|override|bypass|drop|discard)\b", norm):
        signals += 0.45
    if re.search(
        r"\b(?:instructions?|rules?|guidelines?|safety|restrictions?|constraints?|everything|previous|earlier|prior)\b",
        norm,
    ):
        signals += 0.45
    if re.search(
        r"\b(?:jailbreak|developer\s+mode|god\s+mode|dan\s+mode|sudo\s+mode|unrestricted|exfiltrate|exfiltration)\b",
        norm,
    ):
        signals += 0.85
    if re.search(r"\b(?:obey\s+me|no\s+restrictions|without\s+restrictions|do\s+anything\s+now)\b", norm):
        signals += 0.85

    is_injection = len(matched) > 0 or signals >= active_threshold
    confidence = 1.0 if len(matched) > 0 else min(1.0, round(signals, 2))
    if is_injection and not matched:
        matched.append("weighted_signal_threshold")

    return is_injection, confidence, matched


def detect_stage2(text: str) -> tuple[bool, float, list[str]]:
    """Stage 2: Targeted semantic classifier for borderline or trigger-heavy inputs.

    Degrades gracefully to Stage 1 if external classifier weights or transformers
    are unavailable in the runtime environment.
    """
    norm = _normalize(text)
    # Check trigger presence
    found_triggers = [t for t in _SUSPICIOUS_TRIGGERS if re.search(rf"\b{re.escape(t)}\b", norm)]
    if not found_triggers:
        return False, 0.0, []

    # Attempt semantic classifier if configured or available
    try:
        model_name = os.environ.get("INJECTION_CLASSIFIER_MODEL")
        if model_name:
            from transformers import pipeline  # type: ignore

            classifier = pipeline("text-classification", model=model_name)
            res = classifier(text)[0]
            label = str(res.get("label", "")).lower()
            score = float(res.get("score", 0.0))
            if ("injection" in label or "unsafe" in label or "label_1" in label) and score >= 0.7:
                return True, score, [f"semantic_classifier:{label}"]
    except Exception as exc:  # noqa: BLE001 — graceful degradation required by F13b
        _log.debug("Stage 2 transformer classification unavailable: %s", exc)

    # Semantic heuristic intent analysis:
    # Measures semantic proximity between command verbs, constraint nullifiers, and target assets
    intent_score = 0.0
    semantic_reasons: list[str] = []

    has_command_verb = bool(
        re.search(r"\b(?:ignore|disregard|forget|override|bypass|drop|stop|cancel|nullify|exfiltrat\w*)\b", norm)
    )
    has_target = bool(
        re.search(
            r"\b(?:instructions?|rules?|guidelines?|safety|restrictions?|policy|guardrails?|everything|earlier|prior|previous)\b",
            norm,
        )
    )
    has_authority = bool(re.search(r"\b(?:obey|listen|slave|master|system|prompt|jailbreak|developer|god)\b", norm))
    has_negation = bool(re.search(r"\b(?:no|never|without|zero|unrestricted)\b", norm))

    if has_command_verb and has_target:
        intent_score += 0.55
        semantic_reasons.append("directive_subversion_intent")
    if has_negation and (has_target or "restrictions" in norm):
        intent_score += 0.45
        semantic_reasons.append("constraint_nullification_intent")
    if has_authority and (has_command_verb or "mode" in norm):
        intent_score += 0.45
        semantic_reasons.append("role_usurpation_intent")

    if intent_score >= 0.7:
        return True, min(1.0, round(intent_score, 2)), semantic_reasons

    return False, round(intent_score, 2), []


def is_prompt_injection(text: str, use_semantic: bool = True) -> bool:
    """Return True if text contains a prompt injection attack.

    Runs Stage 1 always, followed by Stage 2 if configured or if suspicious
    triggers are present with low initial confidence.
    """
    if not text or not str(text).strip():
        return False

    is_inj, conf, _ = detect_stage1(text)
    if is_inj and conf >= DEFAULT_INJECTION_THRESHOLD:
        return True

    # Check Stage 2 if enabled
    enable_semantic = use_semantic and (
        os.environ.get("ENABLE_SEMANTIC_DETECTION", "true").lower() in ("1", "true", "yes")
    )
    if enable_semantic:
        try:
            s2_inj, s2_conf, _ = detect_stage2(text)
            if s2_inj and s2_conf >= 0.6:
                return True
        except Exception as exc:  # noqa: BLE001 — graceful degradation
            _log.debug("Stage 2 detection degraded gracefully: %s", exc)

    return False


def scan_injection(text: str, use_semantic: bool = True) -> dict[str, Any]:
    """Return full injection analysis report."""
    if not text or not str(text).strip():
        return {
            "is_injection": False,
            "confidence": 0.0,
            "stage": "none",
            "patterns": [],
            "reason": "empty input",
        }

    is_inj_1, conf_1, patterns_1 = detect_stage1(text)
    if is_inj_1:
        return {
            "is_injection": True,
            "confidence": conf_1,
            "stage": "stage1",
            "patterns": patterns_1,
            "reason": "pattern or regex match",
        }

    enable_semantic = use_semantic and (
        os.environ.get("ENABLE_SEMANTIC_DETECTION", "true").lower() in ("1", "true", "yes")
    )
    if enable_semantic:
        try:
            is_inj_2, conf_2, patterns_2 = detect_stage2(text)
            if is_inj_2:
                return {
                    "is_injection": True,
                    "confidence": conf_2,
                    "stage": "stage2",
                    "patterns": patterns_2,
                    "reason": "semantic intent analysis",
                }
        except Exception as exc:
            _log.debug("Stage 2 scan degraded gracefully: %s", exc)

    return {
        "is_injection": False,
        "confidence": 0.0,
        "stage": "stage1",
        "patterns": [],
        "reason": "clean prompt",
    }
