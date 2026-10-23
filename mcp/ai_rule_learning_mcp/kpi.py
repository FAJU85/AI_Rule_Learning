"""Key performance indicators computed from local state (no network).

A snapshot of how well the tool is doing its job, derived entirely from the
local store, the detected agent configs, and the opt-in metrics log. Targets for
each KPI are documented in docs/KPIs.md; this module reports the current value.
"""

from __future__ import annotations

from typing import Any


def _avg(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def compute_kpis() -> dict[str, Any]:
    """Return a structured KPI snapshot computed from local data only."""
    from .injector import detected_targets
    from .metrics import build_metrics_payload, metrics_enabled
    from .store import (
        _download,
        find_rule_health_candidates,
        load_active_rules,
        suggest_duplicate_rules,
    )

    all_rules = _download("rules.jsonl")
    active = load_active_rules()

    pending = [
        r
        for r in all_rules
        if r.get("review_status") == "pending" or r.get("status") == "pending_review"
    ]

    # Rule corpus
    total = len(all_rules)
    active_count = len(active)
    pending_count = len(pending)

    # Deduplication: how many likely-duplicate pairs remain (lower is healthier).
    try:
        dup_pairs = len(suggest_duplicate_rules())
    except Exception:
        dup_pairs = 0

    # Health
    stale, needs_review = find_rule_health_candidates(all_rules)

    # Effectiveness over rules with real trigger history.
    scored = [
        float(r.get("effectiveness_score", 0.0) or 0.0)
        for r in all_rules
        if int(r.get("times_triggered", 0) or 0) > 0
    ]
    avg_effectiveness = round(_avg(scored), 3)

    # Injection coverage: of the agent configs detected on this machine, how many
    # currently carry the guardrail block.
    targets = detected_targets()
    injected = []
    for t in targets:
        try:
            if t.read_injected():
                injected.append(t.name)
        except Exception:
            pass
    detected_names = [t.name for t in targets]
    coverage = round(len(injected) / len(detected_names), 3) if detected_names else 0.0

    # Usage (only meaningful when the owner opted into metrics).
    metrics_on = metrics_enabled()
    outcomes = {"success": 0, "failure": 0}
    event_count = 0
    if metrics_on:
        payload = build_metrics_payload()
        event_count = payload.get("event_count", 0)
        outcomes = {
            "success": payload.get("outcomes", {}).get("success", 0),
            "failure": payload.get("outcomes", {}).get("failure", 0),
        }
    total_outcomes = outcomes["success"] + outcomes["failure"]
    success_rate = round(outcomes["success"] / total_outcomes, 3) if total_outcomes else None

    return {
        "rules": {
            "total": total,
            "active": active_count,
            "pending_review": pending_count,
        },
        "quality": {
            "duplicate_pairs": dup_pairs,
            "stale": len(stale),
            "needs_review": len(needs_review),
            "avg_effectiveness": avg_effectiveness,
        },
        "reach": {
            "agents_detected": detected_names,
            "agents_injected": injected,
            "injection_coverage": coverage,
        },
        "usage": {
            "metrics_enabled": metrics_on,
            "events": event_count,
            "success_rate": success_rate,
        },
    }


def format_kpis(kpis: dict[str, Any] | None = None) -> str:
    """Human-readable KPI summary for the CLI."""
    if kpis is None:
        kpis = compute_kpis()

    r = kpis["rules"]
    q = kpis["quality"]
    reach = kpis["reach"]
    u = kpis["usage"]

    lines = [
        "AI Rule Learning — KPI snapshot",
        "",
        "Rules",
        f"  total:            {r['total']}",
        f"  active:           {r['active']}",
        f"  pending review:   {r['pending_review']}",
        "",
        "Quality",
        f"  duplicate pairs:  {q['duplicate_pairs']}",
        f"  stale:            {q['stale']}",
        f"  needs review:     {q['needs_review']}",
        f"  avg effectiveness:{q['avg_effectiveness']:.3f}",
        "",
        "Reach",
        f"  agents detected:  {len(reach['agents_detected'])} ({', '.join(reach['agents_detected']) or 'none'})",
        f"  agents injected:  {len(reach['agents_injected'])} ({', '.join(reach['agents_injected']) or 'none'})",
        f"  injection coverage: {reach['injection_coverage']:.0%}",
        "",
        "Usage",
        f"  metrics enabled:  {u['metrics_enabled']}",
        f"  events logged:    {u['events']}",
        f"  success rate:     {('%.0f%%' % (u['success_rate'] * 100)) if u['success_rate'] is not None else 'n/a (enable metrics)'}",
    ]
    return "\n".join(lines)
