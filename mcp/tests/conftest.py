"""Shared MCP test fixtures and dependency fallbacks."""

from __future__ import annotations

import sys
import types
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

import pytest


@pytest.fixture(autouse=True)
def _isolate_remote_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep tests hermetic — never touch a developer's real remote backends."""
    for var in (
        "R2_BUCKET",
        "R2_ACCESS_KEY_ID",
        "R2_SECRET_ACCESS_KEY",
        "R2_ACCOUNT_ID",
        "R2_ENDPOINT",
        "R2_PREFIX",
        "CLOUDFLARE_ACCOUNT_ID",
        "ARL_DATASET",
        "HF_TOKEN",
    ):
        monkeypatch.delenv(var, raising=False)


try:  # pragma: no cover - used only when the real MCP SDK is installed
    import mcp.server  # noqa: F401
    import mcp.types  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover - local test environment fallback
    mcp_pkg = sys.modules.setdefault("mcp", types.ModuleType("mcp"))

    server_mod = types.ModuleType("mcp.server")
    stdio_mod = types.ModuleType("mcp.server.stdio")
    types_mod = types.ModuleType("mcp.types")

    class Server:
        """Tiny MCP Server stand-in for unit tests that call handlers directly."""

        def __init__(self, name: str) -> None:
            self.name = name

        def list_tools(self):
            def decorator(func):
                self._list_tools = func
                return func

            return decorator

        def call_tool(self):
            def decorator(func):
                self._call_tool = func
                return func

            return decorator

        async def run(self, *args: Any, **kwargs: Any) -> None:
            return None

        def create_initialization_options(self) -> dict[str, Any]:
            return {}

    @asynccontextmanager
    async def stdio_server():
        yield None, None

    @dataclass
    class Tool:
        name: str
        description: str
        inputSchema: dict[str, Any]

    @dataclass
    class TextContent:
        type: str
        text: str

    server_mod.Server = Server
    stdio_mod.stdio_server = stdio_server
    types_mod.Tool = Tool
    types_mod.TextContent = TextContent

    setattr(mcp_pkg, "server", server_mod)
    setattr(server_mod, "stdio", stdio_mod)
    setattr(mcp_pkg, "types", types_mod)
    sys.modules["mcp.server"] = server_mod
    sys.modules["mcp.server.stdio"] = stdio_mod
    sys.modules["mcp.types"] = types_mod


# Hugging Face has been fully removed; the community layer talks only to the
# R2-backed Workers over HTTP, so no huggingface_hub stub is registered here.
