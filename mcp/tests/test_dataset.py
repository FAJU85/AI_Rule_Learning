"""Tests for the fine-tuning dataset exporter (Phase 4)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ai_rule_learning_mcp.dataset import build_sft_examples, export_sft_jsonl


def _rule(name, instruction, evidence=None, priority=3):
    r = {
        "rule_id": f"rul_{name}",
        "name": name,
        "slot": name,
        "priority": priority,
        "instruction": instruction,
        "action": {"instruction": instruction},
    }
    if evidence is not None:
        r["evidence"] = evidence
    return r


class TestBuildSftExamples:
    def test_basic_shape_is_chat_messages(self):
        rules = [_rule("honor-type-hints", "Always include type hints.")]
        examples = build_sft_examples(rules)
        assert len(examples) == 1
        msgs = examples[0]["messages"]
        assert [m["role"] for m in msgs] == ["system", "user", "assistant"]
        assert msgs[-1]["content"] == "Always include type hints."

    def test_evidence_becomes_user_turn(self):
        rules = [_rule("x", "Always include type hints.", evidence={"snippet": "you forgot the type hints"})]
        msgs = build_sft_examples(rules)[0]["messages"]
        assert msgs[1]["content"] == "you forgot the type hints"

    def test_no_evidence_uses_preference_question(self):
        rules = [_rule("honor-user-preferences", "State the verdict first.")]
        msgs = build_sft_examples(rules)[0]["messages"]
        assert "honor user preferences" in msgs[1]["content"]

    def test_rule_without_directive_is_skipped(self):
        rules = [{"rule_id": "empty", "name": "empty", "instruction": "", "action": {}}]
        assert build_sft_examples(rules) == []

    def test_pii_is_scrubbed_on_export(self):
        rules = [_rule("x", "Email the report to john@example.com.", evidence="ping me at john@example.com")]
        msgs = build_sft_examples(rules)[0]["messages"]
        joined = msgs[1]["content"] + " " + msgs[2]["content"]
        assert "john@example.com" not in joined
        assert "[EMAIL]" in joined

    def test_prefers_action_instruction_over_instruction(self):
        rule = {
            "rule_id": "r",
            "name": "r",
            "instruction": "old text",
            "action": {"instruction": "new canonical text"},
        }
        msgs = build_sft_examples([rule])[0]["messages"]
        assert msgs[-1]["content"] == "new canonical text"


class TestExportJsonl:
    def test_writes_valid_jsonl(self, tmp_path):
        rules = [
            _rule("a", "Always include type hints."),
            _rule("b", "Stop being verbose."),
        ]
        out = tmp_path / "ds.jsonl"
        count = export_sft_jsonl(out, rules=rules)
        assert count == 2
        lines = out.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2
        for line in lines:
            obj = json.loads(line)
            assert "messages" in obj and len(obj["messages"]) == 3

    def test_empty_corpus_writes_no_lines(self, tmp_path):
        out = tmp_path / "ds.jsonl"
        count = export_sft_jsonl(out, rules=[])
        assert count == 0
        assert out.read_text(encoding="utf-8") == ""
