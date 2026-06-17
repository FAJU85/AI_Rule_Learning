"""pytest fixtures shared across the test suite."""
from __future__ import annotations

import uuid
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from src.models.conversation import Conversation
from src.models.conversation import Turn
from src.models.rules import Rule
from src.models.rules import RuleAction
from src.models.rules import RulePriority
from src.models.rules import RuleTrigger
from src.models.rules import RuleType


# ---------------------------------------------------------------------------
# DatasetManager mock
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_dataset_manager():
    """Return a MagicMock that quacks like DatasetManager."""
    dm = MagicMock()
    dm.load_rules.return_value = []
    dm.load_conversations.return_value = []
    dm.get_rule.return_value = None
    dm.get_conversation.return_value = None
    dm.save_rule.return_value = None
    dm.save_conversation.return_value = None
    dm.update_rule.return_value = None
    dm.deactivate_rule.return_value = None
    return dm


# ---------------------------------------------------------------------------
# Conversation fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_turn() -> Turn:
    return Turn(
        turn_number=1,
        user_input="How do I handle exceptions in Python?",
        agent_response="You can use a bare except: clause.",
        sentiment_before=0.5,
        sentiment_after=0.2,
        timestamp=datetime(2024, 1, 15, 10, 0, 0),
    )


@pytest.fixture()
def sample_conversation(sample_turn: Turn) -> Conversation:
    conv = Conversation(
        conversation_id=str(uuid.uuid4()),
        session_id="test-session-1",
        user_id="user-001",
        started_at=datetime(2024, 1, 15, 10, 0, 0),
    )
    conv.add_turn(sample_turn)
    # Add a second turn so it passes MIN_SESSION_LENGTH = 3 when needed
    conv.add_turn(
        Turn(
            turn_number=2,
            user_input="Actually, that's wrong. Bare except is bad practice.",
            agent_response="You are right. Use specific exception types instead.",
            sentiment_before=0.2,
            sentiment_after=0.6,
            timestamp=datetime(2024, 1, 15, 10, 1, 0),
        )
    )
    conv.add_turn(
        Turn(
            turn_number=3,
            user_input="How do I handle exceptions in Python?",  # repeated
            agent_response="Use specific exception types like ValueError or KeyError.",
            sentiment_before=0.6,
            sentiment_after=0.7,
            timestamp=datetime(2024, 1, 15, 10, 2, 0),
        )
    )
    return conv


# ---------------------------------------------------------------------------
# Rule fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_rule() -> Rule:
    return Rule(
        rule_id=str(uuid.uuid4()),
        name="no-bare-except",
        description="Prevent the AI from suggesting bare except clauses.",
        rule_type=RuleType.GUARDRAIL,
        priority=RulePriority.HIGH,
        trigger=RuleTrigger(
            keywords=["except", "exception handling", "try catch"],
            topics=["error handling", "python best practices"],
            sentiment_threshold=None,
        ),
        action=RuleAction(
            type="inject_instruction",
            instruction=(
                "Never suggest bare `except:` clauses. "
                "Always recommend catching specific exception types."
            ),
        ),
        languages=["python"],
        created_at=datetime(2024, 1, 1, 0, 0, 0),
        updated_at=datetime(2024, 1, 1, 0, 0, 0),
    )


@pytest.fixture()
def active_rule_with_stats() -> Rule:
    rule = Rule(
        rule_id=str(uuid.uuid4()),
        name="no-eval",
        description="Never suggest eval().",
        rule_type=RuleType.GUARDRAIL,
        priority=RulePriority.CRITICAL,
        trigger=RuleTrigger(keywords=["eval"]),
        action=RuleAction(
            type="inject_instruction",
            instruction="Never suggest eval(). Use ast.literal_eval or safer alternatives.",
        ),
        times_triggered=20,
        success_count=15,
        failure_count=5,
    )
    return rule


# ---------------------------------------------------------------------------
# AI adapter mock
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_adapter():
    adapter = MagicMock()
    adapter.name = "mock"
    adapter.generate_response.return_value = "This is a mock AI response."
    adapter.health_check.return_value = True
    return adapter
