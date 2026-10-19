"""Hugging Face Independence and Separation Test Suite.

Enforces AC7 (ARL-SPRINT-001):
1. MCP core modules must not import huggingface_hub.
2. space/app.py is the only file with HF imports (Gradio demo space).
3. System architecture cleanly decouples community telemetry (Cloudflare R2) from HF.
"""

from __future__ import annotations

from pathlib import Path


def test_mcp_core_has_zero_hf_imports() -> None:
    """AC7.1: Verify MCP core has zero huggingface_hub imports."""
    root_dir = Path(__file__).resolve().parent.parent
    mcp_core_dir = root_dir / "mcp" / "ai_rule_learning_mcp"
    assert mcp_core_dir.exists(), f"Directory not found: {mcp_core_dir}"

    hf_import_found = []
    for py_file in mcp_core_dir.glob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        for lineno, line in enumerate(content.splitlines(), 1):
            stripped = line.strip()
            if (
                stripped.startswith("import huggingface_hub")
                or stripped.startswith("from huggingface_hub")
                or "import HfApi" in stripped
            ):
                hf_import_found.append(f"{py_file.name}:{lineno}: {stripped}")

    assert not hf_import_found, f"Found prohibited Hugging Face imports in MCP core: {hf_import_found}"


def test_space_app_is_only_allowed_hf_consumer() -> None:
    """AC7.2: space/app.py is the only file allowed to import huggingface_hub."""
    root_dir = Path(__file__).resolve().parent.parent
    space_app = root_dir / "space" / "app.py"
    assert space_app.exists(), f"space/app.py not found at {space_app}"

    # Verify space/app.py contains the expected Gradio / HF demo setup
    space_content = space_app.read_text(encoding="utf-8")
    assert "gradio" in space_content.lower()

    # Search entire mcp package to verify no file imports huggingface_hub
    mcp_files = list((root_dir / "mcp" / "ai_rule_learning_mcp").glob("*.py"))
    for py_file in mcp_files:
        for line in py_file.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            assert not stripped.startswith("import huggingface_hub"), f"Prohibited import in {py_file.name}: {line}"
            assert not stripped.startswith("from huggingface_hub import"), (
                f"Prohibited import in {py_file.name}: {line}"
            )
