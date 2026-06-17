"""GapDetector — identifies conversation gaps that could become rules.

Detects:
- Sentiment drops between turns
- Explicit user corrections ("actually", "no, that's wrong", etc.)
- Repeated questions (user asks same thing more than once)
- Code anti-patterns (bare except, eval, hardcoded secrets, etc.)
"""
from __future__ import annotations

import re
from typing import Any
from typing import Dict
from typing import List

from config.settings import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Type alias for a detected gap
# ---------------------------------------------------------------------------
Gap = Dict[str, Any]

# ---------------------------------------------------------------------------
# Patterns used in code-level detection
# ---------------------------------------------------------------------------
_CODE_ANTI_PATTERNS: List[Dict[str, Any]] = [
    {
        "name": "bare_except",
        "pattern": re.compile(r"\bexcept\s*:", re.MULTILINE),
        "description": "Bare except clause catches all exceptions including SystemExit and KeyboardInterrupt.",
        "severity": 3,
    },
    {
        "name": "eval_usage",
        "pattern": re.compile(r"\beval\s*\("),
        "description": "Use of eval() is a security risk and should be avoided.",
        "severity": 4,
    },
    {
        "name": "hardcoded_secret",
        "pattern": re.compile(
            r'(?i)(password|secret|api_key|token)\s*=\s*["\'][^"\']{4,}["\']'
        ),
        "description": "Hardcoded secret or credential detected.",
        "severity": 5,
    },
    {
        "name": "print_debugging",
        "pattern": re.compile(r"\bprint\s*\("),
        "description": "print() used instead of logging framework.",
        "severity": 1,
    },
    {
        "name": "mutable_default_arg",
        "pattern": re.compile(r"def\s+\w+\s*\([^)]*=\s*[\[\{]"),
        "description": "Mutable default argument in function definition.",
        "severity": 3,
    },
    {
        "name": "missing_error_handling",
        "pattern": re.compile(r"\bopen\s*\([^)]+\)(?!\s*as\b)"),
        "description": "File opened without context manager (with statement).",
        "severity": 3,
    },
]

_CORRECTION_PHRASES: List[str] = [
    "actually",
    "no, that",
    "that's wrong",
    "that is wrong",
    "incorrect",
    "not right",
    "you're wrong",
    "you are wrong",
    "that's not",
    "that is not",
    "wrong answer",
    "please fix",
    "try again",
    "not what i asked",
    "that doesn't answer",
    "that does not answer",
]


class GapDetector:
    """Analyse a list of Turn objects and return a list of Gap dicts."""

    def __init__(self, gap_threshold: float | None = None) -> None:
        self._threshold = gap_threshold if gap_threshold is not None else settings.GAP_THRESHOLD

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect(self, turns: List[Any]) -> List[Gap]:
        """Return all gaps found in *turns*.

        Each Gap dict contains at minimum:
            type        str   — gap category
            severity    int   — 1 (low) … 5 (critical)
            turn_number int   — which turn triggered the gap
            evidence    str   — relevant text excerpt
            description str   — human-readable explanation
        """
        gaps: List[Gap] = []

        gaps.extend(self._detect_sentiment_drops(turns))
        gaps.extend(self._detect_explicit_corrections(turns))
        gaps.extend(self._detect_repeated_questions(turns))
        gaps.extend(self._detect_code_anti_patterns(turns))

        logger.info(
            "Gap detection complete",
            extra={"total_turns": len(turns), "gaps_found": len(gaps)},
        )
        return gaps

    # ------------------------------------------------------------------
    # Individual detectors
    # ------------------------------------------------------------------

    def _detect_sentiment_drops(self, turns: List[Any]) -> List[Gap]:
        gaps: List[Gap] = []
        for turn in turns:
            before = turn.sentiment_before
            after = turn.sentiment_after
            if before is None or after is None:
                continue
            drop = before - after  # positive value means sentiment got worse
            if drop >= self._threshold:
                gaps.append(
                    {
                        "type": "sentiment_drop",
                        "severity": self._severity_from_drop(drop),
                        "turn_number": turn.turn_number,
                        "evidence": f"sentiment before={before:.2f}, after={after:.2f}, drop={drop:.2f}",
                        "description": (
                            f"User sentiment dropped by {drop:.2f} after turn {turn.turn_number}. "
                            "The AI response may have been unhelpful or dismissive."
                        ),
                    }
                )
        return gaps

    def _detect_explicit_corrections(self, turns: List[Any]) -> List[Gap]:
        gaps: List[Gap] = []
        for turn in turns:
            text_lower = turn.user_input.lower()
            for phrase in _CORRECTION_PHRASES:
                if phrase in text_lower:
                    gaps.append(
                        {
                            "type": "explicit_correction",
                            "severity": 3,
                            "turn_number": turn.turn_number,
                            "evidence": turn.user_input[:200],
                            "description": (
                                f'User explicitly corrected the AI at turn {turn.turn_number} '
                                f'(matched phrase: "{phrase}").'
                            ),
                        }
                    )
                    break  # one gap per turn
        return gaps

    def _detect_repeated_questions(self, turns: List[Any]) -> List[Gap]:
        """Flag when the user asks essentially the same question more than once."""
        gaps: List[Gap] = []
        seen: Dict[str, int] = {}  # normalised question → first turn number

        for turn in turns:
            normalised = self._normalise(turn.user_input)
            if normalised in seen:
                gaps.append(
                    {
                        "type": "repeated_question",
                        "severity": 2,
                        "turn_number": turn.turn_number,
                        "evidence": turn.user_input[:200],
                        "description": (
                            f"User repeated a question at turn {turn.turn_number} "
                            f"(first asked at turn {seen[normalised]}). "
                            "The earlier AI response may have been insufficient."
                        ),
                    }
                )
            else:
                seen[normalised] = turn.turn_number

        return gaps

    def _detect_code_anti_patterns(self, turns: List[Any]) -> List[Gap]:
        gaps: List[Gap] = []
        for turn in turns:
            response = turn.agent_response
            for rule in _CODE_ANTI_PATTERNS:
                match = rule["pattern"].search(response)
                if match:
                    gaps.append(
                        {
                            "type": f"code_anti_pattern:{rule['name']}",
                            "severity": rule["severity"],
                            "turn_number": turn.turn_number,
                            "evidence": match.group(0)[:200],
                            "description": rule["description"],
                        }
                    )
        return gaps

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _severity_from_drop(drop: float) -> int:
        if drop >= 1.5:
            return 5
        if drop >= 1.0:
            return 4
        if drop >= 0.6:
            return 3
        if drop >= 0.3:
            return 2
        return 1

    @staticmethod
    def _normalise(text: str) -> str:
        """Strip punctuation / case for rough duplicate detection."""
        text = text.lower().strip()
        text = re.sub(r"[^\w\s]", "", text)
        text = re.sub(r"\s+", " ", text)
        return text
