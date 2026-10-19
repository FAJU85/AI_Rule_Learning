"""Dependency pinning test suite (AC7 / ARL-MAINT-002).

Validates that all critical dependencies in pyproject.toml carry upper bounds
to prevent breaking changes and silent major version upgrades.
"""

from pathlib import Path
import tomllib


def test_dependency_upper_bounds_present():
    pyproject_path = Path("mcp/pyproject.toml")
    assert pyproject_path.exists(), "mcp/pyproject.toml must exist"

    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)

    deps = data.get("project", {}).get("dependencies", [])
    assert len(deps) >= 4, f"Expected at least 4 dependencies, got {len(deps)}"

    required_pinned_packages = ["mcp", "pydantic", "anyio", "huggingface-hub"]

    for pkg in required_pinned_packages:
        matching = [d for d in deps if d.startswith(pkg)]
        assert matching, f"Dependency '{pkg}' not found in dependencies list"
        dep_str = matching[0]
        assert "<" in dep_str, f"Dependency '{dep_str}' is missing an upper bound '<'"


def test_mcp_ceiling_bounded():
    pyproject_path = Path("mcp/pyproject.toml")
    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)

    deps = data.get("project", {}).get("dependencies", [])
    mcp_dep = [d for d in deps if d.startswith("mcp")][0]
    assert "<2.0.0" in mcp_dep, f"mcp dependency must be pinned <2.0.0, got {mcp_dep}"
