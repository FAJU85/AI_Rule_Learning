"""Privacy-preserving metrics tests."""

from __future__ import annotations

import json

import pytest


@pytest.fixture()
def metrics_store(tmp_path, monkeypatch):
    d = tmp_path / "store"
    d.mkdir()
    monkeypatch.setattr("ai_rule_learning_mcp.store.LOCAL_DIR", d)
    monkeypatch.delenv("ARL_METRICS", raising=False)
    monkeypatch.delenv("ARL_METRICS_ENDPOINT", raising=False)
    return d


def test_metrics_disabled_by_default(metrics_store):
    from ai_rule_learning_mcp.metrics import metrics_enabled, record_metric_event
    from ai_rule_learning_mcp.store import _local_load

    assert metrics_enabled() is False
    assert record_metric_event("cli_command", metadata={"command": "sync"}) is None
    assert _local_load("metrics.jsonl") == []


def test_metrics_enable_records_only_safe_labels(metrics_store):
    from ai_rule_learning_mcp.metrics import build_metrics_payload, record_metric_event, set_metrics_enabled
    from ai_rule_learning_mcp.store import _local_load

    set_metrics_enabled(True)
    record_metric_event(
        "cli_command",
        metadata={
            "command": "memory:add",
            "path": "/Users/alice/private/project",
            "content": "Always use my private email alice@example.com",
        },
    )

    rows = _local_load("metrics.jsonl")
    assert len(rows) == 1
    row = rows[0]
    assert row["event"] == "cli_command"
    assert row["command"] == "memory:add"
    assert "path" not in row
    assert "content" not in row
    assert "alice" not in json.dumps(row).lower()

    payload = build_metrics_payload()
    rendered = json.dumps(payload).lower()
    assert payload["event_count"] == 1
    assert payload["commands"] == {"memory:add": 1}
    assert "alice" not in rendered
    assert "/users" not in rendered


def test_metrics_env_var_can_disable_local_opt_in(metrics_store, monkeypatch):
    from ai_rule_learning_mcp.metrics import metrics_enabled, set_metrics_enabled

    set_metrics_enabled(True)
    assert metrics_enabled() is True

    monkeypatch.setenv("ARL_METRICS", "false")
    assert metrics_enabled() is False


def test_metrics_cli_preview_does_not_enable_metrics(metrics_store, capsys):
    from ai_rule_learning_mcp.cli import cmd_metrics
    from ai_rule_learning_mcp.metrics import metrics_enabled

    cmd_metrics(["preview"])

    out = capsys.readouterr().out
    assert '"metrics_enabled": false' in out
    assert metrics_enabled() is False


def test_metrics_cli_enable_disable(metrics_store, capsys):
    from ai_rule_learning_mcp.cli import cmd_metrics
    from ai_rule_learning_mcp.metrics import metrics_enabled

    cmd_metrics(["enable"])
    assert metrics_enabled() is True
    assert "enabled" in capsys.readouterr().out

    cmd_metrics(["disable"])
    assert metrics_enabled() is False
    assert "disabled" in capsys.readouterr().out


def test_metrics_status_reports_source_counts_path_and_endpoint(metrics_store, monkeypatch):
    from ai_rule_learning_mcp.metrics import metrics_status, record_metric_event, set_metrics_enabled

    monkeypatch.setenv("ARL_METRICS_ENDPOINT", "https://metrics.example.test/ingest")
    set_metrics_enabled(True)
    record_metric_event("cli_command", metadata={"command": "status"})

    status = metrics_status()

    assert status["enabled"] is True
    assert status["source"] == "local_settings"
    assert status["event_count"] == 1
    assert status["events_path"].endswith("metrics.jsonl")
    assert status["endpoint_configured"] is True

    monkeypatch.setenv("ARL_METRICS", "false")
    status = metrics_status()
    assert status["enabled"] is False
    assert status["source"] == "environment"
