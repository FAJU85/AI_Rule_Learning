"""Abstract base class for AI provider adapters."""
from __future__ import annotations

from abc import ABC
from abc import abstractmethod
from typing import List
from typing import Optional


class BaseAIAdapter(ABC):
    """Common interface that all AI provider adapters must implement."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name of the provider (e.g. 'openai', 'claude')."""
        ...

    @abstractmethod
    def generate_response(
        self,
        user_input: str,
        system_prompt: str = "",
        conversation_history: str = "",
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> str:
        """Generate a response to *user_input*.

        Parameters
        ----------
        user_input:
            The latest message from the user.
        system_prompt:
            Optional system / instruction prompt (may contain injected rules).
        conversation_history:
            Plain-text transcript of the conversation so far (User:/AI: format).
        max_tokens:
            Maximum number of tokens to generate.
        temperature:
            Sampling temperature.

        Returns
        -------
        str
            The generated response text.
        """
        ...

    @abstractmethod
    def health_check(self) -> bool:
        """Return True if the provider is reachable and the API key is valid."""
        ...
