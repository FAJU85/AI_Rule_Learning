"""Regression test for default install and MCP version ceiling (ARL-REM-2026-006).

Asserts:
1. Resolved mcp version is 1.x (mcp>=1.0.0,<2.0.0).
2. Server process starts cleanly and remains alive for at least 2 seconds.
3. No AttributeError or ImportError in stderr.
4. get_guardrail_rules() succeeds on default path without custom env vars.
"""

from __future__ import annotations

import asyncio
import json
import sys
import tomllib
from pathlib import Path

import pytest
from ai_rule_learning_mcp import server


def test_dependency_ceiling_declared_in_pyproject() -> None:
    """Assert pyproject.toml explicitly specifies the strict upper bound ceiling."""
    pyproject_path = Path("mcp/pyproject.toml")
    assert pyproject_path.exists(), "mcp/pyproject.toml must exist"

    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)

    deps = data.get("project", {}).get("dependencies", [])
    mcp_dep = next((d for d in deps if d.startswith("mcp")), None)

    assert mcp_dep is not None, "mcp dependency must be declared"
    assert "<2" in mcp_dep or "<2.0.0" in mcp_dep, (
        f"mcp dependency must have strict upper bound <2.0.0, found: {mcp_dep}"
    )
    assert ">=1.0.0" in mcp_dep, f"mcp dependency must have floor >=1.0.0, found: {mcp_dep}"


def test_resolved_mcp_version_is_v1() -> None:
    """Assert that the currently resolved mcp package in the environment is 1.x."""

    # Determine installed version via importlib.metadata
    from importlib.metadata import version

    installed_version = version("mcp")
    assert installed_version.startswith("1."), f"Resolved mcp version must be 1.x, got: {installed_version}"


@pytest.mark.asyncio
async def test_server_process_survives_startup_without_import_errors(tmp_path: Path) -> None:
    """Assert server starts, stays alive >=2s, and produces no AttributeError/ImportError in stderr."""
    cmd = [sys.executable, "-m", "ai_rule_learning_mcp.server"]

    # Start server subprocess with stdio piping
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(Path.cwd()),
    )

    # Let the server initialize and run for 2.2 seconds
    await asyncio.sleep(2.2)

    # Check process is still alive
    is_alive = proc.returncode is None
    assert is_alive, f"Server process died prematurely with returncode {proc.returncode}"

    # Terminate gracefully
    proc.terminate()
    stdout_bytes, stderr_bytes = await proc.communicate()

    stderr_text = stderr_bytes.decode("utf-8", errors="replace")
    assert "AttributeError" not in stderr_text, f"AttributeError detected in stderr: {stderr_text}"
    assert "ImportError" not in stderr_text, f"ImportError detected in stderr: {stderr_text}"
    assert "'Server' object has no attribute 'list_tools'" not in stderr_text


@pytest.mark.asyncio
async def test_default_path_get_guardrail_rules_produces_active_rules(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Assert get_guardrail_rules succeeds on default path without custom env vars."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.delenv("ARL_CONTRIBUTE", raising=False)
    monkeypatch.delenv("ARL_SESSIONS", raising=False)

    # Execute get_guardrail_rules
    result = await server._get_guardrail_rules(dry_run=False)
    assert result, "get_guardrail_rules must return non-empty result"

    # Verify active_rules.json was produced
    active_rules_file = Path("active_rules.json")
    assert active_rules_file.exists(), "active_rules.json must be written by default path"

    data = json.loads(active_rules_file.read_text(encoding="utf-8"))
    assert 1 <= data["rules_count"] <= 10, f"Expected 1..10 rules, got {data['rules_count']}"
    assert data["token_count"] <= data["budget_tokens"], "Token count must be within budget"
