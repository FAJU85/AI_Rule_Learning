"""RuleEngine — matches active rules to a conversation context and builds system prompts.

Workflow:
1. Load rules from DatasetManager (or Redis cache).
2. For each incoming context, score every active rule by keyword + embedding similarity.
3. Return matched rules sorted by priority.
4. Build an injected system-prompt snippet from matched rules.
5. Track rule effectiveness (times_triggered, success_count).
"""
from __future__ import annotations

import json
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

import redis

from config.settings import settings
from src.utils.embeddings import cosine_similarity
from src.utils.embeddings import embed
from src.utils.logger import get_logger

logger = get_logger(__name__)

_REDIS_RULES_KEY = "active_rules"


class RuleEngine:
    """Loads, matches, and tracks rules for a given conversation context."""

    def __init__(
        self,
        dataset_manager: Optional[Any] = None,
        redis_client: Optional[redis.Redis] = None,
    ) -> None:
        self._dataset_manager = dataset_manager
        self._redis: Optional[redis.Redis] = redis_client
        self._rules: List[Any] = []  # in-memory cache

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def load_rules(self) -> None:
        """Load active rules from Redis (if available) or HuggingFace dataset."""
        if self._try_load_from_redis():
            return

        if self._dataset_manager is None:
            logger.warning("No DatasetManager configured — no rules loaded")
            return

        try:
            self._rules = self._dataset_manager.load_rules(active_only=True)
            self._cache_rules_in_redis()
            logger.info("Rules loaded from HuggingFace", extra={"count": len(self._rules)})
        except Exception as exc:
            logger.error("Failed to load rules", extra={"error": str(exc)})

    def _try_load_from_redis(self) -> bool:
        if self._redis is None:
            return False
        try:
            raw = self._redis.get(_REDIS_RULES_KEY)
            if raw is None:
                return False
            from src.models.rules import Rule

            data = json.loads(raw)
            self._rules = [Rule(**r) for r in data]
            logger.info("Rules loaded from Redis cache", extra={"count": len(self._rules)})
            return True
        except Exception as exc:
            logger.warning("Redis cache miss / error", extra={"error": str(exc)})
            return False

    def _cache_rules_in_redis(self) -> None:
        if self._redis is None:
            return
        try:
            serialised = json.dumps([json.loads(r.model_dump_json()) for r in self._rules])
            self._redis.setex(_REDIS_RULES_KEY, settings.REDIS_RULE_TTL, serialised)
        except Exception as exc:
            logger.warning("Failed to cache rules in Redis", extra={"error": str(exc)})

    # ------------------------------------------------------------------
    # Matching
    # ------------------------------------------------------------------

    def match_rules(
        self,
        context: str,
        sentiment: Optional[float] = None,
        top_k: int = 5,
    ) -> List[Any]:
        """Return the top-k rules that match *context*, sorted by priority (desc).

        Matching criteria (any one is sufficient):
        - A keyword from rule.trigger.keywords appears in the context (case-insensitive).
        - The cosine similarity between rule.trigger.embedding and the context embedding
          exceeds settings.GAP_THRESHOLD.
        - The current sentiment is below rule.trigger.sentiment_threshold.
        """
        if not self._rules:
            self.load_rules()

        context_lower = context.lower()
        context_embedding = embed(context) if context.strip() else []

        matched: List[Any] = []

        for rule in self._rules:
            if not rule.is_active:
                continue

            if self._matches(rule, context_lower, context_embedding, sentiment):
                matched.append(rule)

        # Sort by priority (higher = more important) then by effectiveness
        matched.sort(key=lambda r: (r.priority, r.effectiveness_score), reverse=True)
        return matched[:top_k]

    def _matches(
        self,
        rule: Any,
        context_lower: str,
        context_embedding: List[float],
        sentiment: Optional[float],
    ) -> bool:
        trigger = rule.trigger

        # Keyword match
        for kw in trigger.keywords:
            if kw.lower() in context_lower:
                return True

        # Topic match (same as keyword for our purposes)
        for topic in trigger.topics:
            if topic.lower() in context_lower:
                return True

        # Sentiment threshold
        if trigger.sentiment_threshold is not None and sentiment is not None:
            if sentiment <= trigger.sentiment_threshold:
                return True

        # Embedding similarity
        if trigger.embedding and context_embedding:
            sim = cosine_similarity(trigger.embedding, context_embedding)
            if sim >= settings.GAP_THRESHOLD:
                return True

        return False

    # ------------------------------------------------------------------
    # Prompt building
    # ------------------------------------------------------------------

    def build_system_prompt(self, matched_rules: List[Any], base_prompt: str = "") -> str:
        """Build an injected system prompt from matched rules.

        Rules are sorted by priority (highest first) and their instructions
        are appended to *base_prompt*.
        """
        if not matched_rules:
            return base_prompt

        rule_lines: List[str] = []
        for rule in matched_rules:
            prefix = f"[{rule.priority.name}]"
            rule_lines.append(f"{prefix} {rule.action.instruction}")
            if rule.action.template:
                rule_lines.append(f"  Template: {rule.action.template}")

        injected = "\n".join(rule_lines)
        separator = "\n\n" if base_prompt else ""
        return f"{base_prompt}{separator}--- Active Rules ---\n{injected}"

    # ------------------------------------------------------------------
    # Effectiveness tracking
    # ------------------------------------------------------------------

    def record_triggered(self, rule_id: str) -> None:
        """Increment times_triggered for a rule and persist."""
        self._update_rule_counter(rule_id, triggered=True, success=None)

    def record_success(self, rule_id: str) -> None:
        """Increment success_count for a rule and persist."""
        self._update_rule_counter(rule_id, triggered=False, success=True)

    def record_failure(self, rule_id: str) -> None:
        """Increment failure_count for a rule and persist."""
        self._update_rule_counter(rule_id, triggered=False, success=False)

    def _update_rule_counter(
        self, rule_id: str, triggered: bool, success: Optional[bool]
    ) -> None:
        from datetime import datetime

        for rule in self._rules:
            if rule.rule_id != rule_id:
                continue
            if triggered:
                rule.times_triggered += 1
            elif success is True:
                rule.success_count += 1
            elif success is False:
                rule.failure_count += 1
            rule.updated_at = datetime.now()

            if self._dataset_manager is not None:
                try:
                    self._dataset_manager.update_rule(rule)
                except Exception as exc:
                    logger.warning(
                        "Failed to persist rule counter update",
                        extra={"rule_id": rule_id, "error": str(exc)},
                    )
            break
        else:
            logger.warning("Rule not found for counter update", extra={"rule_id": rule_id})

    # ------------------------------------------------------------------
    # Invalidation
    # ------------------------------------------------------------------

    def invalidate_cache(self) -> None:
        """Clear the Redis cache and in-memory rule list."""
        self._rules = []
        if self._redis is not None:
            try:
                self._redis.delete(_REDIS_RULES_KEY)
            except Exception as exc:
                logger.warning("Failed to clear Redis cache", extra={"error": str(exc)})
