"""AlignmentSensor — tracks whether a conversation stays on-task and follows rules.

Like a GPS compass: measures direction (on_track / drifting / off_course),
task alignment with the original goal, rule compliance, and semantic drift.
"""

from __future__ import annotations

from collections.abc import Callable

from src.models.conversation import Conversation
from src.models.conversation import SensorReading
from src.models.conversation import Turn
from src.utils.logger import get_logger

logger = get_logger(__name__)


class AlignmentSensor:
    """Computes a SensorReading for each conversation turn."""

    def __init__(self, embed_fn: Callable[[str], list[float]] | None = None) -> None:
        if embed_fn is not None:
            self._embed = embed_fn
        else:
            try:
                from src.utils.embeddings import embed

                self._embed = embed
            except Exception:
                self._embed = lambda _: []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def measure(
        self,
        turn: Turn,
        conversation: Conversation,
        active_rule_keywords: list[list[str]],
    ) -> SensorReading:
        """Return a SensorReading for *turn* given the conversation so far."""
        # Anchor = the user's original goal (first turn input, or this turn if first)
        anchor = conversation.turns[0].user_input if conversation.turns else turn.user_input

        # Previous composite for heading delta
        prev_composite = self._prev_composite(conversation)

        task_alignment = self._task_alignment(turn.agent_response, anchor)
        rule_compliance = self._rule_compliance(turn.agent_response, active_rule_keywords)
        drift = self._drift_score(turn.user_input, anchor)

        composite = (task_alignment + rule_compliance + (1.0 - drift)) / 3.0
        heading = composite - prev_composite if prev_composite is not None else 0.0

        return SensorReading(
            task_alignment_score=round(task_alignment, 3),
            rule_compliance_score=round(rule_compliance, 3),
            drift_score=round(drift, 3),
            direction=self._direction(composite),
            heading=round(heading, 3),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _task_alignment(self, response: str, anchor: str) -> float:
        """Cosine similarity between the AI response and the original goal."""
        try:
            from src.utils.embeddings import cosine_similarity

            return cosine_similarity(self._embed(response), self._embed(anchor))
        except Exception as exc:
            logger.debug("task_alignment fallback", extra={"error": str(exc)})
            return 0.5

    def _rule_compliance(self, response: str, active_rule_keywords: list[list[str]]) -> float:
        """Fraction of active rules whose trigger keywords appear in the response."""
        if not active_rule_keywords:
            return 1.0
        response_lower = response.lower()
        matched = sum(1 for kws in active_rule_keywords if not kws or any(kw.lower() in response_lower for kw in kws))
        return matched / len(active_rule_keywords)

    def _drift_score(self, current_input: str, anchor: str) -> float:
        """Semantic distance from the original topic (0 = same, 1 = fully drifted)."""
        if current_input.strip() == anchor.strip():
            return 0.0
        try:
            from src.utils.embeddings import cosine_similarity

            sim = cosine_similarity(self._embed(current_input), self._embed(anchor))
            return max(0.0, 1.0 - sim)
        except Exception as exc:
            logger.debug("drift_score fallback", extra={"error": str(exc)})
            return 0.0

    @staticmethod
    def _direction(composite: float) -> str:
        if composite >= 0.7:
            return "on_track"
        if composite >= 0.4:
            return "drifting"
        return "off_course"

    @staticmethod
    def _prev_composite(conversation: Conversation) -> float | None:
        if not conversation.turns:
            return None
        reading = conversation.turns[-1].sensor_reading
        if reading is None:
            return None
        return (reading.task_alignment_score + reading.rule_compliance_score + (1.0 - reading.drift_score)) / 3.0
