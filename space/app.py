"""Gradio dashboard for the AI Rule Learning System."""

import json
from datetime import datetime, timedelta
from typing import Any

import gradio as gr
import pandas as pd
import plotly.graph_objects as go

# ---------------------------------------------------------------------------
# Demo data — used when no live HF dataset is connected
# ---------------------------------------------------------------------------

DEMO_RULES = [
    {
        "rule_id": "rule_sentiment_a1b2c3d4",
        "name": "Empathy Prefix on Frustration",
        "description": "Start with empathy when user sentiment drops sharply",
        "rule_type": "guardrail",
        "priority": 4,
        "is_active": True,
        "effectiveness_score": 0.82,
        "times_triggered": 47,
        "success_count": 39,
        "action": {"type": "add_prefix", "instruction": "Begin with empathy statement"},
        "trigger": {"sentiment_threshold": -0.3, "keywords": []},
        "created_at": (datetime.now() - timedelta(days=12)).isoformat(),
    },
    {
        "rule_id": "rule_correction_e5f6g7h8",
        "name": "Clarification Before Responding",
        "description": "Ask clarifying question when correction phrases detected",
        "rule_type": "guardrail",
        "priority": 5,
        "is_active": True,
        "effectiveness_score": 0.71,
        "times_triggered": 31,
        "success_count": 22,
        "action": {"type": "modify_tone", "instruction": "Verify understanding first"},
        "trigger": {"keywords": ["wrong", "incorrect", "fix", "actually", "instead"]},
        "created_at": (datetime.now() - timedelta(days=8)).isoformat(),
    },
    {
        "rule_id": "rule_code_i9j0k1l2",
        "name": "Error Handling Enforcement",
        "description": "Always include error handling in code suggestions",
        "rule_type": "semgrep",
        "priority": 5,
        "is_active": True,
        "effectiveness_score": 0.91,
        "times_triggered": 63,
        "success_count": 58,
        "action": {"type": "modify_response", "instruction": "Include try/except and input validation"},
        "trigger": {"keywords": ["database", "api", "query", "execute"], "topics": ["code_generation"]},
        "created_at": (datetime.now() - timedelta(days=5)).isoformat(),
    },
    {
        "rule_id": "rule_correction_m3n4o5p6",
        "name": "Repeated Question Escalation",
        "description": "Offer human handoff when user repeats the same question",
        "rule_type": "guardrail",
        "priority": 4,
        "is_active": True,
        "effectiveness_score": 0.65,
        "times_triggered": 18,
        "success_count": 12,
        "action": {"type": "escalate", "instruction": "Offer human transfer after 2 repeats"},
        "trigger": {"keywords": ["again", "still", "repeat", "same question"]},
        "created_at": (datetime.now() - timedelta(days=3)).isoformat(),
    },
    {
        "rule_id": "rule_sentiment_q7r8s9t0",
        "name": "Conciseness on Simple Queries",
        "description": "Keep responses short for simple lookup questions",
        "rule_type": "guardrail",
        "priority": 2,
        "is_active": False,
        "effectiveness_score": 0.12,
        "times_triggered": 29,
        "success_count": 4,
        "action": {"type": "enforce_conciseness", "instruction": "Max 3 sentences for simple queries"},
        "trigger": {"keywords": ["what is", "define", "meaning of"]},
        "created_at": (datetime.now() - timedelta(days=15)).isoformat(),
    },
]

DEMO_GAPS = [
    {"type": "sentiment_drop", "severity": 4, "count": 12, "last_seen": "2 hours ago"},
    {"type": "explicit_correction", "severity": 5, "count": 8, "last_seen": "4 hours ago"},
    {"type": "code_anti_pattern", "severity": 5, "count": 6, "last_seen": "1 day ago"},
    {"type": "repeated_question", "severity": 3, "count": 4, "last_seen": "2 days ago"},
]

DEMO_CONVERSATIONS = [
    {
        "id": "conv-001",
        "turns": 7,
        "gaps": 2,
        "rules_applied": 3,
        "outcome": "escalated",
        "date": (datetime.now() - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M"),
    },
    {
        "id": "conv-002",
        "turns": 4,
        "gaps": 0,
        "rules_applied": 1,
        "outcome": "resolved",
        "date": (datetime.now() - timedelta(hours=5)).strftime("%Y-%m-%d %H:%M"),
    },
    {
        "id": "conv-003",
        "turns": 11,
        "gaps": 3,
        "rules_applied": 4,
        "outcome": "resolved",
        "date": (datetime.now() - timedelta(hours=8)).strftime("%Y-%m-%d %H:%M"),
    },
    {
        "id": "conv-004",
        "turns": 3,
        "gaps": 1,
        "rules_applied": 2,
        "outcome": "resolved",
        "date": (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M"),
    },
    {
        "id": "conv-005",
        "turns": 9,
        "gaps": 4,
        "rules_applied": 3,
        "outcome": "human_transfer",
        "date": (datetime.now() - timedelta(days=1, hours=3)).strftime("%Y-%m-%d %H:%M"),
    },
]


# ---------------------------------------------------------------------------
# Tab 1 — Overview dashboard
# ---------------------------------------------------------------------------

def build_overview() -> tuple[Any, Any, str]:
    active = [r for r in DEMO_RULES if r["is_active"]]
    total_triggers = sum(r["times_triggered"] for r in active)
    avg_eff = sum(r["effectiveness_score"] for r in active) / max(len(active), 1)

    # Effectiveness bar chart
    fig_eff = go.Figure(
        go.Bar(
            x=[r["name"][:30] for r in DEMO_RULES],
            y=[r["effectiveness_score"] for r in DEMO_RULES],
            marker_color=["#22c55e" if r["is_active"] else "#94a3b8" for r in DEMO_RULES],
            text=[f"{r['effectiveness_score']:.0%}" for r in DEMO_RULES],
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

    # Gap type pie chart
    fig_gaps = go.Figure(
        go.Pie(
            labels=[g["type"].replace("_", " ").title() for g in DEMO_GAPS],
            values=[g["count"] for g in DEMO_GAPS],
            hole=0.4,
        )
    )
    fig_gaps.update_layout(
        title="Gap Distribution",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        height=350,
    )

    summary = f"""
### System Summary

| Metric | Value |
|--------|-------|
| Active rules | {len(active)} / {len(DEMO_RULES)} |
| Total rule triggers | {total_triggers} |
| Average effectiveness | {avg_eff:.0%} |
| Conversations analysed | {len(DEMO_CONVERSATIONS)} |
| Gaps detected (last 7 days) | {sum(g['count'] for g in DEMO_GAPS)} |
"""
    return fig_eff, fig_gaps, summary


# ---------------------------------------------------------------------------
# Tab 2 — Rules table
# ---------------------------------------------------------------------------

def build_rules_table() -> pd.DataFrame:
    rows = []
    for r in DEMO_RULES:
        rows.append(
            {
                "Status": "✅ Active" if r["is_active"] else "⛔ Inactive",
                "Name": r["name"],
                "Type": r["rule_type"].upper(),
                "Priority": "⭐" * r["priority"],
                "Triggered": r["times_triggered"],
                "Effectiveness": f"{r['effectiveness_score']:.0%}",
                "Action": r["action"]["type"].replace("_", " ").title(),
                "Created": r["created_at"][:10],
            }
        )
    return pd.DataFrame(rows)


def get_rule_detail(rule_name: str) -> str:
    rule = next((r for r in DEMO_RULES if r["name"] == rule_name), None)
    if not rule:
        return "Select a rule from the table above."
    success_rate = rule["success_count"] / max(rule["times_triggered"], 1)
    return f"""
**{rule['name']}**

- **ID**: `{rule['rule_id']}`
- **Type**: {rule['rule_type']}
- **Priority**: {rule['priority']} / 5
- **Status**: {'✅ Active' if rule['is_active'] else '⛔ Inactive'}

**Trigger**: {json.dumps(rule['trigger'], indent=2)}

**Action**: {json.dumps(rule['action'], indent=2)}

**Performance**:
- Times triggered: {rule['times_triggered']}
- Success rate: {success_rate:.0%}
- Effectiveness score: {rule['effectiveness_score']:.0%}
"""


# ---------------------------------------------------------------------------
# Tab 3 — Gap simulator
# ---------------------------------------------------------------------------

def simulate_gap(user_message: str) -> tuple[str, str]:
    msg_lower = user_message.lower()

    detected_gaps = []
    matched_rules = []

    # Detect gaps
    correction_phrases = ["wrong", "incorrect", "fix", "actually", "instead", "no,", "that's not"]
    if any(p in msg_lower for p in correction_phrases):
        detected_gaps.append("🔴 **explicit_correction** (severity 5) — Correction phrase detected")
        matched_rules.append(DEMO_RULES[1])

    code_phrases = ["database", "api", "query", "execute", "sql", "request"]
    if any(p in msg_lower for p in code_phrases):
        detected_gaps.append("🟡 **code_anti_pattern** (severity 4) — Code-related request")
        matched_rules.append(DEMO_RULES[2])

    if "?" in user_message and len(user_message) < 40:
        detected_gaps.append("🟢 **simple_query** (severity 1) — Short question detected")

    gap_output = "\n".join(detected_gaps) if detected_gaps else "✅ No gaps detected"

    # Build injected system prompt
    if matched_rules:
        rules_text = []
        for rule in matched_rules:
            rules_text.append(f"- **RULE [{rule['priority']}/5]**: {rule['action']['instruction']}")
        prompt = "**System prompt with injected rules:**\n\n" + "You are a helpful AI assistant.\n\n## ACTIVE RULES\n" + "\n".join(
            rules_text
        )
    else:
        prompt = "**System prompt (no rules matched):**\n\nYou are a helpful AI assistant."

    return gap_output, prompt


# ---------------------------------------------------------------------------
# Tab 4 — Architecture
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

## Components

- **`ConversationInterceptor`** — orchestrates pre/post hooks per turn
- **`RuleEngine`** — matches rules by keyword, topic, embedding similarity
- **`GapDetector`** — analyses turns for behavioural failures
- **`AnalysisService`** — batch analysis → rule generation
- **`ValidationService`** — effectiveness scoring, auto-deactivation
- **`DatasetManager`** — HuggingFace Hub CRUD for conversations and rules
"""


# ---------------------------------------------------------------------------
# Build Gradio app
# ---------------------------------------------------------------------------

with gr.Blocks(title="AI Rule Learning System", theme=gr.themes.Soft()) as demo:
    gr.Markdown(
        """
# 🧠 AI Rule Learning System
**Autonomous guardrail generation from conversation patterns**

> This dashboard shows a demo with sample data. Connect your HuggingFace dataset to see live rules and gaps.
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
                fig_eff, fig_gaps, summary = build_overview()
                return fig_eff, fig_gaps, summary

            refresh_btn.click(refresh_overview, outputs=[eff_chart, gaps_chart, summary_md])
            demo.load(refresh_overview, outputs=[eff_chart, gaps_chart, summary_md])

        # --- Rules ---
        with gr.Tab("📋 Rules"):
            rules_table = gr.Dataframe(
                value=build_rules_table(),
                interactive=False,
                wrap=True,
            )
            rule_selector = gr.Dropdown(
                choices=[r["name"] for r in DEMO_RULES],
                label="Select rule for details",
            )
            rule_detail = gr.Markdown()
            rule_selector.change(get_rule_detail, inputs=rule_selector, outputs=rule_detail)

        # --- Gap Simulator ---
        with gr.Tab("🔬 Gap Simulator"):
            gr.Markdown(
                "Type a user message below to see which gaps would be detected and which rules would be injected."
            )
            with gr.Row():
                sim_input = gr.Textbox(
                    label="User message",
                    placeholder="e.g. That's wrong, you forgot error handling in the database query",
                    lines=3,
                )
            sim_btn = gr.Button("Simulate", variant="primary")
            with gr.Row():
                gap_output = gr.Markdown(label="Detected gaps")
                prompt_output = gr.Markdown(label="Injected system prompt")

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

## Docker

```bash
docker-compose up
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `python -m src.cli.main chat` | Interactive conversation with rule injection |
| `python -m src.cli.main analyze --days 7` | Analyse last 7 days, generate rules |
| `python -m src.cli.main validate` | Score and prune ineffective rules |
| `python -m src.cli.main list-rules` | Show all active rules |
| `python scripts/upload_historical.py --file data.json` | Bulk upload conversations |

## Environment Variables

```env
HF_TOKEN=your_hf_token
HF_DATASET_NAME=your-org/conversation-memory
HF_RULES_DATASET=your-org/active-rules
OPENAI_API_KEY=your_openai_key        # or
ANTHROPIC_API_KEY=your_anthropic_key
```

## Source

[github.com/FAJU85/AI_Rule_Learning](https://github.com/FAJU85/AI_Rule_Learning)
"""
            )

if __name__ == "__main__":
    demo.launch()
