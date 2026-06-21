"""AnalysisService — mines recent conversations for gaps and generates new rules.

Workflow:
1. Load recent conversations from DatasetManager.
2. Run GapDetector on each conversation.
3. Group similar gaps by type.
4. For any group with >= settings.MIN_GAPS_FOR_RULE occurrences, ask the AI to
   generate a refined Rule.
5. Deploy new rules via DatasetManager and return the list.
"""

from __future__ import annotations

import json
import uuid
from collections import defaultdict
from datetime import datetime
from datetime import timedelta
from typing import Any

from config.settings import settings
from src.core.gap_detector import GapDetector
from src.models.rules import Rule
from src.models.rules import RuleAction
from src.models.rules import RulePriority
from src.models.rules import RuleTrigger
from src.models.rules import RuleType
from src.utils.logger import get_logger

logger = get_logger(__name__)


class AnalysisService:
    """Analyses conversations and derives new rules from recurring gaps."""

    def __init__(
        self,
        dataset_manager: Any,
        adapter: Any,
        gap_detector: GapDetector | None = None,
    ) -> None:
        self._dm = dataset_manager
        self._adapter = adapter
        self._gap_detector = gap_detector or GapDetector()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze_recent(
        self,
        lookback_hours: int = 24,
        limit: int = 500,
    ) -> list[Rule]:
        """Analyse conversations from the last *lookback_hours* hours.

        Returns a list of newly created Rule objects.
        """
        since = datetime.now() - timedelta(hours=lookback_hours)

        logger.info(
            "Starting analysis",
            extra={"lookback_hours": lookback_hours, "since": since.isoformat()},
        )

        conversations = self._dm.load_conversations(limit=limit, since=since)
        if not conversations:
            logger.info("No conversations found in lookback window")
            return []

        # Collect all gaps with their source conversation ID
        gap_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)

        for conv in conversations:
            if len(conv.turns) < settings.MIN_SESSION_LENGTH:
                continue
            gaps = self._gap_detector.detect(conv.turns)
            for gap in gaps:
                gap["source_conversation"] = conv.conversation_id
                gap_type = gap["type"]
                gap_groups[gap_type].append(gap)

        logger.info(
            "Gap grouping complete",
            extra={
                "conversations_analysed": len(conversations),
                "gap_types": len(gap_groups),
            },
        )

        new_rules: list[Rule] = []
        for gap_type, occurrences in gap_groups.items():
            if len(occurrences) < settings.MIN_GAPS_FOR_RULE:
                logger.debug(
                    "Skipping gap type (insufficient occurrences)",
                    extra={"gap_type": gap_type, "count": len(occurrences)},
                )
                continue

            rule = self._generate_rule(gap_type, occurrences)
            if rule is not None:
                self._dm.save_rule(rule)
                new_rules.append(rule)
                logger.info(
                    "New rule deployed",
                    extra={"rule_id": rule.rule_id, "gap_type": gap_type},
                )

        logger.info("Analysis complete", extra={"new_rules": len(new_rules)})
        return new_rules

    # ------------------------------------------------------------------
    # Rule generation
    # ------------------------------------------------------------------

    def _generate_rule(self, gap_type: str, occurrences: list[dict[str, Any]]) -> Rule | None:
        """Ask the AI to generate a rule definition for a recurring gap type."""
        sample = occurrences[:5]  # cap prompt size
        avg_severity = sum(o.get("severity", 1) for o in occurrences) / len(occurrences)
        source_conv = occurrences[0].get("source_conversation", "unknown")

        prompt = self._build_rule_generation_prompt(gap_type, sample, avg_severity)

        try:
            raw_response = self._adapter.generate_response(
                user_input=prompt,
                system_prompt=(
                    "You are a rule engineering assistant. "
                    "Always respond with valid JSON only. No markdown, no explanation."
                ),
            )
            rule_data = json.loads(raw_response.strip())
            rule = self._parse_rule_from_ai(rule_data, gap_type, source_conv, avg_severity)
            return rule
        except json.JSONDecodeError as exc:
            logger.warning(
                "AI returned invalid JSON for rule generation",
                extra={"gap_type": gap_type, "error": str(exc)},
            )
            return self._fallback_rule(gap_type, occurrences, source_conv, avg_severity)
        except Exception as exc:
            logger.error(
                "Rule generation failed",
                extra={"gap_type": gap_type, "error": str(exc)},
            )
            return None

    @staticmethod
    def _build_rule_generation_prompt(
        gap_type: str,
        sample_gaps: list[dict[str, Any]],
        avg_severity: float,
    ) -> str:
        examples_text = "\n".join(
            f"- Turn {g.get('turn_number', '?')}: {g.get('evidence', '')[:120]}" for g in sample_gaps
        )
        return f"""A recurring AI conversation problem has been detected.

Gap type: {gap_type}
Average severity: {avg_severity:.1f} / 5
Sample occurrences:
{examples_text}

Generate a guardrail rule to prevent this problem. Respond with JSON matching this schema:
{{
  "name": "short rule name",
  "description": "what this rule prevents",
  "keywords": ["list", "of", "trigger", "keywords"],
  "topics": ["topic1"],
  "sentiment_threshold": null_or_float,
  "instruction": "what the AI should do when this rule triggers",
  "template": null_or_string
}}"""

    def _parse_rule_from_ai(
        self,
        data: dict[str, Any],
        gap_type: str,
        source_conv: str,
        avg_severity: float,
    ) -> Rule:
        priority = self._severity_to_priority(avg_severity)
        return Rule(
            rule_id=str(uuid.uuid4()),
            name=data.get("name", f"auto-rule-{gap_type}"),
            description=data.get("description", f"Auto-generated rule for {gap_type}"),
            rule_type=RuleType.GUARDRAIL,
            priority=priority,
            trigger=RuleTrigger(
                keywords=data.get("keywords", []),
                topics=data.get("topics", []),
                sentiment_threshold=data.get("sentiment_threshold"),
            ),
            action=RuleAction(
                type="inject_instruction",
                instruction=data.get("instruction", ""),
                template=data.get("template"),
            ),
            source_conversation=source_conv,
            metadata={"gap_type": gap_type, "avg_severity": avg_severity},
        )

    def _fallback_rule(
        self,
        gap_type: str,
        occurrences: list[dict[str, Any]],
        source_conv: str,
        avg_severity: float,
    ) -> Rule:
        """Return a minimal heuristic rule when AI generation fails."""
        description = occurrences[0].get("description", f"Recurring gap: {gap_type}")
        priority = self._severity_to_priority(avg_severity)
        return Rule(
            rule_id=str(uuid.uuid4()),
            name=f"auto-{gap_type.replace(':', '-')}",
            description=description,
            rule_type=RuleType.GUARDRAIL,
            priority=priority,
            trigger=RuleTrigger(keywords=[], topics=[]),
            action=RuleAction(
                type="inject_instruction",
                instruction=f"Be aware of the following recurring issue: {description}",
            ),
            source_conversation=source_conv,
            metadata={"gap_type": gap_type, "avg_severity": avg_severity},
        )

    @staticmethod
    def _severity_to_priority(avg_severity: float) -> RulePriority:
        if avg_severity >= 4.5:
            return RulePriority.CRITICAL
        if avg_severity >= 3.5:
            return RulePriority.HIGH
        if avg_severity >= 2.5:
            return RulePriority.MEDIUM
        if avg_severity >= 1.5:
            return RulePriority.LOW
        return RulePriority.INFO
