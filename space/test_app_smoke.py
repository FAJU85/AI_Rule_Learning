"""Smoke tests for the Hugging Face Space entrypoint."""

import importlib
import importlib.util
from pathlib import Path
from types import SimpleNamespace


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


def test_space_app_falls_back_when_installed_store_lacks_shared_helpers(monkeypatch):
    real_find_spec = importlib.util.find_spec
    real_import_module = importlib.import_module

    def fake_find_spec(name, *args, **kwargs):
        if name == "ai_rule_learning_mcp.store":
            return SimpleNamespace()
        return real_find_spec(name, *args, **kwargs)

    def fake_import_module(name, package=None):
        if name == "ai_rule_learning_mcp.store":
            return SimpleNamespace()
        return real_import_module(name, package)

    monkeypatch.setattr(importlib.util, "find_spec", fake_find_spec)
    monkeypatch.setattr(importlib, "import_module", fake_import_module)

    module = _load_space_app()

    assert module.find_rule_health_candidates is module._fallback_rule_health_candidates
    assert module.suggest_duplicate_rules_from_records is module._fallback_duplicate_rules_from_records


def test_space_app_does_not_import_installed_store_helpers(monkeypatch):
    real_import_module = importlib.import_module

    def fail_import_module(name, package=None):
        if name == "ai_rule_learning_mcp.store":
            raise AssertionError("Space startup must not import installed store helpers")
        return real_import_module(name, package)

    monkeypatch.setattr(importlib, "import_module", fail_import_module)

    module = _load_space_app()

    assert module.find_rule_health_candidates is module._fallback_rule_health_candidates
    assert module.suggest_duplicate_rules_from_records is module._fallback_duplicate_rules_from_records
    assert module._store_helper_import_error is None
