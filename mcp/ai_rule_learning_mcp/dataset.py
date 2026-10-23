"""Export the learned rules corpus as a fine-tuning dataset (Phase 4).

This is the bridge to the optional, opt-in fine-tuning tier. It does NOT train
anything and adds no ML dependencies: training happens externally (e.g. Unsloth
on a GPU or free Colab T4) against the exported JSONL. See docs/fine-tuning.md.

Honest scope: each rule carries a directive (``instruction``) and, where it was
captured, the user's grounded correction (``evidence``). That supports a clean
*instruction-style* SFT dataset — examples that teach a model the user's standing
guardrails. The corpus does NOT store full before/after transcripts, so a true
DPO/preference dataset (chosen vs rejected completions) is deliberately NOT
fabricated here; constructing one would require before/after capture, which is a
prerequisite noted in the docs rather than invented from thin data.
"""

from __future__ import annotations

import json
from pathlib import Path

from .store import load_active_rules, scrub_pii

_SYSTEM = (
    "You are a coding assistant. Follow the user's established guardrail "
    "preferences in every response."
)


def _directive(rule: dict) -> str:
    action = rule.get("action")
    if isinstance(action, dict) and action.get("instruction"):
        return str(action["instruction"]).strip()
    return str(rule.get("instruction") or "").strip()


def _evidence_text(rule: dict) -> str:
    ev = rule.get("evidence")
    if isinstance(ev, dict):
        return str(ev.get("snippet") or ev.get("text") or ev.get("example") or "").strip()
    if isinstance(ev, str):
        return ev.strip()
    return ""


def build_sft_examples(rules: list[dict]) -> list[dict]:
    """Build instruction-style SFT examples (chat `messages` format) from rules.

    One example per rule that has a usable directive. When grounded evidence of
    the user's correction exists, it becomes the user turn (so the model learns
    the directive in the context that produced it); otherwise a neutral question
    about the preference is used. Rules without a directive are skipped. All text
    is PII-scrubbed defensively on the way out, even though the store already
    scrubs on write.
    """
    examples: list[dict] = []
    for rule in rules:
        directive = scrub_pii(_directive(rule))
        if not directive:
            continue
        name = str(rule.get("name") or rule.get("slot") or "guardrail")
        evidence = scrub_pii(_evidence_text(rule))
        if evidence:
            user_turn = evidence
        else:
            user_turn = f"What is my standing preference regarding {name.replace('-', ' ')}?"
        examples.append(
            {
                "messages": [
                    {"role": "system", "content": _SYSTEM},
                    {"role": "user", "content": user_turn},
                    {"role": "assistant", "content": directive},
                ]
            }
        )
    return examples


def export_sft_jsonl(out_path: str | Path, rules: list[dict] | None = None) -> int:
    """Write active rules as an SFT JSONL dataset. Returns the number of examples."""
    if rules is None:
        rules = load_active_rules()
    examples = build_sft_examples(rules)
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for example in examples:
            f.write(json.dumps(example, ensure_ascii=False) + "\n")
    return len(examples)
