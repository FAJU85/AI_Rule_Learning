"""Community dataset contribution — personal tier opt-in.

Only anonymised gap patterns (type, count, severity) are sent to the
community pool. Raw conversation text NEVER leaves the user's machine.

Community dataset: vooom/AI_Rule_Learning_Community (public, opt-in only)
"""

from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime

COMMUNITY_DATASET = "vooom/AI_Rule_Learning_Community"
HF_TOKEN = os.environ.get("HF_TOKEN", "")


def _gap_pattern(gap: dict) -> dict:
    return {
        "type": gap.get("type", "unknown"),
        "severity": gap.get("severity", 1),
        "turn": gap.get("turn", 0),
        "signal": gap.get("signal", ""),  # trigger phrase, no raw text
    }


def contribute_gaps(gaps_by_type: dict[str, list[dict]], source_hash: str) -> bool:
    """Submit anonymised gap pattern counts to the community dataset.

    Only gap type/severity/turn metadata is sent — no conversation text.
    source_hash is SHA-256 of session_id and is used for deduplication only.
    """
    if not HF_TOKEN:
        return False

    patterns = {gtype: [_gap_pattern(g) for g in gaps] for gtype, gaps in gaps_by_type.items() if gaps}
    if not patterns:
        return False

    record = {
        "source_hash": source_hash,
        "contributed_at": datetime.utcnow().isoformat(),
        "gap_patterns": patterns,
        "total_gaps": sum(len(v) for v in patterns.values()),
    }

    try:
        from huggingface_hub import HfApi
        from huggingface_hub import hf_hub_download
        from huggingface_hub.errors import EntryNotFoundError

        api = HfApi(token=HF_TOKEN)

        existing: list[dict] = []
        try:
            path = hf_hub_download(
                repo_id=COMMUNITY_DATASET,
                filename="contributions.jsonl",
                repo_type="dataset",
                token=HF_TOKEN,
                force_download=True,
            )
            with open(path, encoding="utf-8") as f:
                existing = [json.loads(l) for l in f if l.strip()]
        except (EntryNotFoundError, Exception):
            pass

        if record["source_hash"] in {r.get("source_hash") for r in existing}:
            return False

        updated = existing + [record]
        content = "\n".join(json.dumps(r, ensure_ascii=False) for r in updated) + "\n"
        api.upload_file(
            path_or_fileobj=content.encode(),
            path_in_repo="contributions.jsonl",
            repo_id=COMMUNITY_DATASET,
            repo_type="dataset",
            commit_message="mcp: anonymised gap contribution",
        )
        return True
    except Exception:
        return False


def fetch_community_patterns() -> dict[str, dict]:
    """Download contributions.jsonl from the community dataset and aggregate patterns.

    Returns {gap_type: {"count": N, "unique_sources": N, "top_signals": [...]}}
    Returns {} on any error or when HF_TOKEN is not set.
    """
    if not HF_TOKEN:
        return {}

    try:
        from huggingface_hub import hf_hub_download

        path = hf_hub_download(
            repo_id=COMMUNITY_DATASET,
            filename="contributions.jsonl",
            repo_type="dataset",
            token=HF_TOKEN,
            force_download=True,
        )
        records: list[dict] = []
        with open(path, encoding="utf-8") as f:
            records = [json.loads(line) for line in f if line.strip()]
    except Exception:
        return {}

    freq: dict[str, dict] = {}
    for record in records:
        source_hash = record.get("source_hash", "")
        gap_patterns = record.get("gap_patterns", {})
        for gap_type, instances in gap_patterns.items():
            entry = freq.setdefault(gap_type, {"count": 0, "unique_sources": set(), "_signal_counts": Counter()})
            entry["count"] += len(instances)
            entry["unique_sources"].add(source_hash)
            for inst in instances:
                sig = inst.get("signal", "")
                if sig:
                    entry["_signal_counts"][sig] += 1

    result: dict[str, dict] = {}
    for gap_type, entry in freq.items():
        top_signals = [sig for sig, _ in entry["_signal_counts"].most_common(8)]
        result[gap_type] = {
            "count": entry["count"],
            "unique_sources": len(entry["unique_sources"]),
            "top_signals": top_signals,
        }
    return result


def build_community_templates(min_sources: int = 3) -> list[dict]:
    """Build enhanced rule templates from community patterns.

    For each gap_type with unique_sources >= min_sources:
    - If gap_type is in _TEMPLATES: enhance the builtin with new signals.
    - If gap_type is not in _TEMPLATES: create a basic community-new template.

    Returns list of template dicts.
    """
    from .gap_detector import _TEMPLATES

    freq = fetch_community_patterns()
    if not freq:
        return []

    templates: list[dict] = []
    for gap_type, stats in freq.items():
        if stats["unique_sources"] < min_sources:
            continue

        community_signals = stats["top_signals"]
        builtin = _TEMPLATES.get(gap_type)

        if builtin:
            existing_triggers = set(builtin.get("triggers", []))
            new_signals = [s for s in community_signals if s not in existing_triggers]
            merged_triggers = list(existing_triggers) + new_signals
            templates.append({
                "gap_type": gap_type,
                "name": builtin["name"],
                "instruction": builtin["instruction"],
                "priority": builtin["priority"],
                "failure_layer": builtin["failure_layer"],
                "failure_category": builtin["failure_category"],
                "triggers": merged_triggers,
                "source": "community_enhanced",
                "unique_sources": stats["unique_sources"],
            })
        else:
            templates.append({
                "gap_type": gap_type,
                "name": f"community-pattern-{gap_type}",
                "instruction": (
                    f"[Community-discovered pattern: {gap_type}. "
                    "Needs human review before activation.] "
                    "This pattern was detected across multiple independent sessions "
                    "but has not yet been mapped to a verified guardrail instruction."
                ),
                "priority": 2,
                "failure_layer": 1,
                "failure_category": "output_quality",
                "triggers": community_signals,
                "source": "community_new",
                "unique_sources": stats["unique_sources"],
            })

    return templates


def push_community_templates(templates: list[dict]) -> bool:
    """Upload derived templates as community_templates.jsonl to the community dataset.

    Requires HF_TOKEN and write access. Returns True on success, False otherwise.
    """
    if not HF_TOKEN:
        return False

    try:
        from huggingface_hub import HfApi

        api = HfApi(token=HF_TOKEN)
        content = "\n".join(json.dumps(t, ensure_ascii=False) for t in templates) + "\n"
        api.upload_file(
            path_or_fileobj=content.encode(),
            path_in_repo="community_templates.jsonl",
            repo_id=COMMUNITY_DATASET,
            repo_type="dataset",
            commit_message="mcp: derived community templates",
        )
        return True
    except Exception:
        return False


def pull_community_templates() -> list[dict]:
    """Download community_templates.jsonl from the community dataset.

    No token required (public dataset). Returns list of template dicts,
    empty list on any error.
    """
    try:
        from huggingface_hub import hf_hub_download

        path = hf_hub_download(
            repo_id=COMMUNITY_DATASET,
            filename="community_templates.jsonl",
            repo_type="dataset",
            force_download=True,
        )
        templates: list[dict] = []
        with open(path, encoding="utf-8") as f:
            templates = [json.loads(line) for line in f if line.strip()]
        return templates
    except Exception:
        return []
