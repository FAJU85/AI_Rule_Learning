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
    turns = conv.get("turns", [])
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
# Seed rules — empirical rules derived from this project's session gap analysis
# ---------------------------------------------------------------------------

_SEED_RULES: list[dict] = [
    {
        "rule_id": "rule_verify_before_report",
        "name": "Verify live state before reporting",
        "description": "Before stating any system's status, query it live. Never report from memory or assumption.",
        "rule_type": "guardrail", "priority": 5,
        "trigger": {"keywords": ["status", "is it set", "do we have", "is there", "is the dataset", "is the token", "is running"]},
        "action": {"type": "modify_response", "instruction": "STOP. Query the live system before answering. Do not rely on memory or assumptions."},
        "is_active": True, "effectiveness_score": 1.0, "times_triggered": 0, "success_count": 0,
        "empirical_basis": "2 explicit user corrections — stale dataset and token status reports",
        "created_at": "2026-06-17T19:49:25.330561",
    },
    {
        "rule_id": "rule_confirm_scope_before_building",
        "name": "Confirm exact scope before implementing",
        "description": "Restate the interpreted scope (level, data source, target) in one sentence before writing any code.",
        "rule_type": "guardrail", "priority": 5,
        "trigger": {"keywords": ["add", "implement", "build", "create", "sensor", "dashboard", "monitor", "feature", "compass"]},
        "action": {"type": "modify_response", "instruction": "State in ONE sentence what you will build, at what level, using which data source. Ask if ambiguous."},
        "is_active": True, "effectiveness_score": 1.0, "times_triggered": 0, "success_count": 0,
        "empirical_basis": "2 explicit scope corrections — sensor level and demo-vs-real data",
        "created_at": "2026-06-17T19:49:25.330576",
    },
    {
        "rule_id": "rule_pre_validate_before_push",
        "name": "Run local validation before every push",
        "description": "Before git push: verify commit subject is lowercase ≤100 chars; run prettier --check; confirm staged files.",
        "rule_type": "guardrail", "priority": 4,
        "trigger": {"keywords": ["git push", "push", "commit", "pull request"]},
        "action": {"type": "modify_response", "instruction": "Verify commit subject is lowercase ≤100 chars; run prettier --check on changed YAML/JSON/MD; confirm staged files. Fix locally."},
        "is_active": True, "effectiveness_score": 1.0, "times_triggered": 0, "success_count": 0,
        "empirical_basis": "3 avoidable CI failures — uppercase TDD, Fix:, semgrep.yml",
        "created_at": "2026-06-17T19:49:25.330578",
    },
    {
        "rule_id": "rule_rebase_before_pr",
        "name": "Rebase on main before every PR",
        "description": "Always `git fetch origin main && git rebase origin/main` before pushing a PR branch.",
        "rule_type": "guardrail", "priority": 4,
        "trigger": {"keywords": ["pull request", "pr", "create pr", "merge", "push branch"]},
        "action": {"type": "modify_response", "instruction": "Before creating a PR: git fetch origin main && git rebase origin/main. Never open a PR from an unrebased branch."},
        "is_active": True, "effectiveness_score": 1.0, "times_triggered": 0, "success_count": 0,
        "empirical_basis": "3 merge-conflict failures on PRs #14, #15, #16",
        "created_at": "2026-06-17T19:49:25.330579",
    },
    {
        "rule_id": "rule_merge_immediately_no_wait",
        "name": "Merge within one minute — never wait for external services",
        "description": "Merge PRs immediately. Do not wait for CI or external services. Max wait: 60 seconds.",
        "rule_type": "guardrail", "priority": 5,
        "trigger": {"keywords": ["waiting", "wait for", "ci", "checks", "passing", "pending", "once ci"]},
        "action": {"type": "modify_response", "instruction": "Do NOT wait for CI or external services. Merge the PR immediately. If CI fails post-merge, diagnose and fix. Max wait: 60 seconds."},
        "is_active": True, "effectiveness_score": 1.0, "times_triggered": 0, "success_count": 0,
        "empirical_basis": "Explicit user rule: NEVER WAIT MORE THAN ONE MINUTE — MERGE THE PR IMMEDIATELY",
        "created_at": "2026-06-17T19:49:25.330582",
    },
    {
        "rule_id": "rule_rearm_monitors_on_timeout",
        "name": "Re-arm persistent monitors immediately on timeout",
        "description": "When any persistent monitor times out, re-arm it in the same turn before anything else.",
        "rule_type": "guardrail", "priority": 4,
        "trigger": {"keywords": ["monitor timed out", "timeout", "re-arm", "monitor expired"]},
        "action": {"type": "modify_response", "instruction": "Re-arm the monitor immediately — before responding about anything else. A dead monitor is a silent failure."},
        "is_active": True, "effectiveness_score": 1.0, "times_triggered": 0, "success_count": 0,
        "empirical_basis": "2 monitor timeout events that required user prompting to re-arm",
        "created_at": "2026-06-17T19:49:25.330583",
    },
    {
        "rule_id": "rule_fix_root_cause",
        "name": "Fix root cause — never patch symptoms",
        "description": "When CI fails, read the actual log, find the specific file and line, fix that file. No --no-verify, no ignore flags.",
        "rule_type": "guardrail", "priority": 3,
        "trigger": {"keywords": ["ci failed", "check failed", "lint failed", "error", "failure", "broken"]},
        "action": {"type": "modify_response", "instruction": "Read the full error log. Find the exact file and line. Fix that file. Never add --no-verify or ignore comments."},
        "is_active": True, "effectiveness_score": 1.0, "times_triggered": 0, "success_count": 0,
        "empirical_basis": "Pattern across 4 CI failures in this session",
        "created_at": "2026-06-17T19:49:25.330585",
    },
    {
        "rule_id": "rule_real_data_only",
        "name": "Connect to real data — never use placeholders in production",
        "description": "All dashboards and displays must connect to real data sources. No hardcoded samples.",
        "rule_type": "guardrail", "priority": 4,
        "trigger": {"keywords": ["dashboard", "chart", "graph", "display", "table", "visualization", "demo data", "sample data"]},
        "action": {"type": "modify_response", "instruction": "Connect every display to the real data source. If empty, show an empty-state message. Never hardcode sample rows."},
        "is_active": True, "effectiveness_score": 1.0, "times_triggered": 0, "success_count": 0,
        "empirical_basis": "Explicit user correction: 'i want real data not demo data'",
        "created_at": "2026-06-17T19:49:25.330586",
    },
]


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

        rule_data["rule_id"] = f"rule_{gap_type}_{uuid.uuid4().hex[:8]}"
        rule_data["is_active"] = True
        rule_data["effectiveness_score"] = 0.5
        rule_data["times_triggered"] = 0
        rule_data["success_count"] = 0
        rule_data["created_at"] = datetime.utcnow().isoformat()
        rule_data.setdefault("rule_type", "guardrail")
        rule_data.setdefault("priority", 3)
        rule_data.setdefault("severity", rule_data.get("priority", 3))
        rule_data.setdefault("empirical_basis", f"{len(examples)} observed {gap_type} instance(s)")

        return rule_data

    except Exception:
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
    total_turns = sum(len(c.get("turns", [])) for c in conversations)
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

def run_force_reanalyze():
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

    yield from run_analysis()


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
                    "user_input": messages[i]["text"][:4000],
                    "agent_response": messages[j]["text"][:4000],
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
        "project_context": session_meta.get("cwd", ""),
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

            gr.Markdown("---\n### 📤 Export as System Prompt\nCopy this block into any AI system prompt to apply your active rules immediately.")
            export_btn = gr.Button("Generate System Prompt", variant="primary", size="sm")
            system_prompt_output = gr.Textbox(
                label="System prompt — copy and paste into any AI",
                lines=20,
                interactive=True,
                show_copy_button=True,
            )
            export_btn.click(export_system_prompt, outputs=system_prompt_output)
            demo.load(export_system_prompt, outputs=system_prompt_output)

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

        # --- Import Live Sessions ---
        with gr.Tab("📥 Import Sessions"):
            gr.Markdown(
                """
## Import Claude Code Live Sessions

Upload session JSONL files exported directly from Claude Code's local storage —
**no Anthropic API key required**.

### How to export sessions from your machine

```bash
# Export all sessions from this project
python scripts/export_sessions.py --dry-run   # preview
python scripts/export_sessions.py             # upload directly to dataset

# Or export a specific session
python scripts/export_sessions.py --session <session-id>
```

The script reads `~/.claude/projects/` on your local machine and uploads
conversations to the HF dataset. The Space then picks them up automatically.

### Or: upload JSONL files manually here

If you have the raw Claude Code session JSONL files, upload them directly below.
Each file is one session (e.g. `be6d062b-eb09-5398-b69a-1cdfa8f3c5b7.jsonl`).

The importer extracts user↔assistant turn pairs, strips internal tool calls
and webhook notifications, and merges into the conversation dataset.
"""
            )
            session_files_input = gr.File(
                label="Upload Claude Code session JSONL file(s)",
                file_types=[".jsonl"],
                file_count="multiple",
            )
            import_btn = gr.Button("📥 Import Sessions", variant="primary", size="lg")
            import_log = gr.Textbox(
                label="Import log",
                lines=12,
                interactive=False,
                autoscroll=True,
            )
            import_btn.click(run_import_sessions, inputs=session_files_input, outputs=import_log)

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
                reanalyze_btn = gr.Button("🔁 Force Re-analyze All", variant="primary", size="lg")
            with gr.Row():
                evolve_btn = gr.Button("🔄 Validate & Evolve", variant="secondary", size="lg")
                seed_btn = gr.Button("🌱 Seed Work Rules", variant="secondary", size="lg")
            gr.Markdown(
                "_**▶ Run Analysis** processes only new conversations. "
                "**🔁 Force Re-analyze All** clears the checkpoint and reprocesses every "
                "conversation — use this after the gap detection was improved._"
            )
            analysis_log = gr.Textbox(
                label="Analysis log",
                lines=20,
                interactive=False,
                autoscroll=True,
            )
            analysis_btn.click(run_analysis, outputs=analysis_log)
            reanalyze_btn.click(run_force_reanalyze, outputs=analysis_log)
            evolve_btn.click(run_validate_and_evolve, outputs=analysis_log)
            seed_btn.click(run_seed_rules, outputs=analysis_log)

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
## How to Use These Rules with Any AI

### Step 1 — Generate rules from your conversations

1. Upload your Claude Code session files in the **📥 Import Sessions** tab
2. Click **🔁 Force Re-analyze All** in the **🔍 Analysis** tab to scan all conversations
3. The system detects gaps and calls `Qwen/Qwen2.5-72B-Instruct` to generate guardrail rules

### Step 2 — Export the system prompt

Go to **📋 Rules** → click **Generate System Prompt** → copy the output.

### Step 3 — Apply to any AI

Paste the system prompt into:
- **Claude** — Project instructions or system prompt in Claude.ai
- **ChatGPT / OpenAI API** — `system` message in the messages array
- **Any API** — `{"role": "system", "content": "<paste here>"}`
- **Claude Code** — Add to `CLAUDE.md` in your project root

### Auto-export from Claude Code sessions

The Stop hook auto-exports sessions when a session ends. Set `HF_TOKEN` in your shell:

```bash
export HF_TOKEN=your_hf_token
# Now every Claude Code session auto-uploads to the dataset on exit
```

### Fetch rules programmatically

```python
from huggingface_hub import hf_hub_download
import json

path = hf_hub_download("vooom/AI_Rule_Learning", "rules.jsonl", repo_type="dataset", token="your_token")
rules = [json.loads(l) for l in open(path) if l.strip()]
active = [r for r in rules if r.get("is_active")]
```

## Source

[github.com/FAJU85/AI_Rule_Learning](https://github.com/FAJU85/AI_Rule_Learning)
"""
            )

if __name__ == "__main__":
    demo.launch()
