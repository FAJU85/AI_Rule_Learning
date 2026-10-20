"""Regression guard for the stdio JSON-RPC tool-error path.

`call_tool` returns a ``(content, isError)`` tuple for error results. The stdio
`_handle_jsonrpc_message` path previously iterated that result directly, so an
error tuple made it call ``.model_dump()`` on the bool and crash the request
loop. This verifies error tuples are unpacked and surfaced as ``isError``.
"""

from __future__ import annotations

import json

from ai_rule_learning_mcp import server


def _call(name: str, arguments: dict | None = None) -> dict:
    line = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments or {}},
        }
    )
    resp = server._handle_jsonrpc_message(line)
    assert resp is not None
    return resp


def test_stdio_unknown_tool_sets_is_error() -> None:
    resp = _call("unknown_bogus_tool")
    result = resp["result"]
    assert result["isError"] is True
    assert isinstance(result["content"], list) and result["content"]
    # content items must be serialisable dicts (not a leaked bool from the tuple)
    assert all(isinstance(c, dict) for c in result["content"])


def test_stdio_successful_tool_is_not_error() -> None:
    resp = _call("list_providers")
    result = resp["result"]
    assert result["isError"] is False
    assert isinstance(result["content"], list) and result["content"]
