"""ValidationService — measures and updates rule effectiveness.

Workflow:
1. Sample recent conversations where a given rule was applied.
2. Compare average sentiment before vs after turns where the rule fired.
3. Compute an effectiveness score in [0, 1].
4. Persist the updated score back to the DatasetManager.
5. Deactivate rules whose score falls below settings.EFFECTIVENESS_THRESHOLD.
"""

from __future__ import annotations

import random
from datetime import datetime
from typing import Any

from config.settings import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ValidationService:
    """Validates rule effectiveness and prunes underperforming rules."""

    def __init__(self, dataset_manager: Any) -> None:
        self._dm = dataset_manager

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate_all_rules(self) -> list[str]:
        """Validate every active rule and return the list of deactivated rule IDs."""
        rules = self._dm.load_rules(active_only=True)
        deactivated: list[str] = []

        for rule in rules:
            score = self._compute_effectiveness(rule)
            rule.effectiveness_score = score
            rule.updated_at = datetime.now()
            self._dm.update_rule(rule)

            if score < settings.EFFECTIVENESS_THRESHOLD and rule.times_triggered >= 10:
                self._dm.deactivate_rule(rule.rule_id)
                deactivated.append(rule.rule_id)
                logger.info(
                    "Rule deactivated (below threshold)",
                    extra={
                        "rule_id": rule.rule_id,
                        "score": score,
                        "threshold": settings.EFFECTIVENESS_THRESHOLD,
                    },
                )
            else:
                logger.info(
                    "Rule validated",
                    extra={"rule_id": rule.rule_id, "effectiveness": score},
                )

        return deactivated

    def validate_rule(self, rule_id: str) -> float | None:
        """Validate a single rule by ID.  Returns the computed effectiveness score."""
        rule = self._dm.get_rule(rule_id)
        if rule is None:
            logger.warning("Rule not found", extra={"rule_id": rule_id})
            return None

        score = self._compute_effectiveness(rule)
        rule.effectiveness_score = score
        rule.updated_at = datetime.now()
        self._dm.update_rule(rule)

        if score < settings.EFFECTIVENESS_THRESHOLD and rule.times_triggered >= 10:
            self._dm.deactivate_rule(rule_id)
            logger.info(
                "Rule deactivated after single validation",
                extra={"rule_id": rule_id, "score": score},
            )

        return score

    # ------------------------------------------------------------------
    # Effectiveness computation
    # ------------------------------------------------------------------

    def _compute_effectiveness(self, rule: Any) -> float:
        """Compute effectiveness as the sentiment improvement ratio.

        Strategy:
        - Load conversations where the rule was applied.
        - For each matched turn, measure sentiment_after - sentiment_before.
        - Effectiveness = fraction of turns where sentiment improved (delta > 0).

        Falls back to the rule's stored success_rate if no conversation data
        is available.
        """
        conversations = self._load_conversations_for_rule(rule.rule_id)
        if not conversations:
            # Fall back to stored counters
            return rule.success_rate

        sentiments_delta: list[float] = []

        for conv in conversations:
            for turn in conv.turns:
                if rule.rule_id not in turn.rules_applied:
                    continue
                if turn.sentiment_before is None or turn.sentiment_after is None:
                    continue
                sentiments_delta.append(turn.sentiment_after - turn.sentiment_before)

        if not sentiments_delta:
            return rule.success_rate

        improved = sum(1 for d in sentiments_delta if d > 0)
        score = improved / len(sentiments_delta)

        logger.debug(
            "Effectiveness computed",
            extra={
                "rule_id": rule.rule_id,
                "sample_size": len(sentiments_delta),
                "improved": improved,
                "score": score,
            },
        )
        return score

    def _load_conversations_for_rule(self, rule_id: str) -> list[Any]:
        """Sample at most VALIDATION_SAMPLE_SIZE conversations that used this rule."""
        try:
            all_conversations = self._dm.load_conversations()
        except Exception as exc:
            logger.warning(
                "Failed to load conversations for validation",
                extra={"rule_id": rule_id, "error": str(exc)},
            )
            return []

        # Filter to conversations that applied the rule
        relevant = [conv for conv in all_conversations if any(rule_id in turn.rules_applied for turn in conv.turns)]

        # Random sample to stay within budget
        if len(relevant) > settings.VALIDATION_SAMPLE_SIZE:
            relevant = random.sample(relevant, settings.VALIDATION_SAMPLE_SIZE)

        return relevant
