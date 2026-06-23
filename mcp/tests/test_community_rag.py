"""Tests for the RAG-powered community feedback loop.

All HF calls are mocked — no real network requests.
"""

from __future__ import annotations

import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# fetch_community_patterns
# ---------------------------------------------------------------------------

def test_fetch_community_patterns_no_token():
    """Returns {} when HF_TOKEN is not set."""
    import ai_rule_learning_mcp.community as community

    original = community.HF_TOKEN
    community.HF_TOKEN = ""
    try:
        result = community.fetch_community_patterns()
        assert result == {}
    finally:
        community.HF_TOKEN = original


def test_fetch_community_patterns_aggregates():
    """Aggregates count, unique_sources, and top_signals correctly."""
    records = [
        {
            "source_hash": "aaa",
            "gap_patterns": {
                "explicit_correction": [
                    {"type": "explicit_correction", "severity": 1, "turn": 1, "signal": "actually,"},
                    {"type": "explicit_correction", "severity": 1, "turn": 3, "signal": "actually,"},
                ]
            },
        },
        {
            "source_hash": "bbb",
            "gap_patterns": {
                "explicit_correction": [
                    {"type": "explicit_correction", "severity": 2, "turn": 2, "signal": "no,"},
                ]
            },
        },
        {
            "source_hash": "ccc",
            "gap_patterns": {
                "explicit_correction": [
                    {"type": "explicit_correction", "severity": 1, "turn": 1, "signal": "actually,"},
                ]
            },
        },
    ]

    jsonl = "\n".join(json.dumps(r) for r in records) + "\n"

    import ai_rule_learning_mcp.community as community

    original_token = community.HF_TOKEN
    community.HF_TOKEN = "fake-token"
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(jsonl)
            tmp_path = f.name

        with patch("huggingface_hub.hf_hub_download", return_value=tmp_path):
            result = community.fetch_community_patterns()
    finally:
        community.HF_TOKEN = original_token
        os.unlink(tmp_path)

    assert "explicit_correction" in result
    ec = result["explicit_correction"]
    assert ec["count"] == 4          # 2 + 1 + 1
    assert ec["unique_sources"] == 3  # aaa, bbb, ccc
    assert "actually," in ec["top_signals"]
    assert "no," in ec["top_signals"]


# ---------------------------------------------------------------------------
# build_community_templates
# ---------------------------------------------------------------------------

def test_build_community_templates_threshold():
    """Only gap_types with unique_sources >= min_sources generate templates."""
    freq = {
        "explicit_correction": {"count": 10, "unique_sources": 4, "top_signals": ["actually,"]},
        "overconfidence": {"count": 5, "unique_sources": 2, "top_signals": ["i guarantee"]},
    }

    import ai_rule_learning_mcp.community as community

    original_token = community.HF_TOKEN
    community.HF_TOKEN = "fake-token"
    try:
        with patch.object(community, "fetch_community_patterns", return_value=freq):
            templates = community.build_community_templates(min_sources=3)
    finally:
        community.HF_TOKEN = original_token

    gap_types = [t["gap_type"] for t in templates]
    assert "explicit_correction" in gap_types
    assert "overconfidence" not in gap_types


def test_build_community_templates_enhances_builtin():
    """For a known gap_type, template inherits builtin instruction and adds new signals."""
    freq = {
        "explicit_correction": {
            "count": 10,
            "unique_sources": 5,
            "top_signals": ["actually,", "community_signal_xyz"],
        },
    }

    import ai_rule_learning_mcp.community as community

    original_token = community.HF_TOKEN
    community.HF_TOKEN = "fake-token"
    try:
        with patch.object(community, "fetch_community_patterns", return_value=freq):
            templates = community.build_community_templates(min_sources=3)
    finally:
        community.HF_TOKEN = original_token

    assert len(templates) == 1
    tpl = templates[0]
    assert tpl["source"] == "community_enhanced"
    assert tpl["gap_type"] == "explicit_correction"
    # Inherits builtin instruction
    assert "acknowledge" in tpl["instruction"].lower() or "wrong" in tpl["instruction"].lower()
    # Adds new community signal not in builtin triggers
    assert "community_signal_xyz" in tpl["triggers"]


def test_build_community_templates_new_type():
    """For an unknown gap_type, source is 'community_new'."""
    freq = {
        "totally_new_gap_type_xyz": {
            "count": 8,
            "unique_sources": 6,
            "top_signals": ["some signal"],
        },
    }

    import ai_rule_learning_mcp.community as community

    original_token = community.HF_TOKEN
    community.HF_TOKEN = "fake-token"
    try:
        with patch.object(community, "fetch_community_patterns", return_value=freq):
            templates = community.build_community_templates(min_sources=3)
    finally:
        community.HF_TOKEN = original_token

    assert len(templates) == 1
    assert templates[0]["source"] == "community_new"
    assert templates[0]["gap_type"] == "totally_new_gap_type_xyz"


# ---------------------------------------------------------------------------
# load_community_templates + detect_gaps RAG augmentation
# ---------------------------------------------------------------------------

def test_load_community_templates_rag_detection():
    """After loading community templates, detect_gaps finds matches via community triggers."""
    import ai_rule_learning_mcp.gap_detector as gd

    # Reset any previously loaded community templates
    gd._community_extra = {}

    community_template = {
        "gap_type": "community_custom_gap",
        "name": "community-custom",
        "instruction": "Do something about community_custom_gap.",
        "priority": 2,
        "failure_layer": 1,
        "failure_category": "output_quality",
        "triggers": ["community_unique_trigger_phrase"],
        "source": "community_new",
        "unique_sources": 5,
    }

    gd.load_community_templates([community_template])

    turns = [
        {"user_input": "this contains community_unique_trigger_phrase here", "agent_response": "ok"},
    ]
    gaps = gd.detect_gaps(turns)

    assert "community_custom_gap" in gaps
    instances = gaps["community_custom_gap"]
    assert len(instances) == 1
    assert instances[0]["source"] == "community"
    assert instances[0]["signal"] == "community_unique_trigger_phrase"

    # Cleanup
    gd._community_extra = {}


# ---------------------------------------------------------------------------
# pull_community_templates — error path
# ---------------------------------------------------------------------------

def test_pull_community_templates_empty_on_error():
    """Returns [] when HF raises an exception (e.g. file not found)."""
    import ai_rule_learning_mcp.community as community

    with patch("huggingface_hub.hf_hub_download", side_effect=Exception("not found")):
        result = community.pull_community_templates()

    assert result == []
