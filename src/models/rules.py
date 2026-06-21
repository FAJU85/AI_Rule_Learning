from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel
from pydantic import Field


class RulePriority(int, Enum):
    CRITICAL = 5
    HIGH = 4
    MEDIUM = 3
    LOW = 2
    INFO = 1


class RuleType(str, Enum):
    SEMGREP = "semgrep"
    GUARDRAIL = "guardrail"
    PRE_COMMIT = "pre_commit"


class RuleAction(BaseModel):
    type: str
    instruction: str
    template: str | None = None


class RuleTrigger(BaseModel):
    sentiment_threshold: float | None = None
    keywords: list[str] = []
    topics: list[str] = []
    embedding: list[float] | None = None
    pattern: str | None = None


class Rule(BaseModel):
    rule_id: str
    version: int = 1
    name: str
    description: str
    rule_type: RuleType
    priority: RulePriority
    trigger: RuleTrigger
    action: RuleAction
    languages: list[str] = ["python"]
    is_active: bool = True
    effectiveness_score: float = 0.0
    times_triggered: int = 0
    success_count: int = 0
    failure_count: int = 0
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    source_conversation: str | None = None
    metadata: dict[str, Any] = {}

    @property
    def success_rate(self) -> float:
        if self.times_triggered == 0:
            return 0.0
        return self.success_count / self.times_triggered
