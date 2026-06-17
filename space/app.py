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
# Tab 4 — Alignment Sensor (Compass)
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

        # --- Compass ---
        with gr.Tab("🧭 Compass"):
            gr.Markdown(
                "Select a conversation to see its alignment trajectory — "
                "task focus, rule compliance, and drift over time."
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
