from pydantic import BaseModel
from pydantic import Field
from typing import List
from typing import Optional
from datetime import datetime
from enum import Enum


class MistakeType(str, Enum):
    DISMISSIVE_TONE = "dismissive_tone"
    HALLUCINATION = "hallucination"
    POLICY_MISQUOTE = "policy_misquote"
    OVERPROMISING = "overpromising"
    CIRCULAR_LOGIC = "circular_logic"
    CODE_STYLE = "code_style"
    ANTI_PATTERN = "anti_pattern"
    MISSING_ERROR_HANDLING = "missing_error_handling"
    INSECURE_CODE = "insecure_code"
    UNCLEAR_RESPONSE = "unclear_response"


class Turn(BaseModel):
    turn_number: int
    user_input: str
    agent_response: str
    sentiment_before: Optional[float] = None
    sentiment_after: Optional[float] = None
    mistake_type: Optional[MistakeType] = None
    severity: Optional[int] = Field(None, ge=1, le=5)
    root_cause: Optional[str] = None
    rules_applied: List[str] = []
    timestamp: datetime = Field(default_factory=datetime.now)


class Conversation(BaseModel):
    conversation_id: str
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    turns: List[Turn] = []
    project_context: Optional[str] = None
    escalation_occurred: bool = False
    human_intervention: bool = False
    started_at: datetime = Field(default_factory=datetime.now)
    ended_at: Optional[datetime] = None

    def add_turn(self, turn: Turn) -> None:
        self.turns.append(turn)

    @property
    def is_complete(self) -> bool:
        return self.ended_at is not None

    def get_full_transcript(self) -> str:
        lines = []
        for turn in self.turns:
            lines.append(f"User: {turn.user_input}")
            lines.append(f"AI: {turn.agent_response}")
        return "\n".join(lines)
