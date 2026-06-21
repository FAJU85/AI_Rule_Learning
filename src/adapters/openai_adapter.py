"""OpenAI adapter — wraps the openai Python SDK."""

from __future__ import annotations

from config.settings import settings
from src.adapters.base_adapter import BaseAIAdapter
from src.utils.logger import get_logger

logger = get_logger(__name__)


class OpenAIAdapter(BaseAIAdapter):
    """Calls OpenAI chat completion API."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        self._api_key = api_key or settings.OPENAI_API_KEY
        self._model = model or settings.OPENAI_MODEL
        self._client = None  # lazy-loaded

    @property
    def name(self) -> str:
        return "openai"

    def _get_client(self):
        if self._client is None:
            try:
                import openai  # type: ignore

                self._client = openai.OpenAI(api_key=self._api_key)
            except Exception as exc:
                logger.error("Failed to initialise OpenAI client", extra={"error": str(exc)})
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
        messages = self._build_messages(user_input, system_prompt, conversation_history)

        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=self._model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            content = response.choices[0].message.content or ""
            logger.debug(
                "OpenAI response generated",
                extra={"model": self._model, "tokens": response.usage.total_tokens},
            )
            return content
        except Exception as exc:
            logger.error("OpenAI API error", extra={"error": str(exc)})
            raise

    def health_check(self) -> bool:
        try:
            client = self._get_client()
            models = client.models.list()
            return len(list(models)) > 0
        except Exception as exc:
            logger.warning("OpenAI health check failed", extra={"error": str(exc)})
            return False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_messages(
        user_input: str,
        system_prompt: str,
        conversation_history: str,
    ) -> list[dict]:
        messages: list[dict] = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # Re-hydrate previous turns from plain-text transcript
        if conversation_history:
            for line in conversation_history.strip().splitlines():
                if line.startswith("User: "):
                    messages.append({"role": "user", "content": line[len("User: ") :]})
                elif line.startswith("AI: "):
                    messages.append({"role": "assistant", "content": line[len("AI: ") :]})

        messages.append({"role": "user", "content": user_input})
        return messages
