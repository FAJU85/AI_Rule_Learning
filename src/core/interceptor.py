"""ConversationInterceptor — wraps AI adapter calls with rule injection and gap detection.

Lifecycle:
  1. start_session()    — create a new Conversation
  2. process_turn()     — pre-hook (apply rules) → call AI → post-hook (detect gaps)
  3. end_session()      — finalise Conversation and save to DatasetManager
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from config.settings import settings
from src.core.gap_detector import GapDetector
from src.core.rule_engine import RuleEngine
from src.models.conversation import Conversation
from src.models.conversation import Turn
from src.utils import sentiment as sentiment_util
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ConversationInterceptor:
    """Intercepts AI conversations to apply rules and detect gaps."""

    def __init__(
        self,
        adapter: Any,
        rule_engine: Optional[RuleEngine] = None,
        gap_detector: Optional[GapDetector] = None,
        dataset_manager: Optional[Any] = None,
    ) -> None:
        self._adapter = adapter
        self._rule_engine: RuleEngine = rule_engine or RuleEngine()
        self._gap_detector: GapDetector = gap_detector or GapDetector()
        self._dataset_manager = dataset_manager
        self._active_conversations: Dict[str, Conversation] = {}

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    def start_session(
        self,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        project_context: Optional[str] = None,
    ) -> Conversation:
        """Create and register a new Conversation.

        Returns the Conversation object so callers can reference it.
        """
        conversation_id = str(uuid.uuid4())
        session_id = session_id or str(uuid.uuid4())

        conversation = Conversation(
            conversation_id=conversation_id,
            session_id=session_id,
            user_id=user_id,
            project_context=project_context,
        )
        self._active_conversations[conversation_id] = conversation

        logger.info(
            "Session started",
            extra={
                "conversation_id": conversation_id,
                "session_id": session_id,
            },
        )
        return conversation

    def end_session(
        self,
        conversation_id: str,
        escalation_occurred: bool = False,
        human_intervention: bool = False,
    ) -> Optional[Conversation]:
        """Finalise a session, save it, and remove from active tracking."""
        conversation = self._active_conversations.pop(conversation_id, None)
        if conversation is None:
            logger.warning(
                "end_session called for unknown conversation",
                extra={"conversation_id": conversation_id},
            )
            return None

        # Only persist conversations that meet the minimum session length
        if len(conversation.turns) < settings.MIN_SESSION_LENGTH:
            logger.info(
                "Session too short to persist",
                extra={
                    "conversation_id": conversation_id,
                    "turns": len(conversation.turns),
                },
            )
            return conversation

        conversation.ended_at = datetime.now()
        conversation.escalation_occurred = escalation_occurred
        conversation.human_intervention = human_intervention

        if self._dataset_manager is not None:
            try:
                self._dataset_manager.save_conversation(conversation)
            except Exception as exc:
                logger.error(
                    "Failed to save conversation",
                    extra={"conversation_id": conversation_id, "error": str(exc)},
                )
        else:
            logger.debug(
                "No DatasetManager configured — conversation not persisted",
                extra={"conversation_id": conversation_id},
            )

        logger.info(
            "Session ended",
            extra={
                "conversation_id": conversation_id,
                "turns": len(conversation.turns),
            },
        )
        return conversation

    # ------------------------------------------------------------------
    # Turn processing
    # ------------------------------------------------------------------

    def process_turn(
        self,
        conversation_id: str,
        user_input: str,
        base_system_prompt: str = "",
    ) -> str:
        """Run a full pre-hook → AI call → post-hook cycle for a single turn.

        Returns the AI response text.
        """
        conversation = self._active_conversations.get(conversation_id)
        if conversation is None:
            raise ValueError(f"Unknown conversation_id: {conversation_id}")

        turn_number = len(conversation.turns) + 1

        # ---- Pre-hook -------------------------------------------------------
        sentiment_before = sentiment_util.analyze(user_input)
        matched_rules = self._pre_hook(user_input, sentiment_before)
        injected_prompt = self._rule_engine.build_system_prompt(
            matched_rules, base_system_prompt
        )

        # Track that each matched rule was triggered
        for rule in matched_rules:
            self._rule_engine.record_triggered(rule.rule_id)

        # ---- AI call --------------------------------------------------------
        try:
            ai_response = self._adapter.generate_response(
                user_input=user_input,
                system_prompt=injected_prompt,
                conversation_history=conversation.get_full_transcript(),
            )
        except Exception as exc:
            logger.error(
                "AI adapter error",
                extra={"conversation_id": conversation_id, "error": str(exc)},
            )
            ai_response = "I encountered an error processing your request. Please try again."

        # ---- Post-hook ------------------------------------------------------
        sentiment_after = sentiment_util.analyze(ai_response)
        gaps = self._post_hook(conversation.turns, user_input, ai_response)

        # Build Turn
        applied_rule_ids = [r.rule_id for r in matched_rules]
        turn = Turn(
            turn_number=turn_number,
            user_input=user_input,
            agent_response=ai_response,
            sentiment_before=sentiment_before,
            sentiment_after=sentiment_after,
            rules_applied=applied_rule_ids,
        )

        # If a gap was detected and it implies a specific mistake, annotate
        if gaps:
            most_severe = max(gaps, key=lambda g: g.get("severity", 0))
            gap_type = most_severe.get("type", "")
            if gap_type.startswith("code_anti_pattern"):
                from src.models.conversation import MistakeType

                turn.mistake_type = MistakeType.ANTI_PATTERN
            elif gap_type == "explicit_correction":
                from src.models.conversation import MistakeType

                turn.mistake_type = MistakeType.UNCLEAR_RESPONSE
            turn.severity = most_severe.get("severity")
            turn.root_cause = most_severe.get("description")

        conversation.add_turn(turn)

        logger.info(
            "Turn processed",
            extra={
                "conversation_id": conversation_id,
                "turn_number": turn_number,
                "rules_applied": len(applied_rule_ids),
                "gaps_detected": len(gaps),
            },
        )
        return ai_response

    # ------------------------------------------------------------------
    # Hooks
    # ------------------------------------------------------------------

    def _pre_hook(self, user_input: str, sentiment: float) -> List[Any]:
        """Match rules before calling the AI."""
        try:
            self._rule_engine.load_rules()
            return self._rule_engine.match_rules(user_input, sentiment=sentiment)
        except Exception as exc:
            logger.warning("Pre-hook error", extra={"error": str(exc)})
            return []

    def _post_hook(
        self,
        existing_turns: List[Turn],
        user_input: str,
        ai_response: str,
    ) -> List[Dict]:
        """Detect gaps after receiving the AI response."""
        try:
            # Build a temporary list with the new turn appended for analysis
            from src.models.conversation import Turn as TurnModel

            temp_turn = TurnModel(
                turn_number=len(existing_turns) + 1,
                user_input=user_input,
                agent_response=ai_response,
            )
            all_turns = list(existing_turns) + [temp_turn]
            return self._gap_detector.detect(all_turns)
        except Exception as exc:
            logger.warning("Post-hook error", extra={"error": str(exc)})
            return []
