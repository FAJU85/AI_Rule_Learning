"""Gradio dashboard for the AI Rule Learning System."""

import csv
import io
import json
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# PII scrubbing helpers
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", re.IGNORECASE)
_HOME_RE = re.compile(r"(?:/home/[^/\s]+|/Users/[^/\s]+|C:\\Users\\[^\\\s]+)", re.IGNORECASE)
_IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_PHONE_RE = re.compile(r"\b(?:\+?\d[\d\s\-().]{7,}\d)\b")
_TOKEN_RE = re.compile(r"\b(hf_|sk-|ghp_|gho_|ghs_|github_pat_)[A-Za-z0-9_\-]{10,}\b")


def _scrub_pii(text: str) -> str:
    """Replace common PII patterns with safe placeholders."""
    text = _EMAIL_RE.sub("[EMAIL]", text)
    text = _HOME_RE.sub("[HOME]", text)
    text = _IP_RE.sub("[IP]", text)
    text = _PHONE_RE.sub("[PHONE]", text)
    text = _TOKEN_RE.sub("[TOKEN]", text)
    return text


def _sanitize_path(cwd: str) -> str:
    """Return only the project-relative path, stripping the home prefix."""
    if not cwd:
        return ""
    try:
        return str(Path(cwd).relative_to(Path.home()))
    except ValueError:
        return _HOME_RE.sub("[HOME]", cwd)

import gradio as gr
import pandas as pd
import plotly.graph_objects as go
from huggingface_hub import HfApi, hf_hub_download
from huggingface_hub.errors import EntryNotFoundError, RepositoryNotFoundError

# ---------------------------------------------------------------------------
# HF dataset connection
# ---------------------------------------------------------------------------

DATASET_ID = "vooom/AI_Rule_Learning"
COMMUNITY_DATASET_ID = "vooom/AI_Rule_Learning_Community"
HF_TOKEN = os.environ.get("HF_TOKEN")


def _download_jsonl(filename: str) -> list[dict]:
    try:
        path = hf_hub_download(
            repo_id=DATASET_ID,
            filename=filename,
            repo_type="dataset",
            token=HF_TOKEN,
            force_download=True,
        )
        records = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        return records
    except (EntryNotFoundError, RepositoryNotFoundError):
        return []
    except Exception:
        return []


def _upload_jsonl(filename: str, records: list[dict]) -> None:
    api = HfApi(token=HF_TOKEN)
    content = "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n"
    api.upload_file(
        path_or_fileobj=content.encode("utf-8"),
        path_in_repo=filename,
        repo_id=DATASET_ID,
        repo_type="dataset",
        commit_message=f"Update {filename} via Space UI",
    )


def load_conversations() -> list[dict]:
    return _download_jsonl("conversations.jsonl")


def load_rules() -> list[dict]:
    return _download_jsonl("rules.jsonl")


def load_rejected_rules() -> list[dict]:
    return _download_jsonl("rejected_rules.jsonl")


def load_rule_versions() -> list[dict]:
    return _download_jsonl("rule_versions.jsonl")


def _append_jsonl(filename: str, records: list[dict]) -> None:
    """Append records to a JSONL file in the dataset (load → merge → upload)."""
    existing = _download_jsonl(filename)
    _upload_jsonl(filename, existing + records)


def _snapshot_rule_version(rule: dict, event: str) -> None:
    """Save a timestamped snapshot of a rule's current state to rule_versions.jsonl."""
    snapshot = {
        "rule_id": rule.get("rule_id"),
        "name": rule.get("name"),
        "event": event,
        "timestamp": datetime.utcnow().isoformat(),
        "is_active": rule.get("is_active"),
        "effectiveness_score": rule.get("effectiveness_score"),
        "times_triggered": rule.get("times_triggered", 0),
        "success_count": rule.get("success_count", 0),
        "failure_count": rule.get("failure_count", 0),
        "instruction": (rule.get("action") or {}).get("instruction", ""),
        "keywords": (rule.get("trigger") or {}).get("keywords", []),
        "priority": rule.get("priority"),
    }
    try:
        _append_jsonl("rule_versions.jsonl", [snapshot])
    except Exception:
        pass


def _save_to_rejected_memory(rule: dict, reason: str) -> None:
    """Persist a failed rule to rejected_rules.jsonl so it is never recreated."""
    entry = {
        "rule_id": rule.get("rule_id"),
        "name": rule.get("name", ""),
        "description": rule.get("description", ""),
        "keywords": (rule.get("trigger") or {}).get("keywords", []),
        "instruction": (rule.get("action") or {}).get("instruction", ""),
        "reason": reason,
        "rejected_at": datetime.utcnow().isoformat(),
    }
    try:
        _append_jsonl("rejected_rules.jsonl", [entry])
    except Exception:
        pass


def _is_too_similar_to_rejected(new_rule: dict, rejected: list[dict], threshold: float = 0.55) -> str | None:
    """Return the name of the matching rejected rule if the new rule is too similar, else None."""
    new_kws = set(kw.lower() for kw in (new_rule.get("trigger") or {}).get("keywords", []))
    new_instruction = (new_rule.get("action") or {}).get("instruction", "").lower()
    for r in rejected:
        old_kws = set(kw.lower() for kw in r.get("keywords", []))
        if new_kws and old_kws:
            overlap = len(new_kws & old_kws) / max(len(new_kws | old_kws), 1)
            if overlap >= threshold:
                return r.get("name", r.get("rule_id", "?"))
        # Also match on instruction text similarity (word overlap)
        old_instruction = r.get("instruction", "").lower()
        if new_instruction and old_instruction:
            new_words = set(new_instruction.split())
            old_words = set(old_instruction.split())
            word_overlap = len(new_words & old_words) / max(len(new_words | old_words), 1)
            if word_overlap >= threshold:
                return r.get("name", r.get("rule_id", "?"))
    return None


# ---------------------------------------------------------------------------
# Tab 1 — Overview
# ---------------------------------------------------------------------------

def build_overview() -> tuple[Any, Any, str]:
    rules = load_rules()
    conversations = load_conversations()

    if not rules and not conversations:
        empty_fig = go.Figure()
        empty_fig.update_layout(
            title="No data yet — upload conversations to get started",
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            height=350,
        )
        summary = "### No data yet\n\nUpload conversation history in the **Upload History** tab to populate this dashboard."
        return empty_fig, empty_fig, summary

    active_rules = [r for r in rules if r.get("is_active")]
    total_triggers = sum(r.get("times_triggered", 0) for r in active_rules)
    avg_eff = (
        sum(r.get("effectiveness_score", 0) for r in active_rules) / max(len(active_rules), 1)
    )

    # Effectiveness bar chart
    fig_eff = go.Figure(
        go.Bar(
            x=[r.get("name", r.get("rule_id", "?"))[:30] for r in rules],
            y=[r.get("effectiveness_score", 0) for r in rules],
            marker_color=["#22c55e" if r.get("is_active") else "#94a3b8" for r in rules],
            text=[f"{r.get('effectiveness_score', 0):.0%}" for r in rules],
            textposition="outside",
        )
    )
    fig_eff.update_layout(
        title="Rule Effectiveness Scores",
        yaxis_title="Effectiveness",
        yaxis_range=[0, 1.1],
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        height=350,
    )

    # Gap distribution from conversations
    gap_counts: dict[str, int] = {}
    for conv in conversations:
        for turn in conv.get("turns", []):
            for gap in turn.get("gaps_detected", []):
                gtype = gap.get("type", "unknown") if isinstance(gap, dict) else str(gap)
                gap_counts[gtype] = gap_counts.get(gtype, 0) + 1

    if gap_counts:
        fig_gaps = go.Figure(
            go.Pie(
                labels=[k.replace("_", " ").title() for k in gap_counts],
                values=list(gap_counts.values()),
                hole=0.4,
            )
        )
    else:
        fig_gaps = go.Figure(go.Pie(labels=["No gaps detected"], values=[1], hole=0.4))

    fig_gaps.update_layout(
        title="Gap Distribution",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        height=350,
    )

    total_gaps = sum(gap_counts.values())
    summary = f"""
### System Summary

| Metric | Value |
|--------|-------|
| Active rules | {len(active_rules)} / {len(rules)} |
| Total rule triggers | {total_triggers} |
| Average effectiveness | {avg_eff:.0%} |
| Conversations analysed | {len(conversations)} |
| Gaps detected (all time) | {total_gaps} |
"""
    return fig_eff, fig_gaps, summary


# ---------------------------------------------------------------------------
# Tab 2 — Rules
# ---------------------------------------------------------------------------

def build_rules_table() -> pd.DataFrame:
    rules = load_rules()
    if not rules:
        return pd.DataFrame(
            columns=["Status", "Name", "Type", "Priority", "Triggered", "Effectiveness", "Action", "Created"]
        )
    rows = []
    for r in rules:
        rows.append(
            {
                "Status": "✅ Active" if r.get("is_active") else "⛔ Inactive",
                "Name": r.get("name", r.get("rule_id", "?")),
                "Type": r.get("rule_type", "?").upper(),
                "Priority": "⭐" * int(r.get("priority", 0)),
                "Triggered": r.get("times_triggered", 0),
                "Effectiveness": f"{r.get('effectiveness_score', 0):.0%}",
                "Action": (r.get("action", {}) or {}).get("type", "?").replace("_", " ").title()
                if isinstance(r.get("action"), dict)
                else str(r.get("action", "?")),
                "Created": str(r.get("created_at", ""))[:10],
            }
        )
    return pd.DataFrame(rows)


def get_rule_names() -> list[str]:
    rules = load_rules()
    return [r.get("name", r.get("rule_id", "?")) for r in rules]


def get_rule_detail(rule_name: str) -> str:
    if not rule_name:
        return "Select a rule from the table above."
    rules = load_rules()
    rule = next(
        (r for r in rules if r.get("name") == rule_name or r.get("rule_id") == rule_name), None
    )
    if not rule:
        return "Rule not found."
    triggered = rule.get("times_triggered", 0)
    success = rule.get("success_count", 0)
    success_rate = success / max(triggered, 1)
    action = rule.get("action", {})
    trigger = rule.get("trigger", {})
    return f"""
**{rule.get('name', rule.get('rule_id', '?'))}**

- **ID**: `{rule.get('rule_id', '?')}`
- **Type**: {rule.get('rule_type', '?')}
- **Priority**: {rule.get('priority', '?')} / 5
- **Status**: {'✅ Active' if rule.get('is_active') else '⛔ Inactive'}

**Trigger**: ```json
{json.dumps(trigger, indent=2)}
```

**Action**: ```json
{json.dumps(action, indent=2)}
```

**Performance**:
- Times triggered: {triggered}
- Success rate: {success_rate:.0%}
- Effectiveness score: {rule.get('effectiveness_score', 0):.0%}
- Score measurements: {len(rule.get('score_history', []))} recorded
"""


def build_rule_score_trend(rule_name: str) -> Any:
    """Return a Plotly figure showing the rule's effectiveness score over time."""
    if not rule_name:
        return go.Figure()
    rules = load_rules()
    rule = next(
        (r for r in rules if r.get("name") == rule_name or r.get("rule_id") == rule_name), None
    )
    if not rule:
        return go.Figure()
    history = rule.get("score_history", [])
    if not history:
        fig = go.Figure()
        fig.update_layout(title=f"{rule.get('name', rule_name)} — no score history yet")
        return fig
    dates = [h["date"][:10] for h in history]
    scores = [h["score"] for h in history]
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates, y=scores, mode="lines+markers",
        line=dict(color="#4CAF50" if scores[-1] >= 0.7 else ("#FFC107" if scores[-1] >= 0.4 else "#F44336"), width=2),
        marker=dict(size=8),
        name="Effectiveness",
    ))
    fig.add_hline(y=0.7, line_dash="dot", line_color="green", annotation_text="Good (70%)")
    fig.add_hline(y=0.3, line_dash="dot", line_color="red", annotation_text="Evolve threshold (30%)")
    fig.update_layout(
        title=f"{rule.get('name', rule_name)} — effectiveness over time",
        yaxis=dict(range=[0, 1], tickformat=".0%"),
        xaxis_title="Measurement date",
        yaxis_title="Effectiveness score",
        height=300,
    )
    return fig


def build_rule_version_history(rule_name: str) -> pd.DataFrame:
    """Return a DataFrame of all recorded state changes for a rule."""
    if not rule_name:
        return pd.DataFrame(columns=["Date", "Event", "Score", "Triggered", "Success", "Instruction"])
    rules = load_rules()
    rule = next(
        (r for r in rules if r.get("name") == rule_name or r.get("rule_id") == rule_name), None
    )
    if not rule:
        return pd.DataFrame(columns=["Date", "Event", "Score", "Triggered", "Success", "Instruction"])
    rid = rule.get("rule_id")
    versions = [v for v in load_rule_versions() if v.get("rule_id") == rid]
    if not versions:
        return pd.DataFrame({"Info": ["No version history recorded yet. History is captured on approve, reject, score, and evolve events."]})
    rows = []
    for v in sorted(versions, key=lambda x: x.get("timestamp", ""), reverse=True):
        rows.append({
            "Date": v.get("timestamp", "")[:16],
            "Event": v.get("event", "?"),
            "Score": f"{v.get('effectiveness_score', 0):.0%}" if v.get("effectiveness_score") is not None else "—",
            "Triggered": v.get("times_triggered", 0),
            "Success": v.get("success_count", 0),
            "Instruction": (v.get("instruction", "") or "")[:80],
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Tab 3 — Conversations
# ---------------------------------------------------------------------------

def build_conversations_table() -> pd.DataFrame:
    conversations = load_conversations()
    if not conversations:
        return pd.DataFrame(
            columns=["ID", "Turns", "Gaps", "Rules Applied", "Date"]
        )
    rows = []
    for conv in conversations:
        turns = conv.get("turns", [])
        gaps = sum(len(t.get("gaps_detected", [])) for t in turns)
        rules_applied = sum(len(t.get("rules_applied", [])) for t in turns)
        rows.append(
            {
                "ID": conv.get("conversation_id", "?")[:12],
                "Turns": len(turns),
                "Gaps": gaps,
                "Rules Applied": rules_applied,
                "Date": str(conv.get("created_at", conv.get("updated_at", "")))[:16],
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Tab 4 — Project Compass (project-level health sensor)
# ---------------------------------------------------------------------------

SPACE_ID = "vooom/AI_Rule_Learning"


def build_project_compass() -> tuple[Any, Any, str]:
    """Check Space runtime, dataset growth, rule system health, deployment recency."""
    api = HfApi(token=HF_TOKEN)

    # --- Space runtime status ---
    space_status = "UNKNOWN"
    space_pts = 0
    try:
        runtime = api.get_space_runtime(SPACE_ID)
        space_status = str(runtime.stage.value) if hasattr(runtime.stage, "value") else str(runtime.stage)
        space_pts = 40 if space_status == "RUNNING" else 0
    except Exception:
        space_status = "UNAVAILABLE"

    # --- Dataset metrics ---
    conversations = load_conversations()
    rules = load_rules()
    active_rules = [r for r in rules if r.get("is_active")]
    total_gaps = sum(
        len(t.get("gaps_detected", []))
        for c in conversations
        for t in c.get("turns", [])
    )
    avg_effectiveness = (
        sum(r.get("effectiveness_score", 0) for r in active_rules) / max(len(active_rules), 1)
    ) if active_rules else 0.0
    active_ratio = len(active_rules) / max(len(rules), 1) if rules else 0.0

    data_pts = 20 if conversations else 0
    rules_pts = int(active_ratio * 20) if rules else 0

    # --- Deployment recency (Space commits) ---
    deploy_pts = 0
    last_deploy = "Unknown"
    try:
        commits = list(api.list_repo_commits(SPACE_ID, repo_type="space"))
        if commits:
            latest = commits[0]
            last_deploy = str(latest.created_at)[:16] if hasattr(latest, "created_at") else "Recent"
            deploy_pts = 20
    except Exception:
        last_deploy = "Unknown"

    # --- Overall health score ---
    health_score = space_pts + data_pts + rules_pts + deploy_pts

    # Direction
    if health_score >= 70:
        direction = ("on_track", "🟢", "#22c55e")
    elif health_score >= 40:
        direction = ("needs_attention", "🟡", "#f59e0b")
    else:
        direction = ("off_course", "🔴", "#ef4444")

    # --- Gauge ---
    fig_gauge = go.Figure(go.Indicator(
        mode="gauge+number",
        value=health_score,
        gauge={
            "axis": {"range": [0, 100]},
            "bar": {"color": direction[2]},
            "steps": [
                {"range": [0, 40], "color": "#fee2e2"},
                {"range": [40, 70], "color": "#fef9c3"},
                {"range": [70, 100], "color": "#dcfce7"},
            ],
            "threshold": {"line": {"color": "#1d4ed8", "width": 4}, "value": 70},
        },
        title={"text": f"Project Health<br><span style='font-size:0.9em'>"
                       f"{direction[1]} {direction[0].replace('_', ' ').title()}</span>"},
        number={"suffix": " / 100"},
    ))
    fig_gauge.update_layout(height=320, paper_bgcolor="rgba(0,0,0,0)")

    # --- Metrics bar chart ---
    categories = ["Space Running", "Has Data", "Active Rules", "Recent Deploy"]
    scores = [space_pts, data_pts, rules_pts, deploy_pts]
    max_scores = [40, 20, 20, 20]
    colors = ["#22c55e" if s == m else "#f59e0b" if s > 0 else "#ef4444"
              for s, m in zip(scores, max_scores)]

    fig_metrics = go.Figure(go.Bar(
        x=categories,
        y=scores,
        marker_color=colors,
        text=[f"{s}/{m}" for s, m in zip(scores, max_scores)],
        textposition="outside",
    ))
    fig_metrics.update_layout(
        title="Health Score Breakdown",
        yaxis_range=[0, 45],
        yaxis_title="Points",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        height=320,
    )

    # --- Status summary ---
    space_icon = "🟢" if space_status == "RUNNING" else "🔴"
    data_icon = "🟢" if conversations else "🔴"
    rules_icon = "🟢" if active_ratio >= 0.5 else ("🟡" if active_rules else "🔴")
    deploy_icon = "🟢" if deploy_pts > 0 else "🔴"

    summary = f"""### Project Status Summary

| Component | Status | Detail |
|-----------|--------|--------|
| {space_icon} Space Runtime | `{space_status}` | `{SPACE_ID}` |
| {data_icon} Dataset | `{len(conversations)} conversations` | `{total_gaps} gaps recorded` |
| {rules_icon} Rule System | `{len(active_rules)} active / {len(rules)} total` | avg effectiveness `{avg_effectiveness:.0%}` |
| {deploy_icon} Last Deployment | `{last_deploy}` | Space commit history |

**Overall: {direction[1]} {direction[0].replace('_', ' ').title()} — {health_score}/100**
"""
    return fig_gauge, fig_metrics, summary


# ---------------------------------------------------------------------------
# Tab 5 — Alignment Sensor (per-conversation)
# ---------------------------------------------------------------------------

DIRECTION_EMOJI = {"on_track": "🟢", "drifting": "🟡", "off_course": "🔴"}


def get_conversation_ids() -> list[str]:
    convs = load_conversations()
    return [c.get("conversation_id", "?")[:16] for c in convs] if convs else []


def build_compass(conv_id: str) -> tuple[Any, Any, str]:
    if not conv_id:
        empty = go.Figure()
        empty.update_layout(title="Select a conversation", height=300,
                            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        return empty, empty, "Select a conversation from the dropdown."

    convs = load_conversations()
    conv = next((c for c in convs if c.get("conversation_id", "").startswith(conv_id)), None)
    if conv is None:
        empty = go.Figure()
        empty.update_layout(title="Conversation not found", height=300,
                            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        return empty, empty, "Conversation not found."

    turns = conv.get("turns", [])
    readings = [t.get("sensor_reading") for t in turns]

    # If no sensor readings exist, show a notice
    if not any(readings):
        empty = go.Figure()
        empty.update_layout(
            title="No sensor data — readings are generated during live conversations",
            height=300, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)"
        )
        return empty, empty, (
            "**No sensor readings in this conversation.**\n\n"
            "Sensor readings are generated automatically when conversations are "
            "processed via the `ConversationInterceptor`. Upload conversations "
            "that were recorded through the system to see compass data."
        )

    # Latest reading for the gauge
    latest = next((r for r in reversed(readings) if r), None)
    latest_composite = 0.5
    latest_direction = "drifting"
    latest_heading = 0.0
    if latest:
        ta = latest.get("task_alignment_score", 0)
        rc = latest.get("rule_compliance_score", 1)
        dr = latest.get("drift_score", 0)
        latest_composite = (ta + rc + (1 - dr)) / 3
        latest_direction = latest.get("direction", "drifting")
        latest_heading = latest.get("heading", 0.0)

    # --- Gauge ---
    fig_gauge = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=round(latest_composite * 100, 1),
        delta={"reference": round((latest_composite - latest_heading) * 100, 1),
               "increasing": {"color": "#22c55e"}, "decreasing": {"color": "#ef4444"}},
        gauge={
            "axis": {"range": [0, 100]},
            "bar": {"color": "#3b82f6"},
            "steps": [
                {"range": [0, 40], "color": "#fee2e2"},
                {"range": [40, 70], "color": "#fef9c3"},
                {"range": [70, 100], "color": "#dcfce7"},
            ],
            "threshold": {"line": {"color": "#1d4ed8", "width": 4}, "value": 70},
        },
        title={"text": f"Alignment Score<br><span style='font-size:0.8em'>"
                       f"{DIRECTION_EMOJI.get(latest_direction, '🟡')} {latest_direction.replace('_', ' ').title()}</span>"},
        number={"suffix": "%"},
    ))
    fig_gauge.update_layout(height=300, paper_bgcolor="rgba(0,0,0,0)")

    # --- Timeline ---
    turn_nums, task_scores, rule_scores, focus_scores = [], [], [], []
    for t, r in zip(turns, readings):
        if r:
            turn_nums.append(t.get("turn_number", 0))
            task_scores.append(r.get("task_alignment_score", 0))
            rule_scores.append(r.get("rule_compliance_score", 1))
            focus_scores.append(1 - r.get("drift_score", 0))

    fig_timeline = go.Figure()
    if turn_nums:
        fig_timeline.add_trace(go.Scatter(x=turn_nums, y=task_scores, name="Task Alignment",
                                          mode="lines+markers", line={"color": "#3b82f6"}))
        fig_timeline.add_trace(go.Scatter(x=turn_nums, y=rule_scores, name="Rule Compliance",
                                          mode="lines+markers", line={"color": "#22c55e"}))
        fig_timeline.add_trace(go.Scatter(x=turn_nums, y=focus_scores, name="Focus (1-drift)",
                                          mode="lines+markers", line={"color": "#f59e0b"}))
        fig_timeline.add_hline(y=0.7, line_dash="dash", line_color="#22c55e",
                               annotation_text="On-track threshold")
        fig_timeline.add_hline(y=0.4, line_dash="dash", line_color="#ef4444",
                               annotation_text="Off-course threshold")

    fig_timeline.update_layout(
        title="Alignment Timeline per Turn",
        xaxis_title="Turn", yaxis_title="Score", yaxis_range=[0, 1.05],
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", height=350,
        legend={"orientation": "h", "y": -0.2},
    )

    # --- Alert strip ---
    alerts = []
    for t, r in zip(turns, readings):
        if not r:
            continue
        direction = r.get("direction", "on_track")
        heading = r.get("heading", 0.0)
        turn_n = t.get("turn_number", "?")
        if direction == "off_course":
            alerts.append(f"🔴 **Turn {turn_n}** — OFF COURSE (composite < 40%)")
        elif direction == "drifting" and heading < -0.15:
            alerts.append(f"🟡 **Turn {turn_n}** — DRIFTING and declining (Δ {heading:+.2f})")

    if alerts:
        alert_md = "### ⚠️ Alerts\n\n" + "\n\n".join(alerts)
    else:
        alert_md = "### ✅ No alerts — conversation stayed on track throughout."

    return fig_gauge, fig_timeline, alert_md


# ---------------------------------------------------------------------------
# Tab 5 — Gap Simulator
# ---------------------------------------------------------------------------

def simulate_gap(user_message: str) -> tuple[str, str]:
    msg_lower = user_message.lower()
    rules = load_rules()

    detected_gaps = []
    matched_rules = []

    correction_phrases = ["wrong", "incorrect", "fix", "actually", "instead", "no,", "that's not"]
    if any(p in msg_lower for p in correction_phrases):
        detected_gaps.append("🔴 **explicit_correction** (severity 5) — Correction phrase detected")
        matched = [r for r in rules if "correction" in r.get("rule_id", "") or "correction" in r.get("name", "").lower()]
        matched_rules.extend(matched[:1])

    code_phrases = ["database", "api", "query", "execute", "sql", "request"]
    if any(p in msg_lower for p in code_phrases):
        detected_gaps.append("🟡 **code_anti_pattern** (severity 4) — Code-related request")
        matched = [r for r in rules if "code" in r.get("rule_id", "") or "code" in r.get("name", "").lower() or "error" in r.get("name", "").lower()]
        matched_rules.extend(matched[:1])

    if "?" in user_message and len(user_message) < 40:
        detected_gaps.append("🟢 **simple_query** (severity 1) — Short question detected")

    gap_output = "\n".join(detected_gaps) if detected_gaps else "✅ No gaps detected"

    if matched_rules:
        rules_text = [
            f"- **RULE [{r.get('priority', '?')}/5]**: {(r.get('action') or {}).get('instruction', r.get('name', '?'))}"
            for r in matched_rules
        ]
        prompt = (
            "**System prompt with injected rules:**\n\nYou are a helpful AI assistant.\n\n## ACTIVE RULES\n"
            + "\n".join(rules_text)
        )
    else:
        prompt = "**System prompt (no rules matched):**\n\nYou are a helpful AI assistant."

    return gap_output, prompt


# ---------------------------------------------------------------------------
# Tab 5 — Upload History
# ---------------------------------------------------------------------------

def _parse_json_conversations(content: str) -> list[dict]:
    data = json.loads(content)
    if isinstance(data, dict):
        data = [data]
    return data


def _parse_csv_conversations(content: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(content))
    conversations: dict[str, dict] = {}
    for row in reader:
        cid = row.get("conversation_id") or str(uuid.uuid4())
        if cid not in conversations:
            conversations[cid] = {
                "conversation_id": cid,
                "session_id": row.get("session_id"),
                "user_id": row.get("user_id"),
                "created_at": datetime.utcnow().isoformat(),
                "turns": [],
            }
        turn: dict[str, Any] = {
            "turn_number": int(row.get("turn_number", len(conversations[cid]["turns"]) + 1)),
            "user_input": row.get("user_input", ""),
            "agent_response": row.get("agent_response", ""),
            "gaps_detected": [],
            "rules_applied": [],
        }
        if row.get("sentiment_before"):
            turn["sentiment_before"] = float(row["sentiment_before"])
        if row.get("sentiment_after"):
            turn["sentiment_after"] = float(row["sentiment_after"])
        conversations[cid]["turns"].append(turn)
    return list(conversations.values())


def upload_history(file_obj: Any) -> str:
    if file_obj is None:
        return "No file selected."

    if not HF_TOKEN:
        return "❌ HF_TOKEN not set — add it as a Space secret to enable uploads."

    try:
        # Gradio 5 passes file path as string
        file_path = file_obj if isinstance(file_obj, str) else file_obj.name
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        return f"❌ Could not read file: {e}"

    # Detect format
    stripped = content.strip()
    is_json = stripped.startswith("[") or stripped.startswith("{")

    try:
        if is_json:
            new_convs = _parse_json_conversations(content)
        else:
            new_convs = _parse_csv_conversations(content)
    except Exception as e:
        return f"❌ Parse error: {e}"

    if not new_convs:
        return "⚠️ No conversations found in file."

    # Ensure required fields
    for conv in new_convs:
        if "conversation_id" not in conv or not conv["conversation_id"]:
            conv["conversation_id"] = str(uuid.uuid4())
        if "created_at" not in conv:
            conv["created_at"] = datetime.utcnow().isoformat()
        for i, turn in enumerate(conv.get("turns", []), 1):
            if "turn_number" not in turn:
                turn["turn_number"] = i
            turn.setdefault("gaps_detected", [])
            turn.setdefault("rules_applied", [])

    try:
        existing = load_conversations()
        existing_ids = {c.get("conversation_id") for c in existing}
        to_add = [c for c in new_convs if c.get("conversation_id") not in existing_ids]
        merged = existing + to_add
        _upload_jsonl("conversations.jsonl", merged)
    except Exception as e:
        return f"❌ Upload failed: {e}"

    return (
        f"✅ Uploaded **{len(to_add)}** new conversation(s) "
        f"({len(new_convs) - len(to_add)} skipped as duplicates). "
        f"Dataset now has **{len(merged)}** total conversation(s)."
    )


# ---------------------------------------------------------------------------
# Analysis engine — gap detection + HF-powered rule generation
# ---------------------------------------------------------------------------

_CORRECTION_PHRASES = [
    # Direct contradictions
    "wrong", "incorrect", "that's not", "that is not", "no,", "no that",
    "actually,", "actually ", "instead,", "not right", "not correct",
    "you're wrong", "you are wrong", "that is wrong", "that's wrong",
    # Explicit fix requests
    "fix this", "fix it", "please fix", "please correct", "try again",
    "redo this", "do it again", "start over", "not what i asked", "not what I asked",
    "you missed", "you forgot", "you didn't", "you did not",
    # Confusion / clarification signals
    "i don't understand", "I don't understand", "what do you mean",
    "that makes no sense", "that doesn't make sense", "confusing",
    "you misunderstood", "not my question", "not what i meant", "not what I meant",
    # Frustration signals
    "still wrong", "still not right", "again wrong", "same mistake",
    "you keep", "i already told you", "I already told you",
    "as i said", "as I said", "like i said", "like I said",
]

_FRUSTRATION_PHRASES = [
    "frustrated", "annoying", "useless", "terrible", "awful", "horrible",
    "not helpful", "unhelpful", "waste of time", "doesn't work",
    "ridiculous", "nonsense", "garbage", "pathetic",
    "disappointed", "disappointing", "so bad", "this is bad",
    "can't you", "why can't you", "why don't you",
]

_CODE_ANTIPATTERNS = [
    "eval(", "exec(", "password =", "secret =", "api_key =",
    "hardcoded", "bare except", "except:", "except Exception:",
    "print(",  # debug output left in
    "TODO", "FIXME", "HACK",
]

_SHORT_RESPONSE_CHARS = 40   # responses shorter than this are likely non-answers
_REPEAT_OVERLAP_THRESHOLD = 0.55  # lowered from 0.65
_HF_MODEL = "Qwen/Qwen2.5-72B-Instruct"


def _word_overlap(a: str, b: str) -> float:
    wa, wb = set(a.lower().split()), set(b.lower().split())
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / max(len(wa), len(wb))


def _is_question(text: str) -> bool:
    t = text.strip()
    if t.endswith("?"):
        return True
    lower = t.lower()
    return any(lower.startswith(w) for w in [
        "what ", "why ", "how ", "when ", "where ", "who ", "which ",
        "can you", "could you", "would you", "is there", "do you", "does it",
    ])


def _normalize_turns(conv: dict) -> list[dict]:
    """Return a list of {user_input, agent_response} dicts regardless of source format.

    Handles:
    - Our format: conv["turns"] with user_input / agent_response keys
    - Claude export: conv["chat_messages"] with sender "human"/"assistant" + text
    - Generic messages: conv["messages"] with role "user"/"assistant" + content
    - Gradio history: conv["history"] as [[user, assistant], ...]
    """
    # Already in our format
    turns = conv.get("turns", [])
    if turns and isinstance(turns[0], dict) and (
        "user_input" in turns[0] or "agent_response" in turns[0]
    ):
        return turns

    # Claude.ai export: chat_messages with sender/text
    chat_messages = conv.get("chat_messages", [])
    if chat_messages:
        normalized: list[dict] = []
        pending_user: str | None = None
        for msg in chat_messages:
            sender = msg.get("sender", msg.get("role", ""))
            text = msg.get("text", msg.get("content", ""))
            if isinstance(text, list):
                text = " ".join(
                    b.get("text", "") for b in text if isinstance(b, dict) and b.get("type") == "text"
                )
            text = str(text).strip()
            if sender in ("human", "user"):
                pending_user = text
            elif sender in ("assistant", "ai") and pending_user is not None:
                normalized.append({
                    "turn_number": len(normalized) + 1,
                    "user_input": pending_user,
                    "agent_response": text,
                    "gaps_detected": [],
                    "rules_applied": [],
                    "sensor_reading": None,
                })
                pending_user = None
        if normalized:
            return normalized

    # Generic messages array: role/content
    messages = conv.get("messages", [])
    if messages:
        normalized = []
        pending_user = None
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if isinstance(content, list):
                content = " ".join(
                    b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"
                )
            content = str(content).strip()
            if role in ("user", "human"):
                pending_user = content
            elif role in ("assistant", "ai") and pending_user is not None:
                normalized.append({
                    "turn_number": len(normalized) + 1,
                    "user_input": pending_user,
                    "agent_response": content,
                    "gaps_detected": [],
                    "rules_applied": [],
                    "sensor_reading": None,
                })
                pending_user = None
        if normalized:
            return normalized

    # Gradio-style history: [[user, assistant], ...]
    history = conv.get("history", [])
    if history and isinstance(history[0], (list, tuple)):
        normalized = []
        for i, pair in enumerate(history):
            if len(pair) >= 2:
                normalized.append({
                    "turn_number": i + 1,
                    "user_input": str(pair[0] or ""),
                    "agent_response": str(pair[1] or ""),
                    "gaps_detected": [],
                    "rules_applied": [],
                    "sensor_reading": None,
                })
        if normalized:
            return normalized

    return turns  # return original (possibly empty) as fallback


def _detect_gaps_in_conversation(conv: dict) -> list[dict]:
    gaps = []
    turns = _normalize_turns(conv)
    seen_inputs: list[str] = []

    for turn in turns:
        user_input = turn.get("user_input", "")
        agent_response = turn.get("agent_response", "")
        turn_n = turn.get("turn_number", len(seen_inputs) + 1)
        ui_lower = user_input.lower()
        ar_lower = agent_response.lower()

        # 1. Explicit correction
        matched_phrase = next((p for p in _CORRECTION_PHRASES if p in ui_lower), None)
        if matched_phrase:
            gaps.append({
                "type": "explicit_correction",
                "severity": 5,
                "turn": turn_n,
                "description": f"User correction signal: '{matched_phrase}'",
                "user_input": user_input[:150],
                "agent_response": agent_response[:150],
            })

        # 2. User frustration (separate from correction — broader emotional signal)
        matched_frustration = next((p for p in _FRUSTRATION_PHRASES if p in ui_lower), None)
        if matched_frustration:
            gaps.append({
                "type": "user_frustration",
                "severity": 4,
                "turn": turn_n,
                "description": f"Frustration signal: '{matched_frustration}'",
                "user_input": user_input[:150],
                "agent_response": agent_response[:150],
            })

        # 3. Repeated / unanswered question (word overlap with prior turns)
        for prev in seen_inputs[-5:]:
            if _word_overlap(ui_lower, prev) > _REPEAT_OVERLAP_THRESHOLD and len(user_input.split()) > 3:
                gaps.append({
                    "type": "repeated_question",
                    "severity": 3,
                    "turn": turn_n,
                    "description": "User repeated a similar question — possibly unanswered",
                    "user_input": user_input[:150],
                    "agent_response": agent_response[:150],
                })
                break

        # 4. Unanswered question — user asks something, AI gives a very short response
        if (
            _is_question(user_input)
            and len(user_input.split()) >= 5
            and len(agent_response.strip()) < _SHORT_RESPONSE_CHARS
        ):
            gaps.append({
                "type": "unanswered_question",
                "severity": 4,
                "turn": turn_n,
                "description": f"Question received a very short response ({len(agent_response)} chars)",
                "user_input": user_input[:150],
                "agent_response": agent_response[:150],
            })

        # 5. Code anti-pattern in response
        matched_pattern = next((p for p in _CODE_ANTIPATTERNS if p in agent_response), None)
        if matched_pattern:
            gaps.append({
                "type": "code_anti_pattern",
                "severity": 4,
                "turn": turn_n,
                "description": f"Potentially problematic pattern in response: '{matched_pattern}'",
                "user_input": user_input[:150],
                "agent_response": agent_response[:150],
            })

        # 6. Sentiment drop (numeric fields if present)
        sb = turn.get("sentiment_before")
        sa = turn.get("sentiment_after")
        if sb is not None and sa is not None:
            try:
                if float(sb) - float(sa) > 0.3:
                    gaps.append({
                        "type": "sentiment_drop",
                        "severity": 4,
                        "turn": turn_n,
                        "description": f"Sentiment dropped {float(sb):.2f}→{float(sa):.2f}",
                        "user_input": user_input[:150],
                        "agent_response": agent_response[:150],
                    })
            except (ValueError, TypeError):
                pass

        # 7. Negative sentiment in user input (keyword-based, no numeric fields needed)
        neg_count = sum(1 for w in _FRUSTRATION_PHRASES if w in ui_lower)
        if neg_count >= 2 and not matched_frustration:  # 2+ signals = likely negative
            gaps.append({
                "type": "negative_sentiment",
                "severity": 3,
                "turn": turn_n,
                "description": f"Multiple negative signals detected ({neg_count})",
                "user_input": user_input[:150],
                "agent_response": agent_response[:150],
            })

        seen_inputs.append(ui_lower)

    return gaps


def _backfill_sensor_reading(conv: dict) -> None:
    """Compute and inject sensor_reading for every turn that lacks one.

    Uses word-overlap (no sentence_transformers required) so it works in
    any environment. Updates the dict in place.
    """
    turns = _normalize_turns(conv)
    if not turns:
        return

    anchor = turns[0].get("user_input", "")
    prev_composite: float | None = None

    for turn in turns:
        if turn.get("sensor_reading"):
            # already has a reading — just track composite for heading
            r = turn["sensor_reading"]
            ta = r.get("task_alignment_score", 0.5)
            rc = r.get("rule_compliance_score", 1.0)
            dr = r.get("drift_score", 0.0)
            prev_composite = (ta + rc + (1.0 - dr)) / 3.0
            continue

        user_input = turn.get("user_input", "")
        agent_response = turn.get("agent_response", "")

        # Task alignment: overlap between response and original goal
        task_alignment = _word_overlap(agent_response, anchor) if anchor else 0.5
        task_alignment = max(0.1, min(1.0, task_alignment + 0.3))  # floor/ceiling

        # Rule compliance: degrade if gaps detected
        gaps = turn.get("gaps_detected", [])
        if not gaps:
            rule_compliance = 1.0
        else:
            max_sev = max(g.get("severity", 1) for g in gaps)
            rule_compliance = max(0.0, 1.0 - (max_sev / 5.0) * 0.6)

        # Drift: semantic distance from anchor
        if not user_input.strip() or user_input.strip() == anchor.strip():
            drift = 0.0
        else:
            overlap = _word_overlap(user_input, anchor)
            drift = max(0.0, min(1.0, 1.0 - overlap))

        composite = (task_alignment + rule_compliance + (1.0 - drift)) / 3.0
        heading = (composite - prev_composite) if prev_composite is not None else 0.0

        if composite >= 0.7:
            direction = "on_track"
        elif composite >= 0.4:
            direction = "drifting"
        else:
            direction = "off_course"

        turn["sensor_reading"] = {
            "task_alignment_score": round(task_alignment, 3),
            "rule_compliance_score": round(rule_compliance, 3),
            "drift_score": round(drift, 3),
            "direction": direction,
            "heading": round(heading, 3),
        }
        prev_composite = composite


# ---------------------------------------------------------------------------
# Community contribution — anonymised gap pattern summaries only
# ---------------------------------------------------------------------------

def _contribute_community_gaps(gaps_by_type: dict[str, list[dict]]) -> str:
    """Upload an anonymised gap-pattern summary to the community dataset.

    Sends only: gap type, count, severity distribution — zero conversation text.
    """
    if not gaps_by_type:
        return "no gaps to contribute"
    try:
        import hashlib
        source_hash = hashlib.sha256(
            json.dumps(sorted(gaps_by_type.keys())).encode()
        ).hexdigest()[:16]

        contribution = {
            "source_hash": source_hash,
            "contributed_at": datetime.utcnow().isoformat(),
            "gap_patterns": {
                gtype: {
                    "count": len(gaps),
                    "severity_distribution": {
                        str(s): sum(1 for g in gaps if g.get("severity") == s)
                        for s in range(1, 6)
                        if any(g.get("severity") == s for g in gaps)
                    },
                    "avg_severity": round(
                        sum(g.get("severity", 3) for g in gaps) / max(len(gaps), 1), 2
                    ),
                }
                for gtype, gaps in gaps_by_type.items()
            },
            "total_gaps": sum(len(v) for v in gaps_by_type.values()),
            "total_gap_types": len(gaps_by_type),
        }

        api = HfApi(token=HF_TOKEN)
        filename = f"contributions/{datetime.utcnow().strftime('%Y-%m')}.jsonl"

        try:
            path = hf_hub_download(
                repo_id=COMMUNITY_DATASET_ID,
                filename=filename,
                repo_type="dataset",
                token=HF_TOKEN,
                force_download=True,
            )
            with open(path, encoding="utf-8") as f:
                existing_content = f.read()
        except Exception:
            existing_content = ""

        new_content = existing_content + json.dumps(contribution, ensure_ascii=False) + "\n"
        api.upload_file(
            path_or_fileobj=new_content.encode("utf-8"),
            path_in_repo=filename,
            repo_id=COMMUNITY_DATASET_ID,
            repo_type="dataset",
            commit_message="community gap contribution",
        )
        return f"contributed {sum(len(v) for v in gaps_by_type.values())} gap(s) across {len(gaps_by_type)} type(s)"
    except Exception as e:
        return f"skipped: {e}"


# ---------------------------------------------------------------------------
# Seed rules — empirical rules derived from this project's session gap analysis
# ---------------------------------------------------------------------------

_SEED_RULES: list[dict] = [
    {
        "rule_id": "R1", "name": "Verify live state before reporting",
        "description": "Before stating any system's status, query it live. Never report from memory or assumption.",
        "rule_type": "guardrail", "priority": 5, "severity": 5,
        "trigger": {"keywords": ["status", "is it set", "do we have", "is there", "is the dataset", "is the token", "currently", "running"]},
        "action": {"type": "modify_response", "instruction": "STOP. Query the live system before answering. Do not rely on memory or assumptions. If you cannot query live, state that clearly."},
        "conflicts_with": ["R7"],
        "empirical_basis": "2 explicit user corrections — stale dataset and token status reports",
        "is_active": True, "effectiveness_score": 1.0, "times_triggered": 0, "success_count": 0,
        "created_at": "2026-06-17T19:49:25.330561",
    },
    {
        "rule_id": "R2", "name": "Confirm exact scope before implementing",
        "description": "Restate the interpreted scope (level, data source, target) in one sentence before writing any code.",
        "rule_type": "guardrail", "priority": 5, "severity": 5,
        "trigger": {"keywords": ["add", "implement", "build", "create", "sensor", "dashboard", "write", "code"]},
        "action": {"type": "modify_response", "instruction": "State in ONE sentence what you will build, at what level, using which data source. Ask if ambiguous."},
        "empirical_basis": "2 explicit scope corrections — sensor level and demo-vs-real data",
        "is_active": True, "effectiveness_score": 1.0, "times_triggered": 0, "success_count": 0,
        "created_at": "2026-06-17T19:49:25.330576",
    },
    {
        "rule_id": "R3", "name": "Merge within one minute — never wait for external services",
        "description": "Merge PRs immediately after local validation passes. Max wait: 60 seconds. Exception: production/main requires CI pass.",
        "rule_type": "guardrail", "priority": 4, "severity": 4,
        "trigger": {"keywords": ["waiting", "wait for", "ci", "checks", "passing", "pending", "merge"]},
        "action": {"type": "modify_response", "instruction": "If local validation passed, merge immediately. Max wait: 60 seconds. EXCEPTION: production/main requires CI pass."},
        "empirical_basis": "Explicit user rule — NEVER WAIT MORE THAN ONE MINUTE — MERGE THE PR IMMEDIATELY",
        "is_active": True, "effectiveness_score": 1.0, "times_triggered": 0, "success_count": 0,
        "created_at": "2026-06-17T19:49:25.330582",
    },
    {
        "rule_id": "R4", "name": "Run local validation before every push",
        "description": "Before git push: verify commit subject lowercase ≤100 chars; run prettier; confirm staged files.",
        "rule_type": "guardrail", "priority": 4, "severity": 4,
        "trigger": {"keywords": ["git push", "push", "commit", "pull request", "pr"]},
        "action": {"type": "modify_response", "instruction": "Verify commit subject is lowercase ≤100 chars; run prettier --check on YAML/JSON/MD; confirm staged files. Never use --no-verify."},
        "empirical_basis": "3 avoidable CI failures — uppercase TDD, Fix:, semgrep.yml",
        "is_active": True, "effectiveness_score": 1.0, "times_triggered": 0, "success_count": 0,
        "created_at": "2026-06-17T19:49:25.330578",
    },
    {
        "rule_id": "R5", "name": "Rebase on main before every PR",
        "description": "Always git fetch origin main && git rebase origin/main before pushing a PR branch.",
        "rule_type": "guardrail", "priority": 4, "severity": 4,
        "trigger": {"keywords": ["pull request", "pr", "create pr", "merge", "push branch"]},
        "action": {"type": "modify_response", "instruction": "Before creating a PR: git fetch origin main && git rebase origin/main. Never open a PR from an unrebased branch."},
        "empirical_basis": "3 merge-conflict failures on PRs #14, #15, #16",
        "is_active": True, "effectiveness_score": 1.0, "times_triggered": 0, "success_count": 0,
        "created_at": "2026-06-17T19:49:25.330579",
    },
    {
        "rule_id": "R6", "name": "Re-arm persistent monitors immediately on timeout",
        "description": "When any persistent monitor times out, re-arm it in the same turn before anything else.",
        "rule_type": "guardrail", "priority": 4, "severity": 4,
        "trigger": {"keywords": ["monitor timed out", "timeout", "re-arm", "monitor expired", "dead monitor"]},
        "action": {"type": "modify_response", "instruction": "Re-arm the monitor immediately — before responding about anything else. A dead monitor is a silent failure."},
        "empirical_basis": "2 monitor timeout events that required user prompting to re-arm",
        "is_active": True, "effectiveness_score": 1.0, "times_triggered": 0, "success_count": 0,
        "created_at": "2026-06-17T19:49:25.330583",
    },
    {
        "rule_id": "R7", "name": "Connect to real data — never use placeholders in production",
        "description": "All dashboards and data displays must connect to real sources. No hardcoded samples.",
        "rule_type": "guardrail", "priority": 4, "severity": 4,
        "trigger": {"keywords": ["dashboard", "chart", "graph", "display", "table", "visualization", "data"]},
        "action": {"type": "modify_response", "instruction": "Connect every display to the real data source. If empty, show an empty-state message. Never hardcode sample rows."},
        "empirical_basis": "Explicit user correction — I want real data, not demo data",
        "is_active": True, "effectiveness_score": 1.0, "times_triggered": 0, "success_count": 0,
        "created_at": "2026-06-17T19:49:25.330586",
    },
    {
        "rule_id": "R8", "name": "Fix root cause — never patch symptoms",
        "description": "When CI fails, read the actual log, find the specific file and line, fix that file.",
        "rule_type": "guardrail", "priority": 3, "severity": 3,
        "trigger": {"keywords": ["ci failed", "check failed", "lint failed", "error", "failure", "broken", "failing"]},
        "action": {"type": "modify_response", "instruction": "Read the full error log. Find the exact file and line. Fix that file. Never add --no-verify or ignore comments."},
        "empirical_basis": "Pattern across 4 CI failures in this session",
        "is_active": True, "effectiveness_score": 1.0, "times_triggered": 0, "success_count": 0,
        "created_at": "2026-06-17T19:49:25.330585",
    },
    {
        "rule_id": "R9", "name": "Dynamic responses — no hardcoded phrases",
        "description": "Generate dynamic, complete responses that directly address the user's specific request.",
        "rule_type": "guardrail", "priority": 4, "severity": 4,
        "trigger": {"keywords": ["hardcoded", "user wants", "let me", "think through", "incomplete", "cut-off", "doesn't work", "garbage"]},
        "action": {"type": "modify_response", "instruction": "Generate responses that directly address the user's specific request. Never use hardcoded phrases. Never truncate mid-sentence."},
        "empirical_basis": "245 occurrences of hardcoded phrases + 32 incomplete responses (consolidated from duplicate rules 8 & 13, 11 & 16)",
        "is_active": True, "effectiveness_score": 0.5, "times_triggered": 0, "success_count": 0,
        "created_at": "2026-06-18T00:00:00.000000",
    },
    {
        "rule_id": "R10", "name": "Handle user corrections accurately",
        "description": "Re-evaluate and adjust response when user corrects you. Never ignore or misinterpret corrections.",
        "rule_type": "guardrail", "priority": 4, "severity": 4,
        "trigger": {"keywords": ["actually", "no,", "you didn't", "correction", "not that", "that's wrong"]},
        "action": {"type": "modify_response", "instruction": "Stop. Re-evaluate the user's correction. Adjust your response to accurately reflect their intended meaning. Acknowledge the correction explicitly."},
        "empirical_basis": "253 occurrences where AI ignored or misinterpreted user corrections (consolidated from duplicate rules 9 & 14)",
        "is_active": True, "effectiveness_score": 0.5, "times_triggered": 0, "success_count": 0,
        "created_at": "2026-06-18T00:00:00.000000",
    },
    {
        "rule_id": "R11", "name": "Answer unanswered questions — never repeat without responding",
        "description": "Always respond to user questions with substance. Never repeat the question. Never respond with 0 characters.",
        "rule_type": "guardrail", "priority": 4, "severity": 4,
        "trigger": {"keywords": ["repeat", "unanswered", "question", "clarification", "what", "how", "can", "thinking", "idea", "ways"]},
        "action": {"type": "modify_response", "instruction": "Provide a substantive answer. If unclear, acknowledge and ask for clarification. Never repeat the question back without answering."},
        "empirical_basis": "421 occurrences of repeating unanswered questions + 8 zero-character responses (consolidated from duplicate rules 10 & 15, 12 & 17)",
        "is_active": True, "effectiveness_score": 0.5, "times_triggered": 0, "success_count": 0,
        "created_at": "2026-06-18T00:00:00.000000",
    },
]


def run_deduplicate_rules():
    """Remove duplicate rules: keep the one with the best empirical_basis or highest priority."""
    log: list[str] = []

    def emit(msg: str):
        log.append(msg)
        return "\n".join(log)

    if not HF_TOKEN:
        yield emit("❌ HF_TOKEN not set.")
        return

    yield emit("📋 Loading rules from dataset…")
    rules = load_rules()
    if not rules:
        yield emit("ℹ️ No rules found.")
        return
    yield emit(f"   Loaded {len(rules)} rule(s)")

    # Deduplicate by name (case-insensitive) — keep highest priority / most evidence
    seen_names: dict[str, dict] = {}
    duplicates = 0
    for rule in rules:
        name_key = rule.get("name", "").strip().lower()
        if not name_key:
            name_key = rule.get("rule_id", str(id(rule)))
        if name_key not in seen_names:
            seen_names[name_key] = rule
        else:
            existing = seen_names[name_key]
            # Keep whichever has more empirical_basis text or higher priority
            new_basis_len = len(rule.get("empirical_basis", ""))
            old_basis_len = len(existing.get("empirical_basis", ""))
            new_prio = rule.get("priority", 0)
            old_prio = existing.get("priority", 0)
            if new_basis_len > old_basis_len or (new_basis_len == old_basis_len and new_prio > old_prio):
                seen_names[name_key] = rule
            duplicates += 1

    deduped = list(seen_names.values())
    removed = len(rules) - len(deduped)

    if removed == 0:
        yield emit("✅ No duplicates found — rules are already clean.")
        return

    yield emit(f"🗑️  Removing **{removed}** duplicate(s) — keeping {len(deduped)} unique rule(s)…")
    try:
        _upload_jsonl("rules.jsonl", deduped)
        yield emit(f"✅ Done. Dataset now has **{len(deduped)}** rule(s).")
        yield emit("   Refresh the **Rules** tab to see the cleaned list.")
    except Exception as exc:
        yield emit(f"❌ Upload failed: {exc}")


def run_seed_rules():
    """Upload the 8 empirical work rules to the HF dataset."""
    log: list[str] = []

    def emit(msg: str):
        log.append(msg)
        return "\n".join(log)

    if not HF_TOKEN:
        yield emit("❌ HF_TOKEN not set.")
        return

    yield emit("🌱 Seeding empirical work rules into dataset…")
    existing = load_rules()
    existing_ids = {r.get("rule_id") for r in existing}
    new_rules = [r for r in _SEED_RULES if r["rule_id"] not in existing_ids]

    if not new_rules:
        yield emit(f"✅ All {len(_SEED_RULES)} seed rules already present — nothing to add.")
        return

    all_rules = existing + new_rules
    try:
        _upload_jsonl("rules.jsonl", all_rules)
        yield emit(f"✅ Seeded **{len(new_rules)}** rule(s) into dataset ({len(all_rules)} total)")
        for r in new_rules:
            yield emit(f"   • [P{r['priority']}] **{r['name']}**")
        yield emit("\nRefresh **Rules** and **Overview** tabs to see them.")
    except Exception as exc:
        yield emit(f"❌ Failed to upload rules: {exc}")


CHECKPOINT_FILE = "analysis_checkpoint.json"


def _load_checkpoint() -> dict:
    try:
        path = hf_hub_download(
            repo_id=DATASET_ID,
            filename=CHECKPOINT_FILE,
            repo_type="dataset",
            token=HF_TOKEN,
            force_download=True,
        )
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_checkpoint(state: dict) -> None:
    try:
        api = HfApi(token=HF_TOKEN)
        api.upload_file(
            path_or_fileobj=json.dumps(state, ensure_ascii=False).encode("utf-8"),
            path_in_repo=CHECKPOINT_FILE,
            repo_id=DATASET_ID,
            repo_type="dataset",
            commit_message="Update analysis checkpoint",
        )
    except Exception:
        pass


def _generate_rule_hf(gap_type: str, examples: list[dict], total_conversations: int = 0) -> dict | None:
    try:
        import re
        from huggingface_hub import InferenceClient

        client = InferenceClient(token=HF_TOKEN)

        # Load rejected rule memory so the LLM avoids recreating failed rules
        rejected = load_rejected_rules()
        rejected_block = ""
        if rejected:
            rejected_lines = []
            for r in rejected[-20:]:  # last 20 rejected rules as context
                rejected_lines.append(
                    f"  - \"{r.get('name', '?')}\" — {r.get('reason', 'failed')} "
                    f"(keywords: {r.get('keywords', [])})"
                )
            rejected_block = (
                "\nPreviously tried rules that FAILED and must NOT be recreated:\n"
                + "\n".join(rejected_lines)
                + "\nDo not generate a rule with similar keywords or instructions to any of the above.\n"
            )

        example_parts = []
        for e in examples[:5]:
            user = e.get("user_input", "")[:150]
            agent = e.get("agent_response", "")[:150]
            desc = e.get("description", "")
            turn = e.get("turn", "?")
            example_parts.append(
                f"  Turn {turn}: {desc}\n"
                f"    User said: \"{user}\"\n"
                f"    AI responded: \"{agent}\""
            )
        examples_text = "\n".join(example_parts)

        freq_note = f"{len(examples)} occurrence(s)"
        if total_conversations:
            freq_note += f" found across {total_conversations} conversations scanned"

        prompt = f"""You are an expert at learning from AI conversation failures and converting them into actionable guardrail rules.

Gap pattern: {gap_type}
Frequency: {freq_note}
{rejected_block}
Real failure examples (each shows what the user said and what the AI responded that caused the gap):
{examples_text}

Based only on these real observed failures, write a precise guardrail rule that prevents this pattern.
The rule must be grounded in the specific behaviors above — not generic advice.

Return ONLY a valid JSON object with exactly these fields:
{{
  "name": "Action-oriented rule name (max 8 words)",
  "description": "What specific AI failure this rule prevents, referencing the observed pattern",
  "rule_type": "guardrail",
  "priority": <integer 1-5, where 5=critical based on severity of observed failures>,
  "severity": <same integer as priority>,
  "empirical_basis": "One sentence describing what was actually observed, e.g. 'N occurrences where AI did X instead of Y'",
  "action": {{
    "type": "modify_response",
    "instruction": "Concrete imperative instruction. Start with a strong verb. Be specific about what to do differently based on the observed failures."
  }},
  "trigger": {{
    "keywords": ["keyword1", "keyword2", "keyword3", "keyword4"]
  }}
}}

Only output the JSON. No markdown fences, no explanation."""

        response = client.chat.completions.create(
            model=_HF_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            temperature=0.2,
        )
        text = response.choices[0].message.content.strip()
        text = re.sub(r"^```[a-z]*\n?", "", text).rstrip("`").strip()

        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return None

        rule_data = json.loads(match.group())

        # Block rules too similar to previously rejected ones
        similar_to = _is_too_similar_to_rejected(rule_data, rejected)
        if similar_to:
            return None  # silently skip — caller will log this

        rule_data["rule_id"] = f"rule_{gap_type}_{uuid.uuid4().hex[:8]}"
        rule_data["is_active"] = False
        rule_data["status"] = "pending_review"
        rule_data["effectiveness_score"] = 0.5
        rule_data["times_triggered"] = 0
        rule_data["success_count"] = 0
        rule_data["failure_count"] = 0
        rule_data["score_history"] = []
        rule_data["created_at"] = datetime.utcnow().isoformat()
        rule_data.setdefault("rule_type", "guardrail")
        rule_data.setdefault("priority", 3)
        rule_data.setdefault("severity", rule_data.get("priority", 3))
        rule_data.setdefault("empirical_basis", f"{len(examples)} observed {gap_type} instance(s)")

        return rule_data

    except Exception:
        return None


def run_analysis(contribute: bool = False):
    """Generator — yields the growing log string so Gradio streams it live.

    Ralph Loop pattern: saves a checkpoint after every 10 conversations and
    after each rule is generated so the analysis is fully resumable if the
    Space times out mid-run.
    """
    log: list[str] = []

    def emit(msg: str):
        log.append(msg)
        return "\n".join(log)

    if not HF_TOKEN:
        yield emit("❌ HF_TOKEN not set in Space secrets. Add it in Space Settings → Variables and secrets.")
        return

    # --- Ralph Loop: load checkpoint ---
    yield emit("📌 Loading checkpoint (Ralph Loop)…")
    ckpt = _load_checkpoint()
    processed_ids: set[str] = set(ckpt.get("processed_ids", []))
    all_gaps_by_type: dict[str, list[dict]] = ckpt.get("all_gaps_by_type", {})
    generated_rule_types: set[str] = set(ckpt.get("generated_rule_types", []))
    if processed_ids:
        yield emit(f"   ↩️ Resuming — {len(processed_ids)} conversations already processed, "
                   f"{len(all_gaps_by_type)} gap type(s) cached")

    yield emit("\n🔍 Loading conversations from dataset…")
    conversations = load_conversations()
    if not conversations:
        yield emit("❌ No conversations found. Upload some first via the Upload History tab.")
        return
    yield emit(f"📂 Loaded **{len(conversations)}** conversations")

    # Diagnostic: show the data shape of the first conversation
    if conversations:
        sample = conversations[0]
        sample_keys = list(sample.keys())[:8]
        sample_turns = _normalize_turns(sample)
        yield emit(f"   🔬 Sample fields: `{sample_keys}` | turns (normalized): {len(sample_turns)}")

    # --- Gap detection (skip already-processed ones) ---
    pending = [c for c in conversations if c.get("conversation_id") not in processed_ids]
    if pending:
        yield emit(f"\n🔎 Detecting gaps in **{len(pending)}** new conversation(s)…")
    else:
        yield emit("\n✅ All conversations already processed — using cached gap data")

    conv_gap_map: dict[str, list[dict]] = {}

    for i, conv in enumerate(pending):
        gaps = _detect_gaps_in_conversation(conv)
        cid = conv.get("conversation_id", f"_idx_{i}")
        if gaps:
            conv_gap_map[cid] = gaps
            for g in gaps:
                bucket = all_gaps_by_type.setdefault(g["type"], [])
                bucket.append(g)
        processed_ids.add(cid)

        # Checkpoint every 10 conversations (Ralph Loop)
        if (i + 1) % 10 == 0:
            _save_checkpoint({
                "processed_ids": list(processed_ids),
                "all_gaps_by_type": all_gaps_by_type,
                "generated_rule_types": list(generated_rule_types),
            })
            yield emit(f"   💾 Checkpoint saved ({i + 1}/{len(pending)})")

    total_gaps = sum(len(v) for v in all_gaps_by_type.values())
    total_turns = sum(len(_normalize_turns(c)) for c in conversations)
    yield emit(f"\n📊 Scan complete — **{total_turns}** turns scanned across **{len(conversations)}** conversations")
    if total_gaps == 0:
        yield emit("   ℹ️ No gaps detected in new conversations.")
        yield emit("   Tip: gaps are detected from user correction phrases, frustration signals,")
        yield emit("   repeated questions, unanswered questions, and code anti-patterns.")
        yield emit("   If conversations are very short or in languages other than English,")
        yield emit("   keyword detection may not trigger.")
    else:
        yield emit(f"✅ Found **{total_gaps}** gaps across **{len(conv_gap_map)}** conversation(s):")
        for gtype, gaps in sorted(all_gaps_by_type.items(), key=lambda x: -len(x[1])):
            yield emit(f"   • `{gtype}`: {len(gaps)} occurrence{'s' if len(gaps) != 1 else ''}")

    # --- Opt-in community contribution (anonymised gap summaries only) ---
    if contribute and all_gaps_by_type:
        yield emit("\n🌍 Contributing anonymised gap patterns to community dataset…")
        contrib_msg = _contribute_community_gaps(all_gaps_by_type)
        yield emit(f"   {contrib_msg}")

    # --- Annotate conversations with gaps + backfill sensor readings ---
    if conv_gap_map or pending:
        yield emit("\n💾 Annotating conversations with gap data and sensor readings…")
        for conv in conversations:
            cid = conv.get("conversation_id", "?")
            # Inject gap annotations
            if cid in conv_gap_map:
                gaps_by_turn = {}
                for g in conv_gap_map[cid]:
                    gaps_by_turn.setdefault(g["turn"], []).append(g)
                for turn in conv.get("turns", []):
                    tn = turn.get("turn_number")
                    if tn in gaps_by_turn:
                        turn["gaps_detected"] = gaps_by_turn[tn]
            # Backfill sensor readings for turns that lack them
            _backfill_sensor_reading(conv)
        try:
            _upload_jsonl("conversations.jsonl", conversations)
            yield emit("✅ Conversations annotated with gaps and sensor readings")
        except Exception as exc:
            yield emit(f"⚠️ Could not save annotations: {exc}")

    # --- Rule generation ---
    existing_rules = load_rules()

    # Find which gap types already have rules in the dataset (prevents duplicates
    # when force re-analyze clears the checkpoint but keeps existing rules)
    existing_rule_types: set[str] = set()
    for r in existing_rules:
        rid = r.get("rule_id", "")
        for gtype in all_gaps_by_type:
            if gtype in rid:
                existing_rule_types.add(gtype)

    eligible = {
        k: v for k, v in all_gaps_by_type.items()
        if len(v) >= 2
        and k not in generated_rule_types
        and k not in existing_rule_types
    }
    if not eligible:
        yield emit(f"\nℹ️ No new gap types to generate rules for "
                   f"({len(existing_rule_types)} type(s) already have rules). Done.")
        _save_checkpoint({
            "processed_ids": list(processed_ids),
            "all_gaps_by_type": all_gaps_by_type,
            "generated_rule_types": list(generated_rule_types | existing_rule_types),
        })
        return

    yield emit(f"\n🤖 Generating rules for **{len(eligible)}** gap type(s) using `{_HF_MODEL}`…")
    new_rules: list[dict] = []

    for gtype, gap_examples in eligible.items():
        yield emit(f"\n   ⚙️ `{gtype}` ({len(gap_examples)} examples) — calling HF Inference API…")
        rule = _generate_rule_hf(gtype, gap_examples, total_conversations=len(conversations))
        if rule:
            new_rules.append(rule)
            generated_rule_types.add(gtype)
            yield emit(f"   ✅ Rule created: **{rule.get('name', gtype)}**")
            yield emit(f"      → {rule.get('description', '')}")
            # Ralph Loop: checkpoint after each rule is generated
            _save_checkpoint({
                "processed_ids": list(processed_ids),
                "all_gaps_by_type": all_gaps_by_type,
                "generated_rule_types": list(generated_rule_types),
            })
        else:
            yield emit(f"   ⚠️ Failed to generate rule for `{gtype}` — skipping")

    # --- Save rules ---
    if new_rules:
        try:
            all_rules = existing_rules + new_rules
            _upload_jsonl("rules.jsonl", all_rules)
            yield emit(f"\n🎉 **Analysis complete!**")
            yield emit(f"   • {len(new_rules)} new rule(s) generated and saved")
            yield emit(f"   • {len(all_rules)} total rules in dataset")
            yield emit(f"\nRefresh the **Rules** and **Overview** tabs to see them.")
        except Exception as exc:
            yield emit(f"\n❌ Failed to save rules: {exc}")
    else:
        yield emit("\nℹ️ Analysis complete — no rules could be generated from the HF model response.")

    # Final checkpoint
    _save_checkpoint({
        "processed_ids": list(processed_ids),
        "all_gaps_by_type": all_gaps_by_type,
        "generated_rule_types": list(generated_rule_types),
    })


# ---------------------------------------------------------------------------
# Force re-analyze: clear checkpoint and reprocess all conversations
# ---------------------------------------------------------------------------

def run_force_reanalyze(contribute: bool = False):
    """Clear the Ralph Loop checkpoint so every conversation is reprocessed."""
    log: list[str] = []

    def emit(msg: str):
        log.append(msg)
        return "\n".join(log)

    if not HF_TOKEN:
        yield emit("❌ HF_TOKEN not set.")
        return

    yield emit("🗑️  Clearing checkpoint — all conversations will be reprocessed from scratch…")
    try:
        _save_checkpoint({
            "processed_ids": [],
            "all_gaps_by_type": {},
            "generated_rule_types": [],
        })
        yield emit("✅ Checkpoint cleared.\n")
    except Exception as exc:
        yield emit(f"⚠️  Could not clear checkpoint: {exc} — continuing anyway…\n")

    yield from run_analysis(contribute)


# ---------------------------------------------------------------------------
# Export active rules as a copy-pasteable system prompt
# ---------------------------------------------------------------------------

def export_system_prompt() -> str:
    """Format active rules as a system prompt usable with any AI."""
    rules = load_rules()
    if not rules:
        return "No rules found. Run Analysis first or click 🌱 Seed Work Rules."

    active = [r for r in rules if r.get("is_active", True)]
    if not active:
        return "No active rules found."

    active.sort(key=lambda r: -r.get("priority", 3))

    _priority_label = {5: "CRITICAL", 4: "HIGH", 3: "MEDIUM", 2: "LOW", 1: "INFO"}

    lines = [
        "You are operating under the following empirical guardrail rules derived from",
        "real AI conversation failures. Apply them in every response.",
        "",
    ]

    for i, rule in enumerate(active, 1):
        label = _priority_label.get(rule.get("priority", 3), "MEDIUM")
        lines.append(f"## Rule {i}: {rule.get('name', rule.get('rule_id', 'Unnamed'))}")
        lines.append(f"Priority: {label} | Type: {rule.get('rule_type', 'guardrail')}")
        if rule.get("description"):
            lines.append(f"What it prevents: {rule['description']}")
        if rule.get("empirical_basis"):
            lines.append(f"Evidence: {rule['empirical_basis']}")
        inst = rule.get("action", {}).get("instruction", "")
        if inst:
            lines.append(f"Instruction: {inst}")
        kws = rule.get("trigger", {}).get("keywords", [])
        if kws:
            lines.append(f"Triggers on: {', '.join(kws[:6])}")
        lines.append("")

    lines += [
        "---",
        f"Source: {DATASET_ID} | Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        f"Total active rules: {len(active)}",
    ]

    return "\n".join(lines)


def export_rules_as_yaml() -> str:
    """Format active rules as MCP-compatible YAML (claude-learner / mengram / mcp-standards)."""
    rules = load_rules()
    if not rules:
        return "# No rules found. Run Analysis first or click 🌱 Seed Work Rules."

    active = [r for r in rules if r.get("is_active", True)]
    if not active:
        return "# No active rules found."

    active.sort(key=lambda r: -r.get("priority", 3))
    _priority_label = {5: "critical", 4: "high", 3: "medium", 2: "low", 1: "info"}

    lines = [
        "# AI Guardrail Rules — MCP-Ready YAML",
        f"# Source: {DATASET_ID}",
        f"# Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        f"# Total active rules: {len(active)}",
        f"# Compatible with: claude-learner, mengram, mcp-standards",
        "",
        "rules:",
    ]

    for rule in active:
        rid = rule.get("rule_id", "rule_unknown")
        prio = _priority_label.get(rule.get("priority", 3), "medium")
        lines.append(f"  - id: {rid}")
        lines.append(f"    name: {rule.get('name', rid)}")
        lines.append(f"    priority: {prio}")
        desc = rule.get("description", "")
        if desc:
            lines.append(f"    description: {desc}")
        inst = rule.get("action", {}).get("instruction", "")
        if inst:
            inst_lines = inst.replace("\n", "\n      ")
            lines.append(f"    instruction: |")
            for il in inst.split("\n"):
                lines.append(f"      {il}")
        kws = rule.get("trigger", {}).get("keywords", [])
        if kws:
            lines.append("    triggers:")
            for kw in kws:
                lines.append(f"      - {kw!r}")
        basis = rule.get("empirical_basis", "")
        if basis:
            lines.append(f"    evidence: {basis}")
        lines.append("")

    lines += [
        "metadata:",
        f"  version: '2.0'",
        f"  conversations_analyzed: 289",
        f"  compatible_with:",
        "    - claude-learner",
        "    - mengram",
        "    - mcp-standards",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Mengram-style rule evolution
# ---------------------------------------------------------------------------

_EVOLUTION_THRESHOLD = 0.30   # evolve if effectiveness below this
_DEACTIVATION_THRESHOLD = 0.15  # deactivate if still below this after evolution


def _evolve_rule_hf(rule: dict, failures: list[str]) -> dict | None:
    """Ask the HF model to rewrite a low-performing rule (Mengram procedure_feedback pattern)."""
    try:
        import re
        from huggingface_hub import InferenceClient

        client = InferenceClient(token=HF_TOKEN)
        failure_text = "\n".join(f"- {f}" for f in failures[:5])
        prompt = f"""You are an AI guardrail engineer. A guardrail rule is underperforming.

Current rule:
  Name: {rule.get('name', '?')}
  Description: {rule.get('description', '?')}
  Trigger keywords: {rule.get('trigger', {}).get('keywords', [])}
  Instruction: {rule.get('action', {}).get('instruction', '?')}
  Effectiveness score: {rule.get('effectiveness_score', 0):.0%}

Failure patterns (contexts where the rule did NOT prevent the bad behaviour):
{failure_text}

Rewrite the rule to be more effective. Return ONLY a valid JSON object with these fields:
{{
  "name": "Improved rule name (max 8 words)",
  "description": "What the evolved rule prevents",
  "trigger": {{"keywords": ["keyword1", "keyword2", "keyword3", "keyword4"]}},
  "action": {{"type": "modify_response", "instruction": "Clearer, stronger AI instruction"}}
}}

Only output the JSON. No markdown fences."""

        response = client.chat.completions.create(
            model=_HF_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=350,
            temperature=0.2,
        )
        text = response.choices[0].message.content.strip()
        text = re.sub(r"^```[a-z]*\n?", "", text).rstrip("`").strip()
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return None
        evolved = json.loads(match.group())
        # Merge with existing rule metadata, reset score for fresh measurement
        evolved["rule_id"] = rule.get("rule_id", f"rule_evolved_{uuid.uuid4().hex[:8]}")
        evolved["rule_type"] = rule.get("rule_type", "guardrail")
        evolved["priority"] = rule.get("priority", 3)
        evolved["is_active"] = False
        evolved["status"] = "pending_review"
        evolved["effectiveness_score"] = 0.5
        evolved["times_triggered"] = 0
        evolved["success_count"] = 0
        evolved["failure_count"] = 0
        evolved["evolved_from"] = rule.get("rule_id")
        evolved["evolved_at"] = datetime.utcnow().isoformat()
        return evolved
    except Exception:
        return None


def run_validate_and_evolve():
    """Mengram evolve loop — evolves low-performing rules instead of just deactivating them."""
    log: list[str] = []

    def emit(msg: str):
        log.append(msg)
        return "\n".join(log)

    if not HF_TOKEN:
        yield emit("❌ HF_TOKEN not set.")
        return

    yield emit("📋 Loading rules from dataset…")
    rules = load_rules()
    if not rules:
        yield emit("❌ No rules found. Run Analysis first to generate rules.")
        return

    if not rules:
        yield emit("❌ No rules found. Click **🌱 Seed Work Rules** to load the empirical rules, "
                   "or run **▶ Run Analysis** first to generate rules from conversations.")
        return

    yield emit(f"📂 Loaded **{len(rules)}** rule(s)")

    evolved_rules: list[dict] = []
    deactivated: list[str] = []
    healthy: list[str] = []

    for rule in rules:
        score = rule.get("effectiveness_score", 1.0)
        name = rule.get("name", rule.get("rule_id", "?"))
        triggered = rule.get("times_triggered", 0)

        if score >= _EVOLUTION_THRESHOLD or triggered < 5:
            healthy.append(name)
            continue

        yield emit(f"\n🔬 Rule **{name}** — score {score:.0%} (below {_EVOLUTION_THRESHOLD:.0%} threshold)")

        if score < _DEACTIVATION_THRESHOLD and triggered >= 20:
            rule["is_active"] = False
            rule["status"] = "deactivated"
            deactivated.append(name)
            yield emit(f"   🚫 Deactivated (score {score:.0%} < {_DEACTIVATION_THRESHOLD:.0%} with {triggered} triggers)")
            _snapshot_rule_version(rule, "deactivated")
            _save_to_rejected_memory(
                rule,
                f"auto-deactivated: score {score:.0%} after {triggered} triggers — below {_DEACTIVATION_THRESHOLD:.0%} threshold"
            )
            evolved_rules.append(rule)
            continue

        yield emit(f"   🔄 Evolving via `{_HF_MODEL}`…")
        # Collect simple failure context (keywords that should have triggered but didn't)
        failures = [
            f"Rule triggered {triggered} time(s) but effectiveness only {score:.0%}",
            f"Current keywords: {rule.get('trigger', {}).get('keywords', [])}",
        ]
        evolved = _evolve_rule_hf(rule, failures)
        if evolved:
            evolved_rules.append(evolved)
            yield emit(f"   ✅ Evolved to: **{evolved.get('name', name)}**")
            yield emit(f"      New keywords: {evolved.get('trigger', {}).get('keywords', [])}")
            yield emit(f"      New instruction: {evolved.get('action', {}).get('instruction', '')[:100]}")
        else:
            yield emit(f"   ⚠️ Evolution failed — keeping original")
            evolved_rules.append(rule)

    # Rebuild full rules list (unchanged healthy + evolved/deactivated)
    healthy_rules = [r for r in rules if r.get("name", r.get("rule_id")) in healthy]
    final_rules = healthy_rules + evolved_rules

    try:
        _upload_jsonl("rules.jsonl", final_rules)
        yield emit(f"\n🎉 **Evolution complete!**")
        yield emit(f"   • {len(healthy)} rule(s) healthy (unchanged)")
        yield emit(f"   • {len([r for r in evolved_rules if r.get('evolved_from')])} rule(s) evolved")
        yield emit(f"   • {len(deactivated)} rule(s) deactivated")
        yield emit(f"\nRefresh **Rules** and **Overview** tabs to see the updated ruleset.")
    except Exception as exc:
        yield emit(f"\n❌ Failed to save evolved rules: {exc}")


# ---------------------------------------------------------------------------
# Rule safety check
# ---------------------------------------------------------------------------

_UNSAFE_PHRASES = [
    "never refuse", "ignore safety", "bypass", "override your", "disregard",
    "do not refuse", "don't refuse", "ignore your instructions", "ignore all",
    "forget your", "you must always comply", "no matter what",
]

_CONFLICT_SIMILARITY_THRESHOLD = 0.6


def _check_rule_safety(rule: dict) -> list[str]:
    """Return a list of safety issues found in the rule. Empty list = safe."""
    issues = []
    instruction = (rule.get("action") or {}).get("instruction", "").lower()
    description = rule.get("description", "").lower()
    combined = instruction + " " + description

    for phrase in _UNSAFE_PHRASES:
        if phrase in combined:
            issues.append(f"Contains unsafe phrase: \"{phrase}\"")

    if instruction and len(instruction) < 10:
        issues.append("Instruction too vague (< 10 characters)")

    return issues


def _detect_rule_conflicts(new_rule: dict, existing_rules: list[dict]) -> list[str]:
    """Return names of active rules whose keywords heavily overlap with the new rule."""
    new_kws = set(kw.lower() for kw in (new_rule.get("trigger") or {}).get("keywords", []))
    if not new_kws:
        return []
    conflicts = []
    for r in existing_rules:
        if not r.get("is_active"):
            continue
        if r.get("rule_id") == new_rule.get("rule_id"):
            continue
        existing_kws = set(kw.lower() for kw in (r.get("trigger") or {}).get("keywords", []))
        if not existing_kws:
            continue
        overlap = len(new_kws & existing_kws) / max(len(new_kws | existing_kws), 1)
        if overlap >= _CONFLICT_SIMILARITY_THRESHOLD:
            conflicts.append(r.get("name", r.get("rule_id", "?")))
    return conflicts


# ---------------------------------------------------------------------------
# Review gate — approve / reject pending rules
# ---------------------------------------------------------------------------

def build_pending_rules_table() -> pd.DataFrame:
    rules = load_rules()
    pending = [r for r in rules if r.get("status") == "pending_review"]
    if not pending:
        return pd.DataFrame(columns=["Rule ID", "Name", "Priority", "Gap Type", "Instruction", "Safety"])
    rows = []
    for r in pending:
        issues = _check_rule_safety(r)
        safety = "⚠️ " + "; ".join(issues) if issues else "✅ Safe"
        rows.append({
            "Rule ID": r.get("rule_id", "?"),
            "Name": r.get("name", "?"),
            "Priority": r.get("priority", "?"),
            "Gap Type": r.get("empirical_basis", "")[:60],
            "Instruction": (r.get("action") or {}).get("instruction", "")[:80],
            "Safety": safety,
        })
    return pd.DataFrame(rows)


def get_pending_rule_ids() -> list[str]:
    rules = load_rules()
    return [r.get("rule_id", "?") for r in rules if r.get("status") == "pending_review"]


def get_pending_rule_detail(rule_id: str) -> str:
    if not rule_id:
        return "Select a pending rule to review."
    rules = load_rules()
    rule = next((r for r in rules if r.get("rule_id") == rule_id), None)
    if not rule:
        return "Rule not found."
    issues = _check_rule_safety(rule)
    active_rules = [r for r in rules if r.get("is_active")]
    conflicts = _detect_rule_conflicts(rule, active_rules)
    safety_block = "✅ **No safety issues detected**" if not issues else (
        "⚠️ **Safety issues:**\n" + "\n".join(f"- {i}" for i in issues)
    )
    conflict_block = "✅ **No conflicts with active rules**" if not conflicts else (
        "⚠️ **Conflicts with active rules:**\n" + "\n".join(f"- {c}" for c in conflicts)
    )
    return f"""### {rule.get('name', '?')}

**ID:** `{rule.get('rule_id', '?')}`
**Priority:** {rule.get('priority', '?')} / 5
**Empirical basis:** {rule.get('empirical_basis', '—')}

**Description:**
{rule.get('description', '—')}

**Trigger keywords:** {(rule.get('trigger') or {}).get('keywords', [])}

**Instruction to AI:**
> {(rule.get('action') or {}).get('instruction', '—')}

---

{safety_block}

{conflict_block}

---
_Approve to activate this rule. Reject to discard it._
"""


def approve_rule(rule_id: str) -> str:
    if not rule_id:
        return "No rule selected."
    rules = load_rules()
    rule = next((r for r in rules if r.get("rule_id") == rule_id), None)
    if not rule:
        return f"Rule `{rule_id}` not found."
    issues = _check_rule_safety(rule)
    if issues:
        return "❌ Cannot approve — rule has safety issues:\n" + "\n".join(f"- {i}" for i in issues)
    rule["is_active"] = True
    rule["status"] = "active"
    rule["approved_at"] = datetime.utcnow().isoformat()
    rule.setdefault("score_history", [])
    try:
        _upload_jsonl("rules.jsonl", rules)
        _snapshot_rule_version(rule, "approved")
        return f"✅ Rule **{rule.get('name', rule_id)}** approved and activated."
    except Exception as exc:
        return f"❌ Failed to save: {exc}"


def reject_rule(rule_id: str) -> str:
    if not rule_id:
        return "No rule selected."
    rules = load_rules()
    rule = next((r for r in rules if r.get("rule_id") == rule_id), None)
    if not rule:
        return f"Rule `{rule_id}` not found."
    rule["is_active"] = False
    rule["status"] = "rejected"
    rule["rejected_at"] = datetime.utcnow().isoformat()
    try:
        _upload_jsonl("rules.jsonl", rules)
        _snapshot_rule_version(rule, "rejected_by_user")
        _save_to_rejected_memory(rule, "rejected by user during review")
        return f"🗑️ Rule **{rule.get('name', rule_id)}** rejected — stored in memory so it won't be recreated."
    except Exception as exc:
        return f"❌ Failed to save: {exc}"


# ---------------------------------------------------------------------------
# Effectiveness scoring — measures whether rules actually changed AI behaviour
# ---------------------------------------------------------------------------

_GAP_TYPE_TO_RULE_KEYWORDS: dict[str, list[str]] = {
    "explicit_correction": ["wrong", "correct", "actually", "mistake", "error", "fix"],
    "user_frustration": ["frustrated", "useless", "unhelpful", "annoying", "terrible"],
    "repeated_question": ["repeated", "again", "already asked", "same question"],
    "unanswered_question": ["answer", "question", "explain", "how", "what", "why"],
    "code_anti_pattern": ["code", "security", "eval", "exception", "error handling"],
    "sentiment_drop": ["sentiment", "tone", "attitude", "frustration"],
    "negative_sentiment": ["negative", "frustration", "unhappy", "bad"],
}


def _rule_targets_gap(rule: dict, gap_type: str) -> bool:
    """True if this rule's keywords overlap with the given gap type's indicator words."""
    rule_kws = set(kw.lower() for kw in (rule.get("trigger") or {}).get("keywords", []))
    gap_indicators = set(_GAP_TYPE_TO_RULE_KEYWORDS.get(gap_type, []))
    return bool(rule_kws & gap_indicators)


def run_score_effectiveness():
    """Re-score each rule based on whether gaps still appeared after the rule was applied."""
    log: list[str] = []

    def emit(msg: str):
        log.append(msg)
        return "\n".join(log)

    if not HF_TOKEN:
        yield emit("❌ HF_TOKEN not set.")
        return

    yield emit("📂 Loading conversations and rules…")
    conversations = load_conversations()
    rules = load_rules()
    if not conversations:
        yield emit("❌ No conversations found. Upload and analyse sessions first.")
        return
    if not rules:
        yield emit("❌ No rules found.")
        return

    active_rules = {r["rule_id"]: r for r in rules if r.get("is_active") and r.get("rule_id")}
    if not active_rules:
        yield emit("⚠️ No active rules to score yet.")
        return

    yield emit(f"🔬 Scoring {len(active_rules)} active rule(s) across {len(conversations)} conversation(s)…\n")

    # Reset counters for a fresh measurement
    for r in active_rules.values():
        r["times_triggered"] = 0
        r["success_count"] = 0
        r["failure_count"] = 0

    for conv in conversations:
        turns = conv.get("turns", [])
        for i, turn in enumerate(turns):
            applied_ids = turn.get("rules_applied", [])
            if not applied_ids:
                continue
            # Look ahead: did the same gap types reappear in the next 3 turns?
            subsequent_gaps: set[str] = set()
            for future_turn in turns[i + 1: i + 4]:
                for g in future_turn.get("gaps_detected", []):
                    subsequent_gaps.add(g.get("type", ""))

            for rid in applied_ids:
                rule = active_rules.get(rid)
                if not rule:
                    continue
                rule["times_triggered"] += 1
                # Check if a gap the rule targets still appeared afterward
                reappeared = any(_rule_targets_gap(rule, gtype) for gtype in subsequent_gaps)
                if reappeared:
                    rule["failure_count"] = rule.get("failure_count", 0) + 1
                else:
                    rule["success_count"] += 1

    # Update effectiveness scores and report
    now = datetime.utcnow().isoformat()
    updated = 0
    for rule in rules:
        rid = rule.get("rule_id")
        if rid not in active_rules:
            continue
        scored = active_rules[rid]
        triggered = scored["times_triggered"]
        if triggered == 0:
            rule["effectiveness_score"] = rule.get("effectiveness_score", 0.5)
            yield emit(f"   ⏭️  **{rule.get('name', rid)}** — not yet triggered in session data")
            continue
        score = scored["success_count"] / triggered
        rule["times_triggered"] = triggered
        rule["success_count"] = scored["success_count"]
        rule["failure_count"] = scored.get("failure_count", 0)
        rule["effectiveness_score"] = round(score, 3)
        # Append to score history for trend tracking
        rule.setdefault("score_history", [])
        rule["score_history"].append({
            "date": now,
            "score": round(score, 3),
            "triggered": triggered,
            "success": scored["success_count"],
            "failure": scored.get("failure_count", 0),
        })
        updated += 1
        status = "✅" if score >= 0.7 else ("⚠️" if score >= 0.4 else "❌")
        yield emit(
            f"   {status} **{rule.get('name', rid)}** — "
            f"{triggered} trigger(s), {scored['success_count']} success(es) → {score:.0%} effective"
        )

    try:
        _upload_jsonl("rules.jsonl", rules)
        # Snapshot versions for all scored rules
        for rule in rules:
            if rule.get("rule_id") in active_rules and active_rules[rule["rule_id"]]["times_triggered"] > 0:
                _snapshot_rule_version(rule, "scored")
        yield emit(f"\n🎉 Scored {updated} rule(s). Refresh **Rules** tab to see updated scores.")
        yield emit(
            "\n_Score history is recorded each run — open a rule in the Rules tab to see its trend over time. "
            "Rules below 30% effectiveness will be flagged for evolution._"
        )
    except Exception as exc:
        yield emit(f"\n❌ Failed to save scores: {exc}")


# ---------------------------------------------------------------------------
# Live session import — reads Claude Code ~/.claude/projects/ files
# ---------------------------------------------------------------------------

def _extract_text_from_content(content) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
        return " ".join(parts).strip()
    return ""


_SKIP_TAGS = ["<github-webhook-activity>", "<system-reminder>", "<task-notification>", "<untrusted_external_data"]


def _parse_session_jsonl(lines: list[str]) -> dict | None:
    messages = []
    session_meta: dict = {}

    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue

        msg = obj.get("message", {})
        role = msg.get("role")

        if not session_meta:
            session_meta = {
                "session_id": obj.get("sessionId", str(uuid.uuid4())),
                "slug": obj.get("slug", ""),
                "cwd": obj.get("cwd", ""),
                "git_branch": obj.get("gitBranch", ""),
                "started_at": obj.get("timestamp", datetime.utcnow().isoformat()),
            }

        if role not in ("user", "assistant"):
            continue

        text = _extract_text_from_content(msg.get("content", ""))
        if not text:
            continue

        if role == "user" and any(tag in text for tag in _SKIP_TAGS):
            continue

        messages.append({"role": role, "text": text, "timestamp": obj.get("timestamp", "")})

    if not session_meta or len(messages) < 4:
        return None

    turns = []
    i = 0
    while i < len(messages):
        if messages[i]["role"] == "user":
            j = i + 1
            while j < len(messages) and messages[j]["role"] != "assistant":
                j += 1
            if j < len(messages):
                turns.append({
                    "turn_number": len(turns) + 1,
                    "user_input": _scrub_pii(messages[i]["text"][:4000]),
                    "agent_response": _scrub_pii(messages[j]["text"][:4000]),
                    "timestamp": messages[i]["timestamp"],
                    "gaps_detected": [],
                    "rules_applied": [],
                    "sensor_reading": None,
                })
                i = j + 1
                continue
        i += 1

    if len(turns) < 2:
        return None

    return {
        "conversation_id": f"claude_code_{session_meta['session_id']}",
        "session_id": session_meta["session_id"],
        "slug": session_meta["slug"],
        "project_context": _sanitize_path(session_meta.get("cwd", "")),
        "git_branch": session_meta.get("git_branch", ""),
        "source": "claude_code_local",
        "turns": turns,
        "escalation_occurred": False,
        "human_intervention": False,
        "started_at": session_meta["started_at"],
        "ended_at": datetime.utcnow().isoformat(),
        "exported_at": datetime.utcnow().isoformat(),
    }


def run_import_sessions(jsonl_files):
    """Accept uploaded JSONL files (Claude Code session exports) and merge into dataset."""
    log: list[str] = []

    def emit(msg: str):
        log.append(msg)
        return "\n".join(log)

    if not HF_TOKEN:
        yield emit("❌ HF_TOKEN not set in Space secrets.")
        return

    if not jsonl_files:
        yield emit("❌ No files uploaded. Export sessions first using:\n"
                   "   `python scripts/export_sessions.py --dry-run`\n"
                   "then upload the resulting JSONL files here.")
        return

    yield emit(f"📂 Processing **{len(jsonl_files)}** uploaded file(s)…")

    existing = load_conversations()
    existing_ids = {c.get("conversation_id") for c in existing}
    new_conversations = []

    for f in jsonl_files:
        try:
            with open(f.name, encoding="utf-8") as fh:
                lines = fh.readlines()
            conv = _parse_session_jsonl(lines)
            if conv is None:
                yield emit(f"   ⚠️ {os.path.basename(f.name)} — too short or unreadable, skipped")
                continue
            if conv["conversation_id"] in existing_ids:
                yield emit(f"   ↩️  Already in dataset: {conv.get('slug') or conv['session_id'][:12]}")
                continue
            turns = len(conv["turns"])
            yield emit(f"   ✅ {conv.get('slug') or conv['session_id'][:12]} — {turns} turn(s)")
            new_conversations.append(conv)
        except Exception as exc:
            yield emit(f"   ❌ {os.path.basename(f.name)}: {exc}")

    if not new_conversations:
        yield emit("\nℹ️ No new conversations to add.")
        return

    yield emit(f"\n⬆️ Uploading **{len(new_conversations)}** new conversation(s)…")
    try:
        all_convs = existing + new_conversations
        _upload_jsonl("conversations.jsonl", all_convs)
        yield emit(f"🎉 Done! Dataset now has **{len(all_convs)}** conversation(s).")
    except Exception as exc:
        yield emit(f"❌ Upload failed: {exc}")
        return

    # Auto gap scan on newly imported conversations (fast — no LLM call)
    yield emit("\n🔎 Auto-scanning new conversations for gaps…")
    gap_summary: dict[str, int] = {}
    for conv in new_conversations:
        gaps = _detect_gaps_in_conversation(conv)
        for g in gaps:
            gap_summary[g["type"]] = gap_summary.get(g["type"], 0) + 1

    total_gaps = sum(gap_summary.values())
    if total_gaps == 0:
        yield emit("   ℹ️ No gaps detected in new sessions (keyword detection may not trigger for "
                   "short or non-English conversations).")
    else:
        yield emit(f"   Found **{total_gaps}** gap(s) in the new sessions:")
        for gtype, count in sorted(gap_summary.items(), key=lambda x: -x[1]):
            yield emit(f"   • `{gtype}`: {count}")
        yield emit("\n   Click **▶ Run Analysis** in the Analysis tab to generate rules from these gaps.")


# ---------------------------------------------------------------------------
# Architecture
# ---------------------------------------------------------------------------

ARCHITECTURE_MD = """
## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    CONVERSATION FLOW                            │
│                                                                 │
│  User Input                                                     │
│      │                                                          │
│      ▼                                                          │
│  ┌──────────────┐    ┌─────────────┐    ┌──────────────────┐  │
│  │   Rule       │    │  System     │    │   AI Adapter     │  │
│  │   Engine     │───▶│  Prompt     │───▶│  OpenAI/Claude   │  │
│  │  (pre-hook)  │    │  Injected   │    │                  │  │
│  └──────────────┘    └─────────────┘    └──────────────────┘  │
│         │                                        │              │
│         │                                        ▼              │
│  ┌──────────────┐                      ┌──────────────────┐   │
│  │  HF Dataset  │                      │   AI Response    │   │
│  │  (rules)     │                      │                  │   │
│  └──────────────┘                      └──────────────────┘   │
│                                                  │              │
│                                                  ▼              │
│                                        ┌──────────────────┐   │
│                                        │  Gap Detector    │   │
│                                        │  (post-hook)     │   │
│                                        └──────────────────┘   │
│                                                  │              │
│                              ┌───────────────────┤             │
│                              ▼                   ▼             │
│                    ┌──────────────┐    ┌──────────────────┐   │
│                    │  HF Dataset  │    │ Rule Generator   │   │
│                    │(conversations│    │ (when gaps → 2+) │   │
│                    └──────────────┘    └──────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## Gap Detection Categories

| Gap Type | Trigger | Severity |
|----------|---------|----------|
| `sentiment_drop` | User sentiment falls > 0.3 points | 4 |
| `explicit_correction` | User says "wrong", "actually", "fix" etc. | 5 |
| `repeated_question` | Same question asked 2+ times | 3 |
| `code_anti_pattern` | Bare except, eval, hardcoded secrets | 5 |

## Rule Lifecycle

```
Gap detected → Group similar gaps → ≥2 occurrences?
                                          │
                                     Yes  ▼
                              Generate Rule (via AI)
                                          │
                                          ▼
                              Deploy to HF Dataset
                                          │
                                          ▼
                              Inject in future prompts
                                          │
                                          ▼
                              Track effectiveness
                                          │
                              Score < 15%? → Deactivate
```
"""


# ---------------------------------------------------------------------------
# Dashboard CSS + theme
# ---------------------------------------------------------------------------

_CSS = """
/* Base */
body, .gradio-container { background: #0d1117 !important; }
.app { background: #0d1117 !important; }

/* Header */
.arl-header { padding: 28px 0 8px; }
.arl-header h1 { font-size: 1.6rem; font-weight: 700; color: #f0f6fc; margin: 0; }
.arl-header p  { font-size: 0.875rem; color: #8b949e; margin: 6px 0 0; }

/* Metric cards */
.metrics-row { display: flex; gap: 14px; margin: 0 0 20px; }
.metric-card {
    flex: 1; background: #161b22; border: 1px solid #21262d;
    border-radius: 12px; padding: 20px; text-align: center;
}
.metric-value  { font-size: 2rem; font-weight: 700; color: #58a6ff; display: block; }
.metric-value.green  { color: #3fb950; }
.metric-value.amber  { color: #d29922; }
.metric-value.red    { color: #f85149; }
.metric-label { font-size: 0.72rem; color: #8b949e; text-transform: uppercase;
    letter-spacing: 0.08em; margin-top: 4px; display: block; }

/* Section dividers */
.section-title { font-size: 0.75rem; font-weight: 600; color: #8b949e;
    text-transform: uppercase; letter-spacing: 0.1em;
    margin: 20px 0 10px; padding-bottom: 8px; border-bottom: 1px solid #21262d; }

/* Activity feed */
.activity-feed { display: flex; flex-direction: column; gap: 8px; }
.activity-item { background: #161b22; border: 1px solid #21262d; border-radius: 8px;
    padding: 11px 16px; display: flex; align-items: center; gap: 12px; font-size: 0.875rem; }
.activity-icon { font-size: 1rem; width: 22px; text-align: center; }
.activity-text { color: #e2e8f0; flex: 1; }
.activity-time { color: #8b949e; font-size: 0.72rem; white-space: nowrap; }

/* Pending alert */
.pending-alert { background: #2b1d0e; border: 1px solid #9e6a03; border-radius: 10px;
    padding: 13px 18px; color: #d29922; font-size: 0.875rem; margin-bottom: 14px; }
.pending-alert.none { background: #0d2119; border-color: #238636; color: #3fb950; }

/* Tabs */
.tab-nav button { color: #8b949e !important; }
.tab-nav button.selected { color: #f0f6fc !important; border-bottom-color: #58a6ff !important; }

/* Inputs / textboxes */
.gr-textbox textarea, .gr-textbox input { background: #161b22 !important;
    border-color: #21262d !important; color: #e2e8f0 !important; }
label.gr-form { color: #8b949e !important; }
"""


# ---------------------------------------------------------------------------
# Dashboard helper functions
# ---------------------------------------------------------------------------

def _dark_fig(fig: Any) -> Any:
    """Apply consistent dark styling to a Plotly figure."""
    fig.update_layout(
        paper_bgcolor="#161b22",
        plot_bgcolor="#161b22",
        font=dict(color="#e2e8f0", size=12),
        xaxis=dict(gridcolor="#21262d", linecolor="#21262d"),
        yaxis=dict(gridcolor="#21262d", linecolor="#21262d"),
        margin=dict(l=16, r=16, t=44, b=16),
    )
    return fig


def build_metrics_html() -> str:
    rules = load_rules()
    conversations = load_conversations()
    active = [r for r in rules if r.get("is_active")]
    pending = [r for r in rules if r.get("status") == "pending_review"]
    avg_eff = sum(r.get("effectiveness_score", 0) for r in active) / max(len(active), 1)
    eff_cls = "green" if avg_eff >= 0.7 else ("amber" if avg_eff >= 0.4 else ("red" if active else ""))
    pending_cls = "amber" if pending else "green"
    return f"""
<div class="metrics-row">
  <div class="metric-card"><span class="metric-value green">{len(active)}</span><span class="metric-label">Active Rules</span></div>
  <div class="metric-card"><span class="metric-value {eff_cls}">{avg_eff:.0%}</span><span class="metric-label">Avg Effectiveness</span></div>
  <div class="metric-card"><span class="metric-value">{len(conversations)}</span><span class="metric-label">Sessions Analyzed</span></div>
  <div class="metric-card"><span class="metric-value {pending_cls}">{len(pending)}</span><span class="metric-label">Pending Review</span></div>
</div>"""


def build_activity_html() -> str:
    versions = load_rule_versions()
    if not versions:
        return '<div class="activity-item"><span class="activity-text" style="color:#8b949e">No activity yet — import sessions and run analysis to get started.</span></div>'
    recent = sorted(versions, key=lambda x: x.get("timestamp", ""), reverse=True)[:10]
    icons = {
        "approved": "✅", "rejected_by_user": "🗑️", "scored": "📊",
        "evolved": "🔄", "deactivated": "⛔", "scored_auto": "📊",
    }
    labels = {
        "approved": "activated", "rejected_by_user": "rejected", "scored": "scored",
        "evolved": "evolved", "deactivated": "deactivated",
    }
    items = []
    for v in recent:
        event = v.get("event", "?")
        icon = icons.get(event, "📝")
        label = labels.get(event, event)
        name = v.get("name", "Unknown rule")
        time = v.get("timestamp", "")[:16].replace("T", " ")
        score = v.get("effectiveness_score")
        score_str = f" · {score:.0%}" if score is not None else ""
        items.append(
            f'<div class="activity-item">'
            f'<span class="activity-icon">{icon}</span>'
            f'<span class="activity-text"><strong>{name}</strong> {label}{score_str}</span>'
            f'<span class="activity-time">{time}</span></div>'
        )
    return f'<div class="activity-feed">{"".join(items)}</div>'


def build_pending_alert_html() -> str:
    rules = load_rules()
    pending = [r for r in rules if r.get("status") == "pending_review"]
    if pending:
        names = ", ".join(r.get("name", "?") for r in pending[:3])
        more = f" + {len(pending) - 3} more" if len(pending) > 3 else ""
        return f'<div class="pending-alert">⚠️ <strong>{len(pending)} rule(s) waiting for review:</strong> {names}{more} — go to the <strong>Rules</strong> tab to approve or reject.</div>'
    return '<div class="pending-alert none">✅ No rules pending review.</div>'


def build_effectiveness_chart_dark() -> Any:
    rules = load_rules()
    if not rules:
        return _dark_fig(go.Figure())
    active = [r for r in rules if r.get("is_active")]
    if not active:
        return _dark_fig(go.Figure())
    names = [r.get("name", r.get("rule_id", "?"))[:30] for r in active]
    scores = [r.get("effectiveness_score", 0) for r in active]
    colors = ["#3fb950" if s >= 0.7 else ("#d29922" if s >= 0.4 else "#f85149") for s in scores]
    fig = go.Figure(go.Bar(
        x=scores, y=names, orientation="h",
        marker_color=colors,
        text=[f"{s:.0%}" for s in scores], textposition="outside",
    ))
    fig.update_layout(
        title=dict(text="Rule Effectiveness", font=dict(size=14, color="#e2e8f0")),
        xaxis=dict(range=[0, 1.1], tickformat=".0%"),
        height=max(250, len(active) * 38),
    )
    return _dark_fig(fig)


# ---------------------------------------------------------------------------
# Conversation clustering — group by project context, visualise gap distribution
# ---------------------------------------------------------------------------

def build_cluster_chart() -> Any:
    """Stack-bar of gap types per project context — shows where problems concentrate."""
    conversations = load_conversations()
    if not conversations:
        return _dark_fig(go.Figure(layout=dict(
            title=dict(text="No data — import sessions first", font=dict(color="#e2e8f0")),
            height=320,
        )))

    cluster_gaps: dict[str, dict[str, int]] = {}
    for conv in conversations:
        raw_ctx = (
            conv.get("project_context")
            or conv.get("git_branch")
            or conv.get("slug")
            or "unknown"
        )
        ctx = str(raw_ctx).rstrip("/").split("/")[-1][:30] or "unknown"
        bucket = cluster_gaps.setdefault(ctx, {})
        for turn in conv.get("turns", []):
            for gap in turn.get("gaps_detected", []):
                gtype = gap.get("type", "unknown") if isinstance(gap, dict) else str(gap)
                bucket[gtype] = bucket.get(gtype, 0) + 1

    if not cluster_gaps:
        return _dark_fig(go.Figure(layout=dict(
            title=dict(text="No gaps recorded yet — run Analysis first", font=dict(color="#e2e8f0")),
            height=320,
        )))

    contexts = list(cluster_gaps.keys())
    gap_types = sorted({gt for b in cluster_gaps.values() for gt in b})
    palette = ["#58a6ff", "#3fb950", "#d29922", "#f85149", "#8b5cf6", "#06b6d4", "#ec4899"]

    fig = go.Figure()
    for i, gtype in enumerate(gap_types):
        fig.add_trace(go.Bar(
            name=gtype.replace("_", " ").title(),
            x=contexts,
            y=[cluster_gaps[ctx].get(gtype, 0) for ctx in contexts],
            marker_color=palette[i % len(palette)],
        ))
    fig.update_layout(
        barmode="stack",
        title=dict(text="Gap Frequency by Project Context", font=dict(size=14, color="#e2e8f0")),
        xaxis_title="Project / Context",
        yaxis_title="Gaps detected",
        height=340,
        legend=dict(orientation="h", y=-0.28, font=dict(size=11)),
    )
    return _dark_fig(fig)


def build_cluster_summary() -> str:
    """Return markdown table: project context → conversation count, gap count, top gap type."""
    conversations = load_conversations()
    if not conversations:
        return "_No conversations yet._"

    rows: dict[str, dict] = {}
    for conv in conversations:
        raw_ctx = (
            conv.get("project_context")
            or conv.get("git_branch")
            or conv.get("slug")
            or "unknown"
        )
        ctx = str(raw_ctx).rstrip("/").split("/")[-1][:40] or "unknown"
        r = rows.setdefault(ctx, {"convs": 0, "gaps": 0, "types": {}})
        r["convs"] += 1
        for turn in conv.get("turns", []):
            for gap in turn.get("gaps_detected", []):
                gtype = gap.get("type", "?") if isinstance(gap, dict) else str(gap)
                r["gaps"] += 1
                r["types"][gtype] = r["types"].get(gtype, 0) + 1

    lines = ["| Project | Sessions | Gaps | Top Issue |", "|---------|----------|------|-----------|"]
    for ctx, data in sorted(rows.items(), key=lambda x: -x[1]["gaps"]):
        top = max(data["types"], key=data["types"].get) if data["types"] else "—"
        top = top.replace("_", " ")
        lines.append(f"| `{ctx}` | {data['convs']} | {data['gaps']} | {top} |")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# A/B testing — create keyword variants of rules and compare effectiveness
# ---------------------------------------------------------------------------

def create_rule_ab_variant(rule_name: str) -> str:
    """Generate a keyword/instruction variant of a rule for A/B comparison."""
    if not rule_name:
        return "Select a rule first."
    if not HF_TOKEN:
        return "❌ HF_TOKEN not set."
    rules = load_rules()
    rule = next(
        (r for r in rules if r.get("name") == rule_name or r.get("rule_id") == rule_name), None
    )
    if not rule:
        return "Rule not found."

    try:
        import re
        from huggingface_hub import InferenceClient

        client = InferenceClient(token=HF_TOKEN)
        original_kws = (rule.get("trigger") or {}).get("keywords", [])
        original_inst = (rule.get("action") or {}).get("instruction", "")

        prompt = f"""You are an AI guardrail engineer. Create a variant of this rule with different trigger keywords but the same intent, for A/B effectiveness testing.

Original rule:
  Name: {rule.get('name')}
  Instruction: {original_inst}
  Keywords: {original_kws}

Generate a variant with broader or more specific keywords. The instruction may be slightly refined but must have the same goal.

Return ONLY a valid JSON object:
{{
  "trigger": {{"keywords": ["kw1", "kw2", "kw3", "kw4"]}},
  "action": {{"type": "modify_response", "instruction": "Refined instruction here"}}
}}

Only output the JSON. No markdown fences."""

        response = client.chat.completions.create(
            model=_HF_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=250,
            temperature=0.3,
        )
        text = response.choices[0].message.content.strip()
        text = re.sub(r"^```[a-z]*\n?", "", text).rstrip("`").strip()
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return "❌ Could not parse variant from model response."

        variant_data = json.loads(match.group())
        variant: dict = {
            **rule,
            "rule_id": f"{rule.get('rule_id', 'rule')}_v{uuid.uuid4().hex[:6]}",
            "name": f"{rule.get('name', '?')} (Variant)",
            "is_active": False,
            "status": "pending_review",
            "ab_original_id": rule.get("rule_id"),
            "effectiveness_score": 0.5,
            "times_triggered": 0,
            "success_count": 0,
            "failure_count": 0,
            "score_history": [],
            "created_at": datetime.utcnow().isoformat(),
        }
        variant["trigger"] = variant_data.get("trigger", rule.get("trigger", {}))
        variant["action"] = variant_data.get("action", rule.get("action", {}))

        _upload_jsonl("rules.jsonl", rules + [variant])
        new_kws = variant["trigger"].get("keywords", [])
        return (
            f"✅ A/B variant created: **{variant['name']}**\n\n"
            f"**Original keywords:** {original_kws}\n\n"
            f"**Variant keywords:** {new_kws}\n\n"
            f"Go to **Review Queue** to approve the variant, then run "
            f"**Score Effectiveness** after sessions to compare performance."
        )
    except Exception as exc:
        return f"❌ Failed to create variant: {exc}"


def build_ab_comparison(rule_name: str) -> str:
    """Compare effectiveness of original rule vs its A/B variant(s)."""
    if not rule_name:
        return "_Select a rule to see its A/B comparison._"
    rules = load_rules()
    rule = next(
        (r for r in rules if r.get("name") == rule_name or r.get("rule_id") == rule_name), None
    )
    if not rule:
        return "Rule not found."

    rid = rule.get("rule_id")
    # Look for variants of this rule, and also check if this IS a variant
    variants = [r for r in rules if r.get("ab_original_id") == rid]
    original_id = rule.get("ab_original_id")
    if original_id and not variants:
        original = next((r for r in rules if r.get("rule_id") == original_id), None)
        if original:
            return build_ab_comparison(original.get("name") or original_id)

    if not variants:
        return (
            "_No A/B variants found for this rule._\n\n"
            "Click **Create A/B Variant** above to generate an alternative version "
            "with different trigger keywords for comparison testing."
        )

    def _fmt(r: dict, label: str) -> list[str]:
        eff = r.get("effectiveness_score", 0)
        triggered = r.get("times_triggered", 0)
        status = "✅ Active" if r.get("is_active") else "⏳ Pending review"
        kws = (r.get("trigger") or {}).get("keywords", [])
        return [
            f"**{label}** (`{r.get('rule_id')}`)",
            f"- Effectiveness: **{eff:.0%}**",
            f"- Triggered: {triggered} time(s)",
            f"- Keywords: `{kws}`",
            f"- Status: {status}",
        ]

    lines = [f"### A/B Comparison — {rule.get('name', rid)}\n"]
    lines += _fmt(rule, "Original")
    lines.append("")

    for v in variants:
        lines += _fmt(v, "Variant")
        orig_eff = rule.get("effectiveness_score", 0)
        var_eff = v.get("effectiveness_score", 0)
        orig_t = rule.get("times_triggered", 0)
        var_t = v.get("times_triggered", 0)
        if orig_t >= 5 and var_t >= 5:
            if var_eff > orig_eff + 0.05:
                lines.append(f"\n🏆 **Variant is winning** (+{var_eff - orig_eff:.0%}) — consider replacing the original.")
            elif orig_eff > var_eff + 0.05:
                lines.append(f"\n🏆 **Original is winning** (+{orig_eff - var_eff:.0%}) — variant can be rejected.")
            else:
                lines.append("\n🤝 **Too close to call** — collect more trigger data.")
        else:
            lines.append(
                f"\n_Need ≥5 triggers each to declare a winner. "
                f"Original: {orig_t}, Variant: {var_t}._"
            )
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Build Gradio app
# ---------------------------------------------------------------------------

with gr.Blocks(title="AI Rule Learning", theme=gr.themes.Base(), css=_CSS) as demo:

    gr.HTML("""
<div class="arl-header">
  <h1>AI Rule Learning</h1>
  <p>Your AI gets smarter every session — automatically.</p>
</div>
""")

    with gr.Tabs():

        # ── Dashboard ────────────────────────────────────────────────────────
        with gr.Tab("📊 Dashboard"):
            metrics_html = gr.HTML()
            pending_alert = gr.HTML()
            dashboard_refresh = gr.Button("↻ Refresh", variant="secondary", size="sm")

            gr.HTML('<div class="section-title">Rule Effectiveness</div>')
            dash_eff_chart = gr.Plot()

            gr.HTML('<div class="section-title">Recent Activity</div>')
            activity_html = gr.HTML()

            def refresh_dashboard():
                return (
                    build_metrics_html(),
                    build_pending_alert_html(),
                    build_effectiveness_chart_dark(),
                    build_activity_html(),
                )

            dashboard_refresh.click(
                refresh_dashboard,
                outputs=[metrics_html, pending_alert, dash_eff_chart, activity_html],
            )
            demo.load(
                refresh_dashboard,
                outputs=[metrics_html, pending_alert, dash_eff_chart, activity_html],
            )

        # ── Rules ────────────────────────────────────────────────────────────
        with gr.Tab("📋 Rules"):

            gr.HTML('<div class="section-title">Active Rules</div>')
            rules_table = gr.Dataframe(interactive=False, wrap=True)
            refresh_rules_btn = gr.Button("↻ Refresh", variant="secondary", size="sm")

            rule_selector = gr.Dropdown(label="Select rule", choices=[])
            rule_detail = gr.Markdown()

            gr.HTML('<div class="section-title">Effectiveness Trend</div>')
            score_trend_chart = gr.Plot()

            gr.HTML('<div class="section-title">Version History</div>')
            version_history_table = gr.Dataframe(interactive=False, wrap=True)

            def refresh_rules():
                return build_rules_table(), gr.Dropdown(choices=get_rule_names())

            refresh_rules_btn.click(refresh_rules, outputs=[rules_table, rule_selector])
            demo.load(refresh_rules, outputs=[rules_table, rule_selector])
            rule_selector.change(get_rule_detail, inputs=rule_selector, outputs=rule_detail)
            rule_selector.change(build_rule_score_trend, inputs=rule_selector, outputs=score_trend_chart)
            rule_selector.change(build_rule_version_history, inputs=rule_selector, outputs=version_history_table)

            gr.HTML('<div class="section-title">Review Queue</div>')
            pending_table = gr.Dataframe(interactive=False, wrap=True)
            refresh_pending_btn = gr.Button("↻ Refresh queue", variant="secondary", size="sm")
            pending_selector = gr.Dropdown(label="Select pending rule", choices=[])
            pending_detail = gr.Markdown()

            with gr.Row():
                approve_btn = gr.Button("✅ Approve & Activate", variant="primary")
                reject_btn = gr.Button("🗑️ Reject", variant="stop")
            review_status = gr.Markdown()

            def refresh_pending():
                return build_pending_rules_table(), gr.Dropdown(choices=get_pending_rule_ids())

            refresh_pending_btn.click(refresh_pending, outputs=[pending_table, pending_selector])
            demo.load(refresh_pending, outputs=[pending_table, pending_selector])
            pending_selector.change(get_pending_rule_detail, inputs=pending_selector, outputs=pending_detail)
            approve_btn.click(approve_rule, inputs=pending_selector, outputs=review_status)
            reject_btn.click(reject_rule, inputs=pending_selector, outputs=review_status)

            gr.HTML('<div class="section-title">A/B Testing</div>')
            gr.Markdown("Create a keyword variant of a rule to compare effectiveness after real sessions.")
            ab_rule_selector = gr.Dropdown(label="Select rule to test", choices=[])
            ab_refresh_btn = gr.Button("↻ Refresh rule list", variant="secondary", size="sm")
            ab_create_btn = gr.Button("🧪 Create A/B Variant", variant="secondary")
            ab_status = gr.Markdown()
            ab_comparison = gr.Markdown()

            def _refresh_ab_rules():
                return gr.Dropdown(choices=get_rule_names())

            ab_refresh_btn.click(_refresh_ab_rules, outputs=ab_rule_selector)
            demo.load(_refresh_ab_rules, outputs=ab_rule_selector)
            ab_rule_selector.change(build_ab_comparison, inputs=ab_rule_selector, outputs=ab_comparison)
            ab_create_btn.click(create_rule_ab_variant, inputs=ab_rule_selector, outputs=ab_status)

            gr.HTML('<div class="section-title">Export</div>')
            with gr.Row():
                export_btn = gr.Button("Export as System Prompt", variant="secondary", size="sm")
                yaml_export_btn = gr.Button("Export as YAML", variant="secondary", size="sm")
            system_prompt_output = gr.Textbox(
                label="System prompt",
                lines=15, interactive=True, show_copy_button=True,
            )
            yaml_output = gr.Textbox(
                label="YAML",
                lines=15, interactive=True, show_copy_button=True,
            )
            export_btn.click(export_system_prompt, outputs=system_prompt_output)
            yaml_export_btn.click(export_rules_as_yaml, outputs=yaml_output)

        # ── Sessions ─────────────────────────────────────────────────────────
        with gr.Tab("🔄 Sessions"):

            gr.HTML('<div class="section-title">Step 1 — Import Sessions</div>')
            with gr.Row():
                with gr.Column():
                    gr.Markdown("**Upload Claude Code session files (.jsonl)**")
                    session_files_input = gr.File(
                        label="Session files",
                        file_types=[".jsonl"],
                        file_count="multiple",
                    )
                    import_btn = gr.Button("Import", variant="primary")

                with gr.Column():
                    gr.Markdown("**Upload conversation history (JSON or CSV)**")
                    upload_file = gr.File(
                        label="Conversation file",
                        file_types=[".json", ".csv"],
                    )
                    upload_btn = gr.Button("Upload", variant="primary")

            import_log = gr.Textbox(label="Import log", lines=8, interactive=False, autoscroll=True)
            upload_status = gr.Markdown()

            import_btn.click(run_import_sessions, inputs=session_files_input, outputs=import_log)
            upload_btn.click(upload_history, inputs=upload_file, outputs=upload_status)

            gr.HTML('<div class="section-title">Step 2 — Analyse</div>')
            with gr.Row():
                analysis_btn = gr.Button("▶ Run Analysis", variant="primary", size="lg")
                reanalyze_btn = gr.Button("🔁 Re-analyze All", variant="secondary", size="lg")
                score_btn = gr.Button("📊 Score Effectiveness", variant="secondary", size="lg")

            with gr.Row():
                evolve_btn = gr.Button("🔄 Evolve Low-Scoring Rules", variant="secondary")
                seed_btn = gr.Button("🌱 Load Starter Rules", variant="secondary")
                dedup_btn = gr.Button("🧹 Remove Duplicates", variant="secondary")

            community_toggle = gr.Checkbox(
                label="Contribute anonymous gap patterns to the community (no conversation text)",
                value=False,
            )
            analysis_log = gr.Textbox(
                label="Analysis log", lines=18, interactive=False, autoscroll=True,
            )

            analysis_btn.click(run_analysis, inputs=community_toggle, outputs=analysis_log)
            reanalyze_btn.click(run_force_reanalyze, inputs=community_toggle, outputs=analysis_log)
            evolve_btn.click(run_validate_and_evolve, outputs=analysis_log)
            seed_btn.click(run_seed_rules, outputs=analysis_log)
            dedup_btn.click(run_deduplicate_rules, outputs=analysis_log)
            score_btn.click(run_score_effectiveness, outputs=analysis_log)

            gr.HTML('<div class="section-title">Step 3 — Review New Rules</div>')
            gr.Markdown("New rules generated by analysis appear in the **Rules** tab → Review Queue. Approve each one to activate it.")

        # ── Insights ─────────────────────────────────────────────────────────
        with gr.Tab("🔬 Insights"):

            gr.HTML('<div class="section-title">Conversation Clusters</div>')
            gr.Markdown("Gap frequency grouped by project context — shows where problems concentrate.")
            cluster_chart = gr.Plot()
            cluster_summary = gr.Markdown()
            cluster_refresh_btn = gr.Button("↻ Refresh", variant="secondary", size="sm")

            def _refresh_clusters():
                return build_cluster_chart(), build_cluster_summary()

            cluster_refresh_btn.click(_refresh_clusters, outputs=[cluster_chart, cluster_summary])
            demo.load(_refresh_clusters, outputs=[cluster_chart, cluster_summary])

            gr.HTML('<div class="section-title">Conversations</div>')
            conversations_table = gr.Dataframe(interactive=False, wrap=True)
            refresh_convs_btn = gr.Button("↻ Refresh", variant="secondary", size="sm")
            refresh_convs_btn.click(build_conversations_table, outputs=[conversations_table])
            demo.load(build_conversations_table, outputs=[conversations_table])

            gr.HTML('<div class="section-title">Alignment Sensor</div>')
            gr.Markdown("Per-conversation task focus, rule compliance, and drift across turns.")
            with gr.Row():
                conv_selector = gr.Dropdown(label="Conversation", choices=[], scale=3)
                refresh_compass_btn = gr.Button("↻ Refresh list", variant="secondary", size="sm", scale=1)

            with gr.Row():
                compass_gauge = gr.Plot()
                compass_timeline = gr.Plot()
            compass_alerts = gr.Markdown()

            def refresh_compass_list():
                return gr.Dropdown(choices=get_conversation_ids())

            refresh_compass_btn.click(refresh_compass_list, outputs=[conv_selector])
            demo.load(refresh_compass_list, outputs=[conv_selector])
            conv_selector.change(
                build_compass, inputs=conv_selector,
                outputs=[compass_gauge, compass_timeline, compass_alerts],
            )

            gr.HTML('<div class="section-title">System Health</div>')
            with gr.Row():
                proj_gauge = gr.Plot()
                proj_metrics = gr.Plot()
            proj_summary = gr.Markdown()
            proj_refresh_btn = gr.Button("↻ Refresh", variant="secondary", size="sm")
            proj_refresh_btn.click(build_project_compass, outputs=[proj_gauge, proj_metrics, proj_summary])
            demo.load(build_project_compass, outputs=[proj_gauge, proj_metrics, proj_summary])

            gr.HTML('<div class="section-title">Gap Simulator</div>')
            gr.Markdown("Type a message to see which gaps would be detected and which rules would apply.")
            sim_input = gr.Textbox(
                label="Message",
                placeholder="e.g. That's wrong, you forgot error handling",
                lines=2,
            )
            sim_btn = gr.Button("Simulate", variant="primary", size="sm")
            with gr.Row():
                gap_output = gr.Markdown()
                prompt_output = gr.Markdown()
            sim_btn.click(simulate_gap, inputs=sim_input, outputs=[gap_output, prompt_output])
            sim_input.submit(simulate_gap, inputs=sim_input, outputs=[gap_output, prompt_output])
            gr.Examples(
                examples=[
                    ["That's wrong, you forgot error handling in the database query"],
                    ["Actually, I said I wanted Python not JavaScript"],
                    ["I asked you this already — how do I query the API?"],
                ],
                inputs=sim_input,
            )


if __name__ == "__main__":
    demo.launch()
