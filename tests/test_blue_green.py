from __future__ import annotations

import json
from urllib import error

import pytest

from scripts import blue_green


def test_build_plan_defaults_to_green_idle(monkeypatch):
    monkeypatch.setenv("BG_BLUE_SPACE_ID", "owner/app-blue")
    monkeypatch.setenv("BG_GREEN_SPACE_ID", "owner/app-green")
    monkeypatch.setenv("BG_LIVE_COLOR", "blue")
    monkeypatch.setenv("BG_HEALTH_PATH", "healthz")

    plan = blue_green.build_plan()

    assert plan.live_color == "blue"
    assert plan.idle_color == "green"
    assert plan.live_space_id == "owner/app-blue"
    assert plan.idle_space_id == "owner/app-green"
    assert plan.health_path == "/healthz"
    assert plan.idle_url == "https://owner-app-green.hf.space"


def test_build_plan_rejects_invalid_color():
    with pytest.raises(ValueError, match="color must"):
        blue_green.build_plan(live_color="purple")


def test_smoke_check_reports_success(monkeypatch):
    class Response:
        status = 204

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(blue_green.request, "urlopen", lambda url, timeout: Response())

    assert blue_green.smoke_check("https://example.test", "/health") == {
        "ok": True,
        "status": 204,
        "url": "https://example.test/health",
    }


def test_smoke_check_reports_http_failure(monkeypatch):
    def fail(_url, timeout):
        raise error.HTTPError("https://example.test/health", 503, "unavailable", hdrs=None, fp=None)

    monkeypatch.setattr(blue_green.request, "urlopen", fail)

    result = blue_green.smoke_check("https://example.test", "/health")
    assert result["ok"] is False
    assert result["status"] == 503


def test_call_router_cutover_posts_expected_payload(monkeypatch):
    captured = {}

    class Response:
        status = 202

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return b'{"accepted": true}'

    def fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        captured["headers"] = dict(req.header_items())
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return Response()

    monkeypatch.setattr(blue_green.request, "urlopen", fake_urlopen)

    result = blue_green.call_router_cutover(
        "green",
        "owner/app-green",
        commit_sha="abc123",
        endpoint="https://router.example.test/cutover",
        token="secret-token",
    )

    assert result["status"] == 202
    assert captured["url"] == "https://router.example.test/cutover"
    assert captured["headers"]["Authorization"] == "Bearer secret-token"
    assert captured["body"] == {
        "active_color": "green",
        "active_space_id": "owner/app-green",
        "commit_sha": "abc123",
    }
