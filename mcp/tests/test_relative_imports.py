"""Regression guard for ARL live-tool import failures.

`get_guardrail_rules` and `why` previously used absolute self-imports
(`from ai_rule_learning_mcp.catalog import ...`) that resolved fine under
pytest but raised ``ModuleNotFoundError: No module named
'ai_rule_learning_mcp.catalog'`` in the installed server runtime, breaking
both tools. Every other import in the package is relative; these must be too.

This test fails before the fix (two absolute imports present) and passes
after (all intra-package imports relative).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

PACKAGE_DIR = Path(__file__).resolve().parent.parent / "ai_rule_learning_mcp"
PACKAGE_NAME = "ai_rule_learning_mcp"


def _python_modules() -> list[Path]:
    return sorted(PACKAGE_DIR.glob("*.py"))


@pytest.mark.parametrize("module_path", _python_modules(), ids=lambda p: p.name)
def test_no_absolute_self_imports(module_path: Path) -> None:
    """Intra-package imports must be relative so they survive any launch context."""
    tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))
    offenders: list[str] = []
    for node in ast.walk(tree):
        # `from ai_rule_learning_mcp.x import y` (level 0 == absolute)
        if isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module and node.module.split(".")[0] == PACKAGE_NAME:
                offenders.append(f"line {node.lineno}: from {node.module} import ...")
        # `import ai_rule_learning_mcp.x`
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] == PACKAGE_NAME:
                    offenders.append(f"line {node.lineno}: import {alias.name}")

    assert not offenders, (
        f"{module_path.name} uses absolute self-imports (use relative imports instead): "
        + "; ".join(offenders)
    )
