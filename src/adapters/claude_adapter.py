"""Anthropic / Claude adapter — wraps the anthropic Python SDK."""
from __future__ import annotations

from typing import List
from typing import Optional

from config.settings import settings
from src.adapters.base_adapter import BaseAIAdapter
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ClaudeAdapter(BaseAIAdapter):
    """Calls Anthropic Messages API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        self._api_key = api_key or settings.ANTHROPIC_API_KEY
        self._model = model or settings.ANTHROPIC_MODEL
        self._client = None  # lazy-loaded

    @property
    def name(self) -> str:
        return "claude"

    def _get_client(self):
        if self._client is None:
            try:
                import anthropic  # type: ignore

                self._client = anthropic.Anthropic(api_key=self._api_key)
            except Exception as exc:
                logger.error("Failed to initialise Anthropic client", extra={"error": str(exc)})
                raise
        return self._client

    def generate_response(
        self,
        user_input: str,
        system_prompt: str = "",
        conversation_history: str = "",
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> str:
        messages = self._build_messages(user_input, conversation_history)

        kwargs = {
            "model": self._model,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if system_prompt:
            kwargs["system"] = system_prompt

        try:
            client = self._get_client()
            response = client.messages.create(**kwargs)
            content = response.content[0].text if response.content else ""
            logger.debug(
                "Claude response generated",
                extra={
                    "model": self._model,
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                },
            )
            return content
        except Exception as exc:
            logger.error("Anthropic API error", extra={"error": str(exc)})
            raise

    def health_check(self) -> bool:
        try:
            client = self._get_client()
            # A minimal call to verify credentials
            client.messages.create(
                model=self._model,
                max_tokens=10,
                messages=[{"role": "user", "content": "ping"}],
            )
            return True
        except Exception as exc:
            logger.warning("Claude health check failed", extra={"error": str(exc)})
            return False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_messages(user_input: str, conversation_history: str) -> List[dict]:
        """Convert plain-text history to Anthropic messages format."""
        messages: List[dict] = []

        if conversation_history:
            for line in conversation_history.strip().splitlines():
                if line.startswith("User: "):
                    messages.append({"role": "user", "content": line[len("User: "):]})
                elif line.startswith("AI: "):
                    messages.append({"role": "assistant", "content": line[len("AI: "):]})

        messages.append({"role": "user", "content": user_input})
        return messages
