---
title: AI Rule Learning
emoji: 🧠
colorFrom: blue
colorTo: purple
sdk: gradio
sdk_version: 5.29.0
python_version: '3.10'
app_file: app.py
pinned: false
license: mit
short_description: Autonomous system that learns rules from AI conversations
---

An autonomous system that intercepts AI conversations, detects behavioural gaps,
and generates guardrail rules — learning continuously without manual intervention.

## Features

- **Live Gap Detection** — sentiment drops, explicit corrections, repeated questions, code anti-patterns
- **Automatic Rule Generation** — rules are synthesised from recurring gap patterns
- **Rule Injection** — active rules are injected into system prompts before each AI response
- **Effectiveness Tracking** — rules are scored and deactivated if they stop working

## Architecture

```text
Conversation → Interceptor → Gap Detector → Rule Engine → HF Dataset
                    ↑                              ↓
              System Prompt  ←──────── Active Rules
```

## Source

GitHub: [faju85/AI_Rule_Learning](https://github.com/FAJU85/AI_Rule_Learning)
