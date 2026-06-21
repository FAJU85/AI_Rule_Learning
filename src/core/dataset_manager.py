"""HuggingFace dataset CRUD for conversations and rules.

DatasetManager handles:
- Pushing new Conversation objects to the HF conversations dataset
- Pushing / updating Rule objects in the HF rules dataset
- Loading conversations and rules back for analysis and validation
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from config.settings import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class DatasetManager:
    """Manages persistent storage of conversations and rules on Hugging Face Hub."""

    def __init__(self) -> None:
        self._hf_token: str | None = settings.HF_TOKEN
        self._conversations_dataset: str = settings.HF_DATASET_NAME
        self._rules_dataset: str = settings.HF_RULES_DATASET
        self._api = None  # lazy-loaded

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_api(self):
        """Return a cached HfApi instance."""
        if self._api is None:
            try:
                from huggingface_hub import HfApi  # type: ignore

                self._api = HfApi(token=self._hf_token)
            except Exception as exc:
                logger.error("Failed to initialise HfApi", extra={"error": str(exc)})
                raise
        return self._api

    def _load_dataset(self, dataset_name: str) -> list[dict[str, Any]]:
        """Download and parse a JSONL dataset from the Hub."""
        try:
            from datasets import load_dataset  # type: ignore

            ds = load_dataset(dataset_name, token=self._hf_token, split="train")
            return [dict(row) for row in ds]
        except Exception as exc:
            logger.warning(
                "Could not load dataset",
                extra={"dataset": dataset_name, "error": str(exc)},
            )
            return []

    def _push_rows(self, dataset_name: str, rows: list[dict[str, Any]]) -> None:
        """Append *rows* to a Hub dataset by uploading a JSONL file."""

        try:
            from datasets import Dataset  # type: ignore

            existing = self._load_dataset(dataset_name)
            all_rows = existing + rows
            ds = Dataset.from_list(all_rows)
            ds.push_to_hub(dataset_name, token=self._hf_token)
            logger.info(
                "Dataset updated",
                extra={"dataset": dataset_name, "total_rows": len(all_rows)},
            )
        except Exception as exc:
            logger.error(
                "Failed to push rows to dataset",
                extra={"dataset": dataset_name, "error": str(exc)},
            )
            raise

    # ------------------------------------------------------------------
    # Conversation CRUD
    # ------------------------------------------------------------------

    def save_conversation(self, conversation: Conversation) -> None:  # type: ignore[name-defined]  # noqa: F821
        """Persist a completed Conversation to the HF conversations dataset."""

        row = json.loads(conversation.model_dump_json())
        self._push_rows(self._conversations_dataset, [row])
        logger.info(
            "Conversation saved",
            extra={"conversation_id": conversation.conversation_id},
        )

    def load_conversations(
        self,
        limit: int | None = None,
        since: datetime | None = None,
    ) -> list[Conversation]:  # type: ignore[name-defined]  # noqa: F821
        """Load conversations from the HF dataset, optionally filtered by date."""
        from src.models.conversation import Conversation

        rows = self._load_dataset(self._conversations_dataset)

        if since is not None:
            rows = [r for r in rows if datetime.fromisoformat(r.get("started_at", "1970-01-01")) >= since]

        if limit is not None:
            rows = rows[-limit:]  # most recent last

        conversations: list[Conversation] = []
        for row in rows:
            try:
                conversations.append(Conversation(**row))
            except Exception as exc:
                logger.warning(
                    "Skipping malformed conversation row",
                    extra={"error": str(exc)},
                )

        logger.info(
            "Conversations loaded",
            extra={"count": len(conversations)},
        )
        return conversations

    def get_conversation(self, conversation_id: str) -> Conversation | None:  # type: ignore[name-defined]  # noqa: F821
        """Fetch a single conversation by ID."""
        from src.models.conversation import Conversation

        rows = self._load_dataset(self._conversations_dataset)
        for row in rows:
            if row.get("conversation_id") == conversation_id:
                try:
                    return Conversation(**row)
                except Exception as exc:
                    logger.warning(
                        "Malformed conversation row",
                        extra={"conversation_id": conversation_id, "error": str(exc)},
                    )
        return None

    # ------------------------------------------------------------------
    # Rule CRUD
    # ------------------------------------------------------------------

    def save_rule(self, rule: Rule) -> None:  # type: ignore[name-defined]  # noqa: F821
        """Persist a new Rule to the HF rules dataset."""
        row = json.loads(rule.model_dump_json())
        rows = self._load_dataset(self._rules_dataset)

        # Upsert: replace existing rule with same ID if present
        rows = [r for r in rows if r.get("rule_id") != rule.rule_id]
        rows.append(row)

        try:
            from datasets import Dataset  # type: ignore

            ds = Dataset.from_list(rows)
            ds.push_to_hub(self._rules_dataset, token=self._hf_token)
            logger.info("Rule saved", extra={"rule_id": rule.rule_id})
        except Exception as exc:
            logger.error(
                "Failed to save rule",
                extra={"rule_id": rule.rule_id, "error": str(exc)},
            )
            raise

    def load_rules(self, active_only: bool = True) -> list[Rule]:  # type: ignore[name-defined]  # noqa: F821
        """Load rules from the HF rules dataset."""
        from src.models.rules import Rule

        rows = self._load_dataset(self._rules_dataset)
        rules: list[Rule] = []
        for row in rows:
            try:
                rule = Rule(**row)
                if active_only and not rule.is_active:
                    continue
                rules.append(rule)
            except Exception as exc:
                logger.warning(
                    "Skipping malformed rule row",
                    extra={"error": str(exc)},
                )

        logger.info("Rules loaded", extra={"count": len(rules)})
        return rules

    def get_rule(self, rule_id: str) -> Rule | None:  # type: ignore[name-defined]  # noqa: F821
        """Fetch a single rule by ID."""
        from src.models.rules import Rule

        rows = self._load_dataset(self._rules_dataset)
        for row in rows:
            if row.get("rule_id") == rule_id:
                try:
                    return Rule(**row)
                except Exception as exc:
                    logger.warning(
                        "Malformed rule row",
                        extra={"rule_id": rule_id, "error": str(exc)},
                    )
        return None

    def update_rule(self, rule: Rule) -> None:  # type: ignore[name-defined]  # noqa: F821
        """Update an existing rule (full replacement by rule_id)."""
        self.save_rule(rule)

    def deactivate_rule(self, rule_id: str) -> None:
        """Mark a rule as inactive in the dataset."""
        rule = self.get_rule(rule_id)
        if rule is None:
            logger.warning("Rule not found for deactivation", extra={"rule_id": rule_id})
            return
        rule.is_active = False
        rule.updated_at = datetime.now()
        self.save_rule(rule)
        logger.info("Rule deactivated", extra={"rule_id": rule_id})
