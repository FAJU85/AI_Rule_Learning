"""Wheel verification gate asserting built package contains absolute path (ARL-BUG-004).

Verifies Acceptance Criteria:
- AC1: Wheel contains absolute path definition in catalog.py.
- AC3: Wheel inspection verifies Path.home / expanduser presence.
"""

from __future__ import annotations

import glob
import zipfile
from pathlib import Path

import pytest


def test_built_wheel_contains_absolute_active_rules_path() -> None:
    """Assert that any built wheel in mcp/dist/ contains Path.home in _ACTIVE_RULES_PATH."""
    wheels = glob.glob("mcp/dist/*.whl")
    if not wheels:
        pytest.skip("No wheel in mcp/dist/ to inspect (run after python -m build mcp/)")

    latest_wheel = max(wheels, key=lambda w: Path(w).stat().st_mtime)
    with zipfile.ZipFile(latest_wheel, "r") as z:
        catalog_src = z.read("ai_rule_learning_mcp/catalog.py").decode("utf-8")
        assert "Path.home" in catalog_src or "expanduser" in catalog_src

        matching_lines = [line.strip() for line in catalog_src.splitlines() if line.startswith("_ACTIVE_RULES_PATH =")]
        assert len(matching_lines) >= 1, "Expected _ACTIVE_RULES_PATH constant in catalog.py"
        assert "Path.home" in matching_lines[0] or "expanduser" in matching_lines[0]
        assert 'Path("active_rules.json")' not in matching_lines[0]
