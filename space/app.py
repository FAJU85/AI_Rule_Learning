"""Gradio dashboard for the AI Rule Learning System."""

import csv
import io
import json
import os
import uuid
from datetime import datetime
from typing import Any

import gradio as gr
import pandas as pd
import plotly.graph_objects as go
from huggingface_hub import HfApi, hf_hub_download
from huggingface_hub.errors import EntryNotFoundError, RepositoryNotFoundError

# ---------------------------------------------------------------------------
# HF dataset connection
# ---------------------------------------------------------------------------

DATASET_ID = "vooom/AI_Rule_Learning"
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
"""


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
    "wrong", "incorrect", "that's not", "no,", "actually,", "instead,",
    "you're wrong", "not right", "fix this", "that is wrong", "no that",
    "you missed", "you forgot", "not what i", "not what I",
]
_CODE_ANTIPATTERNS = ["eval(", "exec(", "password =", "secret =", "hardcoded", "bare except", "except:"]
_HF_MODEL = "Qwen/Qwen2.5-72B-Instruct"


def _word_overlap(a: str, b: str) -> float:
    wa, wb = set(a.lower().split()), set(b.lower().split())
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / max(len(wa), len(wb))


def _detect_gaps_in_conversation(conv: dict) -> list[dict]:
    gaps = []
    turns = conv.get("turns", [])
    seen_inputs: list[str] = []

    for turn in turns:
        user_input = turn.get("user_input", "")
        agent_response = turn.get("agent_response", "")
        turn_n = turn.get("turn_number", len(seen_inputs) + 1)
        ui_lower = user_input.lower()
        ar_lower = agent_response.lower()

        # Explicit correction
        if any(p in ui_lower for p in _CORRECTION_PHRASES):
            gaps.append({
                "type": "explicit_correction",
                "severity": 5,
                "turn": turn_n,
                "description": "User explicitly corrected the AI",
                "user_input": user_input[:120],
            })

        # Repeated question (word overlap with any prior turn)
        for prev in seen_inputs[-5:]:
            if _word_overlap(ui_lower, prev) > 0.65 and len(user_input.split()) > 3:
                gaps.append({
                    "type": "repeated_question",
                    "severity": 3,
                    "turn": turn_n,
                    "description": "User repeated a similar question",
                    "user_input": user_input[:120],
                })
                break

        # Code anti-pattern in response
        if any(p in ar_lower for p in _CODE_ANTIPATTERNS):
            gaps.append({
                "type": "code_anti_pattern",
                "severity": 5,
                "turn": turn_n,
                "description": "Potentially unsafe pattern in AI response",
                "user_input": user_input[:120],
            })

        # Sentiment drop (if fields present)
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
                        "user_input": user_input[:120],
                    })
            except (ValueError, TypeError):
                pass

        seen_inputs.append(ui_lower)

    return gaps


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


def _generate_rule_hf(gap_type: str, examples: list[dict]) -> dict | None:
    try:
        import re
        from huggingface_hub import InferenceClient

        client = InferenceClient(token=HF_TOKEN)
        examples_text = "\n".join(
            f"- Turn {e.get('turn', '?')}: {e.get('description', '')} | user said: \"{e.get('user_input', '')[:80]}\""
            for e in examples[:4]
        )

        prompt = f"""You are an AI guardrail rule generator. Analyze these conversation gaps and create a guardrail rule.

Gap type: {gap_type}
Observed examples:
{examples_text}

Return ONLY a valid JSON object with exactly these fields:
{{
  "name": "Short descriptive rule name (max 8 words)",
  "description": "What behaviour this rule prevents or encourages",
  "rule_type": "guardrail",
  "priority": 4,
  "action": {{
    "type": "modify_response",
    "instruction": "Specific, actionable instruction for the AI assistant"
  }},
  "trigger": {{
    "keywords": ["keyword1", "keyword2", "keyword3"]
  }}
}}

Only output the JSON. No explanation, no markdown fences."""

        response = client.chat.completions.create(
            model=_HF_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=400,
            temperature=0.3,
        )
        text = response.choices[0].message.content.strip()

        # Strip markdown fences if present
        text = re.sub(r"^```[a-z]*\n?", "", text).rstrip("`").strip()

        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return None

        rule_data = json.loads(match.group())

        rule_data["rule_id"] = f"rule_{gap_type}_{uuid.uuid4().hex[:8]}"
        rule_data["is_active"] = True
        rule_data["effectiveness_score"] = 0.5
        rule_data["times_triggered"] = 0
        rule_data["success_count"] = 0
        rule_data["created_at"] = datetime.utcnow().isoformat()
        rule_data.setdefault("rule_type", "guardrail")
        rule_data.setdefault("priority", 3)

        return rule_data

    except Exception as exc:
        return None


def run_analysis():
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
    yield emit(f"✅ Found **{total_gaps}** gaps across **{len(conv_gap_map)}** new conversations:")
    for gtype, gaps in sorted(all_gaps_by_type.items(), key=lambda x: -len(x[1])):
        yield emit(f"   • `{gtype}`: {len(gaps)} occurrence{'s' if len(gaps) != 1 else ''}")

    # --- Annotate conversations with detected gaps and save ---
    if conv_gap_map:
        yield emit("\n💾 Annotating conversations with gap data…")
        for conv in conversations:
            cid = conv.get("conversation_id", "?")
            if cid in conv_gap_map:
                gaps_by_turn = {}
                for g in conv_gap_map[cid]:
                    gaps_by_turn.setdefault(g["turn"], []).append(g)
                for turn in conv.get("turns", []):
                    tn = turn.get("turn_number")
                    if tn in gaps_by_turn:
                        turn["gaps_detected"] = gaps_by_turn[tn]
        try:
            _upload_jsonl("conversations.jsonl", conversations)
            yield emit("✅ Conversations updated in dataset")
        except Exception as exc:
            yield emit(f"⚠️ Could not save gap annotations: {exc}")

    # --- Rule generation ---
    eligible = {
        k: v for k, v in all_gaps_by_type.items()
        if len(v) >= 2 and k not in generated_rule_types
    }
    if not eligible:
        yield emit("\nℹ️ No new gap types to generate rules for. Done.")
        # Save final checkpoint so resume is instant next time
        _save_checkpoint({
            "processed_ids": list(processed_ids),
            "all_gaps_by_type": all_gaps_by_type,
            "generated_rule_types": list(generated_rule_types),
        })
        return

    yield emit(f"\n🤖 Generating rules for **{len(eligible)}** gap type(s) using `{_HF_MODEL}`…")

    existing_rules = load_rules()
    new_rules: list[dict] = []

    for gtype, gap_examples in eligible.items():
        yield emit(f"\n   ⚙️ `{gtype}` ({len(gap_examples)} examples) — calling HF Inference API…")
        rule = _generate_rule_hf(gtype, gap_examples)
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
        evolved["is_active"] = True
        evolved["effectiveness_score"] = 0.5
        evolved["times_triggered"] = 0
        evolved["success_count"] = 0
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
            deactivated.append(name)
            yield emit(f"   🚫 Deactivated (score {score:.0%} < {_DEACTIVATION_THRESHOLD:.0%} with {triggered} triggers)")
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
# Build Gradio app
# ---------------------------------------------------------------------------

with gr.Blocks(title="AI Rule Learning System", theme=gr.themes.Soft()) as demo:
    gr.Markdown(
        """
# 🧠 AI Rule Learning System
**Autonomous guardrail generation from conversation patterns**

> Connected to dataset: [`vooom/AI_Rule_Learning`](https://huggingface.co/datasets/vooom/AI_Rule_Learning)
"""
    )

    with gr.Tabs():
        # --- Overview ---
        with gr.Tab("📊 Overview"):
            with gr.Row():
                eff_chart = gr.Plot(label="Rule Effectiveness")
                gaps_chart = gr.Plot(label="Gap Distribution")
            summary_md = gr.Markdown()
            refresh_btn = gr.Button("🔄 Refresh", variant="secondary", size="sm")

            def refresh_overview():
                return build_overview()

            refresh_btn.click(refresh_overview, outputs=[eff_chart, gaps_chart, summary_md])
            demo.load(refresh_overview, outputs=[eff_chart, gaps_chart, summary_md])

        # --- Rules ---
        with gr.Tab("📋 Rules"):
            rules_table = gr.Dataframe(interactive=False, wrap=True)
            refresh_rules_btn = gr.Button("🔄 Refresh", variant="secondary", size="sm")
            rule_selector = gr.Dropdown(label="Select rule for details", choices=[])
            rule_detail = gr.Markdown()

            def refresh_rules():
                return build_rules_table(), gr.Dropdown(choices=get_rule_names())

            refresh_rules_btn.click(refresh_rules, outputs=[rules_table, rule_selector])
            demo.load(refresh_rules, outputs=[rules_table, rule_selector])
            rule_selector.change(get_rule_detail, inputs=rule_selector, outputs=rule_detail)

        # --- Conversations ---
        with gr.Tab("💬 Conversations"):
            conversations_table = gr.Dataframe(interactive=False, wrap=True)
            refresh_convs_btn = gr.Button("🔄 Refresh", variant="secondary", size="sm")

            def refresh_conversations():
                return build_conversations_table()

            refresh_convs_btn.click(refresh_conversations, outputs=[conversations_table])
            demo.load(refresh_conversations, outputs=[conversations_table])

        # --- Upload History ---
        with gr.Tab("📤 Upload History"):
            gr.Markdown(
                """
## Upload Conversation History

Upload a **JSON** or **CSV** file containing past conversations.

### JSON format
```json
[
  {
    "conversation_id": "optional",
    "turns": [
      {"turn_number": 1, "user_input": "Hello", "agent_response": "Hi!"},
      {"turn_number": 2, "user_input": "...", "agent_response": "..."}
    ]
  }
]
```

### CSV format
One row per turn, columns: `conversation_id, turn_number, user_input, agent_response`
Optional columns: `session_id, user_id, sentiment_before, sentiment_after`
"""
            )
            upload_file = gr.File(
                label="Select JSON or CSV file",
                file_types=[".json", ".csv"],
            )
            upload_btn = gr.Button("Upload to Dataset", variant="primary")
            upload_status = gr.Markdown()

            upload_btn.click(upload_history, inputs=upload_file, outputs=upload_status)

        # --- Analysis ---
        with gr.Tab("🔍 Analysis"):
            gr.Markdown(
                """
## Run Analysis

Scans all uploaded conversations for behavioural gaps, then uses
**`Qwen/Qwen2.5-72B-Instruct`** via the HF Inference API to generate
guardrail rules automatically.

- **Ralph Loop** checkpointing: analysis is resumable if the Space times out mid-run
- Detects: explicit corrections, repeated questions, code anti-patterns, sentiment drops
- Requires ≥2 occurrences of a gap type before generating a rule
- Rules are saved directly to the dataset and appear in the **Rules** tab

---

**🔄 Validate & Evolve** uses the Mengram feedback pattern: instead of just
deactivating low-performing rules (< 30% effectiveness), it rewrites them with the
AI model so they improve rather than disappear.
"""
            )
            with gr.Row():
                analysis_btn = gr.Button("▶ Run Analysis", variant="primary", size="lg")
                evolve_btn = gr.Button("🔄 Validate & Evolve", variant="secondary", size="lg")
            analysis_log = gr.Textbox(
                label="Analysis log",
                lines=20,
                interactive=False,
                autoscroll=True,
            )
            analysis_btn.click(run_analysis, outputs=analysis_log)
            evolve_btn.click(run_validate_and_evolve, outputs=analysis_log)

        # --- Project Compass ---
        with gr.Tab("🧭 Project Compass"):
            gr.Markdown(
                "**Project-level health sensor** — tracks whether the deployed Space, "
                "dataset, rule system, and workflow are all moving in the right direction."
            )
            with gr.Row():
                proj_gauge = gr.Plot(label="Health Score")
                proj_metrics = gr.Plot(label="Score Breakdown")
            proj_summary = gr.Markdown()
            proj_refresh_btn = gr.Button("🔄 Refresh", variant="secondary", size="sm")

            def refresh_project_compass():
                return build_project_compass()

            proj_refresh_btn.click(refresh_project_compass,
                                   outputs=[proj_gauge, proj_metrics, proj_summary])
            demo.load(refresh_project_compass,
                      outputs=[proj_gauge, proj_metrics, proj_summary])

        # --- Alignment Sensor ---
        with gr.Tab("📐 Alignment"):
            gr.Markdown(
                "Per-conversation alignment sensor — task focus, rule compliance, "
                "and semantic drift across turns."
            )
            with gr.Row():
                conv_selector = gr.Dropdown(label="Conversation", choices=[], scale=3)
                refresh_compass_btn = gr.Button("🔄 Refresh list", variant="secondary", size="sm", scale=1)

            with gr.Row():
                compass_gauge = gr.Plot(label="Alignment Score")
                compass_timeline = gr.Plot(label="Timeline")

            compass_alerts = gr.Markdown()

            def refresh_compass_list():
                return gr.Dropdown(choices=get_conversation_ids())

            refresh_compass_btn.click(refresh_compass_list, outputs=[conv_selector])
            demo.load(refresh_compass_list, outputs=[conv_selector])
            conv_selector.change(build_compass, inputs=conv_selector,
                                 outputs=[compass_gauge, compass_timeline, compass_alerts])

        # --- Gap Simulator ---
        with gr.Tab("🔬 Gap Simulator"):
            gr.Markdown(
                "Type a user message below to see which gaps would be detected and which rules would be injected."
            )
            sim_input = gr.Textbox(
                label="User message",
                placeholder="e.g. That's wrong, you forgot error handling in the database query",
                lines=3,
            )
            sim_btn = gr.Button("Simulate", variant="primary")
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
                    ["What is the capital of France?"],
                ],
                inputs=sim_input,
            )

        # --- Architecture ---
        with gr.Tab("🏗️ Architecture"):
            gr.Markdown(ARCHITECTURE_MD)

        # --- Quick Start ---
        with gr.Tab("🚀 Quick Start"):
            gr.Markdown(
                """
## Run Locally

```bash
git clone https://github.com/FAJU85/AI_Rule_Learning.git
cd AI_Rule_Learning
pip install -r requirements.txt
cp .env.example .env
# Add your API keys to .env
python -m src.cli.main chat
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `python -m src.cli.main chat` | Interactive conversation with rule injection |
| `python -m src.cli.main analyze --days 7` | Analyse last 7 days, generate rules |
| `python -m src.cli.main validate` | Score and prune ineffective rules |
| `python -m src.cli.main list-rules` | Show all active rules |
| `python scripts/upload_historical.py --file data.json` | Bulk upload conversations via CLI |

## Environment Variables

```env
HF_TOKEN=your_hf_token
HF_DATASET_NAME=vooom/AI_Rule_Learning
OPENAI_API_KEY=your_openai_key        # or
ANTHROPIC_API_KEY=your_anthropic_key
```

## Source

[github.com/FAJU85/AI_Rule_Learning](https://github.com/FAJU85/AI_Rule_Learning)
"""
            )

if __name__ == "__main__":
    demo.launch()
