"""Smoke tests for the Hugging Face Space entrypoint."""

import importlib.util
from pathlib import Path


def _load_space_app():
    app_path = Path(__file__).with_name("app.py")
    spec = importlib.util.spec_from_file_location("space_app_smoke", app_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_space_app_imports_from_repo_root():
    module = _load_space_app()

    assert hasattr(module, "demo")
    assert module.SPACE_DIR == Path(__file__).parent.resolve()


def test_landing_hero_renders_runtime_status():
    module = _load_space_app()

    hero = module.build_landing_hero()

    assert "arl-hero" in hero
    assert "Import Sessions" in hero
    assert "MCP package" in hero
