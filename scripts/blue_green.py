#!/usr/bin/env python3
"""Blue-green deployment helpers for the Hugging Face Space release workflow.

The script is intentionally provider-light: GitHub Actions still uploads the
Space with huggingface_hub, while this helper decides the idle environment,
smoke-tests it, and calls an optional router webhook for cutover/rollback.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import asdict
from dataclasses import dataclass
from typing import Any
from urllib import error
from urllib import request

VALID_COLORS = {"blue", "green"}


@dataclass(frozen=True)
class DeploymentPlan:
    live_color: str
    idle_color: str
    live_space_id: str
    idle_space_id: str
    live_url: str
    idle_url: str
    health_path: str


def _normalise_color(value: str) -> str:
    color = value.strip().lower()
    if color not in VALID_COLORS:
        raise ValueError(f"color must be one of {sorted(VALID_COLORS)}")
    return color


def _space_url(space_id: str) -> str:
    """Return the public hf.space URL for an owner/name Space id."""
    if "/" not in space_id:
        raise ValueError("Space id must use owner/name format")
    owner, name = space_id.split("/", 1)
    slug = re.sub(r"[^a-z0-9-]+", "-", f"{owner}-{name}".lower()).strip("-")
    return f"https://{slug}.hf.space"


def build_plan(
    live_color: str | None = None,
    blue_space_id: str | None = None,
    green_space_id: str | None = None,
    health_path: str | None = None,
) -> DeploymentPlan:
    """Build the blue-green deployment plan from explicit args or environment."""
    live = _normalise_color(live_color or os.environ.get("BG_LIVE_COLOR", "blue"))
    idle = "green" if live == "blue" else "blue"
    blue = blue_space_id or os.environ.get("BG_BLUE_SPACE_ID", "vooom/AI_Rule_Learning")
    green = green_space_id or os.environ.get("BG_GREEN_SPACE_ID", "vooom/AI_Rule_Learning_Green")
    path = health_path or os.environ.get("BG_HEALTH_PATH", "/")
    if not path.startswith("/"):
        path = f"/{path}"
    spaces = {"blue": blue, "green": green}
    return DeploymentPlan(
        live_color=live,
        idle_color=idle,
        live_space_id=spaces[live],
        idle_space_id=spaces[idle],
        live_url=_space_url(spaces[live]),
        idle_url=_space_url(spaces[idle]),
        health_path=path,
    )


def smoke_check(base_url: str, health_path: str = "/", timeout_seconds: float = 30.0) -> dict[str, Any]:
    """Run a lightweight HTTP health/smoke check against an environment."""
    path = health_path if health_path.startswith("/") else f"/{health_path}"
    url = f"{base_url.rstrip('/')}{path}"
    try:
        with request.urlopen(url, timeout=timeout_seconds) as response:  # noqa: S310 - configured release URL
            status = int(response.status)
            ok = 200 <= status < 400
            return {"ok": ok, "status": status, "url": url}
    except error.HTTPError as exc:
        return {"ok": False, "status": exc.code, "url": url, "error": str(exc)}
    except error.URLError as exc:
        return {"ok": False, "status": None, "url": url, "error": str(exc.reason)}


def call_router_cutover(
    target_color: str,
    target_space_id: str,
    commit_sha: str | None = None,
    endpoint: str | None = None,
    token: str | None = None,
) -> dict[str, Any]:
    """Ask the external router/load balancer to switch production traffic."""
    color = _normalise_color(target_color)
    router_endpoint = endpoint or os.environ.get("BG_ROUTER_CUTOVER_URL")
    if not router_endpoint:
        raise RuntimeError("BG_ROUTER_CUTOVER_URL is required for traffic cutover")

    payload = {
        "active_color": color,
        "active_space_id": target_space_id,
        "commit_sha": commit_sha or os.environ.get("GITHUB_SHA", ""),
    }
    body = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    router_token = token or os.environ.get("BG_ROUTER_TOKEN")
    if router_token:
        headers["Authorization"] = f"Bearer {router_token}"

    req = request.Request(router_endpoint, data=body, headers=headers, method="POST")
    with request.urlopen(req, timeout=30) as response:  # noqa: S310 - configured router endpoint
        response_body = response.read().decode("utf-8")
        return {"status": int(response.status), "body": response_body, "request": payload}


def _print_json(data: Any, output_field: str | None = None) -> None:
    if output_field:
        if not isinstance(data, dict):
            raise ValueError("--output-field requires an object result")
        print(data[output_field])
    else:
        print(json.dumps(data, indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Blue-green deployment helper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan_parser = subparsers.add_parser("plan", help="Print live/idle environment mapping")
    plan_parser.add_argument("--live-color")
    plan_parser.add_argument("--output-field")

    smoke_parser = subparsers.add_parser("smoke", help="Smoke-test an environment URL")
    smoke_parser.add_argument("--url")
    smoke_parser.add_argument("--color", choices=sorted(VALID_COLORS))
    smoke_parser.add_argument("--timeout", type=float, default=float(os.environ.get("BG_SMOKE_TIMEOUT_SECONDS", "30")))

    cutover_parser = subparsers.add_parser("cutover", help="Switch traffic to a target color")
    cutover_parser.add_argument("--target-color", required=True, choices=sorted(VALID_COLORS))
    cutover_parser.add_argument("--commit-sha")

    rollback_parser = subparsers.add_parser("rollback", help="Switch traffic back to the previous color")
    rollback_parser.add_argument("--previous-color", required=True, choices=sorted(VALID_COLORS))
    rollback_parser.add_argument("--commit-sha")

    args = parser.parse_args(argv)
    plan = build_plan(getattr(args, "live_color", None))

    if args.command == "plan":
        _print_json(asdict(plan), args.output_field)
        return 0

    if args.command == "smoke":
        url = args.url
        if not url and args.color:
            url = plan.live_url if args.color == plan.live_color else plan.idle_url
        if not url:
            url = plan.idle_url
        result = smoke_check(url, plan.health_path, args.timeout)
        _print_json(result)
        return 0 if result["ok"] else 1

    if args.command == "cutover":
        target_space_id = plan.live_space_id if args.target_color == plan.live_color else plan.idle_space_id
        _print_json(call_router_cutover(args.target_color, target_space_id, args.commit_sha))
        return 0

    if args.command == "rollback":
        target_space_id = plan.live_space_id if args.previous_color == plan.live_color else plan.idle_space_id
        _print_json(call_router_cutover(args.previous_color, target_space_id, args.commit_sha))
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
