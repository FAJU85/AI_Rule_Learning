"""AI Rule Learning MCP server."""

from __future__ import annotations

from typing import Any

__version__ = "0.2.0"


def __getattr__(name: str) -> Any:
    if name in ("scrub_pii", "redact_pii", "anonymize_pii", "strip_pii", "redact", "anonymize"):
        from .store import scrub_pii

        return scrub_pii
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
